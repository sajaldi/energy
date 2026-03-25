import time
import os
from django.contrib import messages
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
    from mantenimiento.models import Rutina
    from django.shortcuts import get_object_or_404, redirect
    from django.contrib import admin, messages
    
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
            kpi.save()
        else:
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
        'categorias': KPI.CATEGORIA_CHOICES,
        'estados': KPI.ESTADO_CHOICES,
        'checklist_items': kpi.checklist_items.all().order_by('orden') if kpi else [],
        'documentos_relacionados': documentos_relacionados,
        'historial_auditorias': kpi.resultados_auditoria.all().select_related('auditoria').order_by('-auditoria__fecha') if kpi else [],
    }
    return render(request, 'servicios/kpi_form.html', context)


@staff_member_required
def auditoria_form_view(request, pk=None):
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
