import time
import os
from django.contrib import admin, messages
from django.utils import timezone
from django.contrib.admin.views.decorators import staff_member_required
from django.core.cache import cache
from django.core.files.storage import default_storage
from django.http import JsonResponse
from django.shortcuts import render
from celery.result import AsyncResult
from .tasks import import_kpis_task
from django.views.decorators.csrf import csrf_exempt
from django.contrib.contenttypes.models import ContentType
from documentos.models import MetadatoValor

@staff_member_required
def kpi_form_view(request, pk=None):
    """Vista de formulario KPI estilo SAP Fiori con editor Markdown."""
    from .models import KPI, Servicio, ChecklistItem, Auditoria, AuditoriaResultado
    from mantenimiento.models import Rutina, Frecuencia
    from django.shortcuts import get_object_or_404, redirect
    
    kpi = get_object_or_404(KPI, pk=pk) if pk else None
    servicios = Servicio.objects.filter(activo=True).order_by('nombre')
    rutinas_todas = Rutina.objects.all().order_by('nombre')
    
    if request.method == 'POST':
        servicio_id = request.POST.get('servicio')
        nombre = request.POST.get('nombre', '')
        descripcion = request.POST.get('descripcion', '')
        forma_de_cumplimiento = request.POST.get('forma_de_cumplimiento', '')
        metodo_de_supervision = request.POST.get('metodo_de_supervision', '')
        categoria = request.POST.get('categoria', 'MAYOR')
        estado = request.POST.get('estado', 'CUMPLIMIENTO')
        fecha_medicion = request.POST.get('fecha_medicion')
        comentarios = request.POST.get('comentarios', '')
        
        if kpi:
            kpi.servicio_id = servicio_id
            kpi.nombre = nombre
            kpi.descripcion = descripcion
            kpi.forma_de_cumplimiento = forma_de_cumplimiento
            kpi.metodo_de_supervision = metodo_de_supervision
            kpi.categoria = categoria
            kpi.estado = estado
            kpi.comentarios = comentarios
            if fecha_medicion:
                kpi.fecha_medicion = fecha_medicion
            freq_id = request.POST.get('frecuencia_supervision')
            kpi.frecuencia_supervision_id = int(freq_id) if freq_id else None
            kpi.save()
        else:
            freq_id = request.POST.get('frecuencia_supervision')
            kpi = KPI.objects.create(
                servicio_id=servicio_id,
                nombre=nombre,
                descripcion=descripcion,
                forma_de_cumplimiento=forma_de_cumplimiento,
                metodo_de_supervision=metodo_de_supervision,
                categoria=categoria,
                estado=estado,
                comentarios=comentarios,
                fecha_medicion=fecha_medicion or None,
                frecuencia_supervision_id=int(freq_id) if freq_id else None,
            )
        
        # Procesar Rutinas M2M
        rutinas_ids = request.POST.getlist('rutinas')
        kpi.rutinas.set(rutinas_ids)
        
        # Procesar checklist items
        checklist_items = request.POST.getlist('checklist_desc[]')
        checklist_checks = request.POST.getlist('checklist_done[]')
        
        # Borrar existentes y recrear
        kpi.checklist_items.all().delete()
        for i, desc in enumerate(checklist_items):
            if desc.strip():
                ChecklistItem.objects.create(
                    kpi=kpi,
                    descripcion=desc.strip(),
                    completado=str(i) in checklist_checks,
                    orden=i
                )
        
        messages.success(request, f'KPI "{kpi.nombre}" guardado exitosamente.')
        return redirect('servicios:kpi_form_edit', pk=kpi.pk)
    
    # Obtener documentos relacionados (vía MetadatoValor GenericForeignKey)
    documentos_relacionados = []
    if kpi:
        kpi_ct = ContentType.objects.get_for_model(KPI)
        documentos_relacionados = MetadatoValor.objects.filter(
            content_type=kpi_ct,
            object_id=kpi.id
        ).select_related('documento', 'documento__ultima_revision')

    context = {
        **admin.site.each_context(request),
        'title': f'Editar KPI: {kpi.nombre}' if kpi else 'Nuevo KPI',
        'kpi': kpi,
        'servicios': servicios,
        'rutinas_todas': rutinas_todas,
        'rutinas_seleccionadas_ids': list(kpi.rutinas.values_list('id', flat=True)) if kpi else [],
        'frecuencias': Frecuencia.objects.all().order_by('dias'),
        'categorias': KPI.CATEGORIA_CHOICES,
        'estados': KPI.ESTADO_CHOICES,
        'checklist_items': kpi.checklist_items.all().order_by('orden') if kpi else [],
        'documentos_relacionados': documentos_relacionados,
        'historial_auditorias': kpi.resultados_auditoria.all().select_related('auditoria').order_by('-auditoria__fecha') if kpi else [],
    }
    return render(request, 'servicios/kpi_form.html', context)


@staff_member_required
@csrf_exempt
def api_kpi_subir_archivo(request, pk):
    """API para subir un archivo a un KPI."""
    from django.shortcuts import get_object_or_404
    from .models import KPI, KPIArchivo
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
    kpi = get_object_or_404(KPI, pk=pk)
    archivo = request.FILES.get('archivo')
    if not archivo:
        return JsonResponse({'status': 'error', 'message': 'No se envió ningún archivo'}, status=400)
    descripcion = request.POST.get('descripcion', '')
    obj = KPIArchivo.objects.create(
        kpi=kpi, archivo=archivo,
        descripcion=descripcion,
        subido_por=request.user
    )
    return JsonResponse({
        'status': 'success',
        'id': obj.id,
        'nombre': obj.nombre,
        'url': obj.archivo.url,
        'creado_en': obj.creado_en.isoformat(),
    })


@staff_member_required
@csrf_exempt
def api_kpi_eliminar_archivo(request, pk):
    """API para eliminar un archivo de un KPI."""
    from django.shortcuts import get_object_or_404
    from .models import KPIArchivo
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
    archivo = get_object_or_404(KPIArchivo, pk=pk)
    archivo.archivo.delete(save=False)
    archivo.delete()
    return JsonResponse({'status': 'success'})


@staff_member_required
def auditoria_form_view(request, pk=None):
    from django.shortcuts import get_object_or_404, redirect
    from .models import KPI, Auditoria, AuditoriaResultado

    auditoria = get_object_or_404(Auditoria, pk=pk) if pk else None
    
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        fecha = request.POST.get('fecha')
        descripcion = request.POST.get('descripcion', '')
        
        if auditoria:
            auditoria.nombre = nombre
            auditoria.fecha = fecha
            auditoria.descripcion = descripcion
            auditoria.save()
        else:
            auditoria = Auditoria.objects.create(
                nombre=nombre,
                fecha=fecha,
                descripcion=descripcion
            )
            
        # Procesar resultados de KPIs
        kpi_ids = request.POST.getlist('kpi_id[]')
        cumples = request.POST.getlist('cumple[]')
        planes = request.POST.getlist('plan_de_accion[]')
        observaciones = request.POST.getlist('observaciones[]')
        
        # Primero eliminar resultados previos si estamos editando
        if pk:
            auditoria.resultados.all().delete()
            
        for i in range(len(kpi_ids)):
            if kpi_ids[i]:
                AuditoriaResultado.objects.create(
                    auditoria=auditoria,
                    kpi_id=kpi_ids[i],
                    cumple=cumples[i] == 'true',
                    plan_de_accion=planes[i],
                    observaciones=observaciones[i]
                )
        
        messages.success(request, f'Auditoría "{auditoria.nombre}" guardada exitosamente.')
        return redirect('servicios:auditoria_form_edit', pk=auditoria.pk)

    kpis = KPI.objects.select_related('servicio').all().order_by('servicio__nombre', 'nombre')
    resultados = auditoria.resultados.all().select_related('kpi') if auditoria else []

    context = {
        **admin.site.each_context(request),
        'title': f'Editar Auditoría: {auditoria.nombre}' if auditoria else 'Nueva Auditoría',
        'auditoria': auditoria,
        'today_str': timezone.now().strftime('%Y-%m-%d'),
        'kpis_todos': kpis,
        'resultados': resultados,
        'resultados_dict': {r.kpi_id: r for r in resultados},
    }
    return render(request, 'servicios/auditoria_form.html', context)


@staff_member_required
def import_kpis_background(request):
    from django.contrib import admin
    context = {
        **admin.site.each_context(request),
        'title': 'Importación masiva de KPIs (Background)',
    }
    return render(request, 'admin/servicios/kpi/import_background.html', context)

@staff_member_required
@csrf_exempt
def import_kpis_process(request):
    import sys
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    is_confirm = request.POST.get('confirm', '').lower() in ['true', 'on', '1']
    existing_path = request.POST.get('file_path')
    import_file = request.FILES.get('import_file')

    if not is_confirm:
        if not import_file:
            return JsonResponse({'error': 'No se subió ningún archivo'}, status=400)
            
        file_ext = import_file.name.split('.')[-1].lower()
        temp_name = f'tmp/import_kpis_{request.user.id}_{int(time.time())}.{file_ext}'
        
        try:
            path = default_storage.save(temp_name, import_file)
        except Exception as e:
            return JsonResponse({'error': f'Error al guardar archivo: {str(e)}'}, status=500)
    else:
        if not existing_path:
            return JsonResponse({'error': 'Falta la ruta del archivo para confirmar'}, status=400)
        path = existing_path
        file_ext = path.split('.')[-1].lower()
    
    cache_key = f"import_kpis_progress_{request.user.id}"
    cache.delete(cache_key)
    
    v_val = request.POST.get('verification_mode', '').lower()
    verification_mode = v_val in ['true', 'on', '1']
    dry_run = (not verification_mode) and (not is_confirm)
    
    import_name = request.POST.get('name') or f"KPIs: {import_file.name if import_file else os.path.basename(path)}"
    
    task = import_kpis_task.delay(
        path, 
        file_ext, 
        user_id=request.user.id, 
        verification_mode=verification_mode,
        dry_run=dry_run
    )
    
    return JsonResponse({
        'status': 'started', 
        'task_id': task.id, 
        'dry_run': dry_run,
        'verification_mode': verification_mode
    })

@staff_member_required
def import_kpis_progress(request):
    task_id = request.GET.get('task_id')
    if not task_id:
        return JsonResponse({'error': 'Falta task_id'}, status=400)
        
    cache_key = f"import_kpis_progress_{request.user.id}"
    progress = cache.get(cache_key, {'status': 'pending', 'percent': 0})
    
    res = AsyncResult(task_id)
    if res.state == 'SUCCESS':
        if isinstance(res.result, dict):
            progress.update(res.result)
        progress['state'] = 'COMPLETED'
        progress['percent'] = 100
    elif res.state == 'FAILURE':
        progress['error'] = str(res.result)
        progress['state'] = 'FAILURE'
    elif res.state == 'PROGRESS':
        if isinstance(res.info, dict):
            progress.update(res.info)
        progress['state'] = 'PROGRESS'
    else:
        progress['state'] = res.state if res else 'PENDING'
        
    return JsonResponse(progress)


@staff_member_required
def kpi_dashboard_view(request):
    """Dashboard de KPIs agrupados por servicio."""
    from .models import Servicio, KPI
    from django.contrib import admin
    from django.shortcuts import render
    
    # Obtener servicios con sus KPIs pre-cargados
    servicios = Servicio.objects.filter(activo=True).prefetch_related('kpis').order_by('nombre')
    
    # Métricas generales
    total_servicios = servicios.count()
    total_kpis = KPI.objects.count()
    kpis_cumplimiento = KPI.objects.filter(estado='CUMPLIMIENTO').count()
    kpis_parcial = KPI.objects.filter(estado='PARCIAL').count()
    kpis_incumplimiento = KPI.objects.filter(estado='INCUMPLIMIENTO').count()
    
    # Calcular porcentaje de cumplimiento global
    cumplimiento_global = 0
    if total_kpis > 0:
        cumplimiento_global = int((kpis_cumplimiento / total_kpis) * 100)
    
    # Agrupar datos para el template
    servicios_data = []
    for s in servicios:
        kpis = s.kpis.all().order_by('nombre')
        kpis_count = kpis.count()
        kpis_ok = kpis.filter(estado='CUMPLIMIENTO').count()
        
        status_color = 'success'
        if kpis_count > 0:
            percent = (kpis_ok / kpis_count) * 100
            if percent < 50: status_color = 'danger'
            elif percent < 90: status_color = 'warning'
        
        servicios_data.append({
            'obj': s,
            'kpis': kpis,
            'kpis_count': kpis_count,
            'kpis_ok': kpis_ok,
            'status_color': status_color,
            'percent': int((kpis_ok / kpis_count * 100) if kpis_count > 0 else 0)
        })

    context = {
        **admin.site.each_context(request),
        'title': 'Dashboard de KPI por Servicio',
        'servicios_data': servicios_data,
        'total_servicios': total_servicios,
        'total_kpis': total_kpis,
        'kpis_cumplimiento': kpis_cumplimiento,
        'kpis_parcial': kpis_parcial,
        'kpis_incumplimiento': kpis_incumplimiento,
        'cumplimiento_global': cumplimiento_global,
    }
    return render(request, 'admin/servicios/kpi/dashboard.html', context)


# ================================================================
# RAG + Búsqueda Vectorial Semántica de KPIs
# ================================================================

@staff_member_required
def kpi_buscador_view(request):
    """Renderiza la interfaz premium del buscador semántico RAG de KPIs."""
    from django.contrib import admin
    context = {
        **admin.site.each_context(request),
        'title': 'Buscador Inteligente de KPIs',
    }
    return render(request, 'admin/servicios/kpi/buscador_rag.html', context)


@staff_member_required
def api_kpi_busqueda_semantica(request):
    """
    API que realiza búsqueda híbrida de KPIs (texto + vector).
    Usa el embedding de la consulta para buscar similitud de coseno.
    """
    from .models import KPI, KPIFragmento
    from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
    from pgvector.django import CosineDistance
    from core.ai_utils import get_embedding

    query_text = request.GET.get('q', '').strip()
    if not query_text:
        return JsonResponse({'status': 'error', 'message': 'Query vacía'})

    # 1. Búsqueda Vectorial (Semántica)
    vector_results = []
    try:
        query_embedding = get_embedding(query_text, task_type="retrieval_query")
        if query_embedding:
            # Buscar en fragmentos
            fragmentos = KPIFragmento.objects.annotate(
                distance=CosineDistance('embedding', query_embedding)
            ).order_by('distance')[:20]
            
            kpi_ids_vistos = set()
            for f in fragmentos:
                if f.kpi_id not in kpi_ids_vistos:
                    similitud = 1 - float(f.distance)
                    if similitud > 0.35: 
                        vector_results.append({
                            'id': f.kpi.id,
                            'nombre': f.kpi.nombre,
                            'servicio': f.kpi.servicio.nombre,
                            'categoria': f.kpi.get_categoria_display(),
                            'estado': f.kpi.get_estado_display(),
                            'estado_raw': f.kpi.estado,
                            'descripcion': (f.kpi.descripcion or '')[:200],
                            'fragmento_preview': f.contenido[:200] + '...',
                            'similitud': round(similitud, 4),
                            'match_type': 'semantica'
                        })
                        kpi_ids_vistos.add(f.kpi_id)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Error búsqueda semántica: {e}")

    # 2. Búsqueda de Texto
    text_results = []
    try:
        kpis_texto = KPI.objects.annotate(
            rank=SearchRank(
                SearchVector('nombre', weight='A') + 
                SearchVector('descripcion', weight='B') +
                SearchVector('servicio__nombre', weight='C'),
                SearchQuery(query_text)
            )
        ).filter(rank__gte=0.1).order_by('-rank')[:15]

        for k in kpis_texto:
            text_results.append({
                'id': k.id,
                'nombre': k.nombre,
                'servicio': k.servicio.nombre,
                'categoria': k.get_categoria_display(),
                'estado': k.get_estado_display(),
                'estado_raw': k.estado,
                'descripcion': (k.descripcion or '')[:200],
                'similitud': round(float(k.rank), 4),
                'match_type': 'texto'
            })
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Error búsqueda texto: {e}")

    # 3. Fusionar
    final_map = {r['id']: r for r in vector_results}
    for r in text_results:
        if r['id'] not in final_map:
            final_map[r['id']] = r
        else:
            final_map[r['id']]['match_type'] = 'hibrido'

    resultados = sorted(final_map.values(), key=lambda x: x['similitud'], reverse=True)
    return JsonResponse({'status': 'success', 'resultados': resultados[:20]})

@staff_member_required
def api_kpi_rag(request):
    """
    RAG (Retrieval Augmented Generation) para KPIs usando Gemini u Ollama.
    """
    from .models import KPIFragmento
    from pgvector.django import CosineDistance
    from core.ai_utils import get_embedding, ask_ia

    query_text = request.GET.get('q', '').strip()
    if not query_text:
        return JsonResponse({'status': 'error', 'message': 'Query vacía'})

    try:
        query_embedding = get_embedding(query_text, task_type="retrieval_query")
        if not query_embedding:
            return JsonResponse({'status': 'error', 'message': 'No se pudo procesar la consulta IA'})

        fragmentos = KPIFragmento.objects.annotate(
            distance=CosineDistance('embedding', query_embedding)
        ).order_by('distance')[:7]

        context_parts = []
        fuentes = []
        seen_ids = set()
        for f in fragmentos:
            if (1 - float(f.distance)) > 0.35:
                context_parts.append(f"KPI: {f.kpi.nombre} ({f.kpi.servicio.nombre})\nContenido: {f.contenido}")
                if f.kpi_id not in seen_ids:
                    fuentes.append({
                        'id': f.kpi.id,
                        'nombre': f.kpi.nombre,
                        'servicio': f.kpi.servicio.nombre,
                        'similitud': round(1 - float(f.distance), 4)
                    })
                    seen_ids.add(f.kpi_id)

        contexto = "\n\n".join(context_parts)
        if not contexto:
            return JsonResponse({'status': 'success', 'respuesta': 'No encontré información relevante en los KPIs.', 'fuentes': []})

        system_prompt = "Eres un analista de servicios. Responde basándote solo en el contexto proporcionado sobre KPIs. Usa Markdown."
        respuesta = ask_ia(query_text, context=contexto, system_prompt=system_prompt)

        return JsonResponse({
            'status': 'success',
            'respuesta': respuesta,
            'fuentes': fuentes
        })
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error RAG: {str(e)}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@staff_member_required
def api_kpi_vectorize_all(request):
    """Trigger manual para re-indexar todos los KPIs (solo superusers)."""
    if not request.user.is_superuser:
        return JsonResponse({'error': 'No autorizado'}, status=403)

    from .tasks import vectorize_all_kpis
    from .models import KPI

    total = KPI.objects.count()
    vectorize_all_kpis.delay()

    return JsonResponse({
        'status': 'success',
        'message': f'Vectorización de {total} KPIs iniciada. Los embeddings se generarán en segundo plano.',
        'total': total
    })

