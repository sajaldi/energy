from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, FileResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.urls import reverse
from django import forms
from django.db import IntegrityError
from .models import Actividad, Proyecto, DocumentoProyecto, ObservacionProyecto, PlanoProyecto, PinObservacionProyecto, FotoPinObservacion, AreaPlanoProyecto, ElementoProyecto, ElementoDocumento
from documentos.models import Carpeta, Documento, Revision, TipoDocumento, Disciplina
import json
import os
from datetime import datetime, timedelta
from core.ai_utils import ask_gemini

@csrf_exempt
@staff_member_required
def crear_actividad_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            nombre = data.get('nombre')
            proyecto_id = data.get('proyecto_id')
            prioridad = data.get('prioridad', 'MEDIA')
            fecha_inicio = data.get('fecha_inicio')
            fecha_fin = data.get('fecha_fin')
            predecesora_id = data.get('predecesora_id')
            
            # Aceptar estado personalizado con validación
            ESTADOS_VALIDOS = ['PENDIENTE', 'EN_PROGRESO', 'COMPLETADA', 'BLOQUEADA']
            estado = data.get('estado', 'PENDIENTE')
            if estado not in ESTADOS_VALIDOS:
                return JsonResponse({'status': 'error', 'message': f'Estado inválido. Valores permitidos: {", ".join(ESTADOS_VALIDOS)}'}, status=400)
            
            # Aceptar asignado_id con fallback a request.user
            from django.contrib.auth.models import User
            asignado_id = data.get('asignado_id')
            if asignado_id:
                asignado_a = User.objects.filter(pk=asignado_id).first()
                if not asignado_a:
                    asignado_a = request.user
            else:
                asignado_a = request.user
            
            if not nombre or not proyecto_id:
                return JsonResponse({'status': 'error', 'message': 'Faltan datos obligatorios'}, status=400)
            
            proyecto = Proyecto.objects.get(pk=proyecto_id)
            
            ultimo_orden = Actividad.objects.filter(proyecto=proyecto).order_by('-orden').first()
            orden = (ultimo_orden.orden + 1) if ultimo_orden else 1
            
            predecesora = None
            if predecesora_id:
                predecesora = Actividad.objects.filter(pk=predecesora_id).first()

            actividad = Actividad.objects.create(
                proyecto=proyecto,
                nombre=nombre,
                prioridad=prioridad,
                estado=estado,
                orden=orden,
                asignado_a=asignado_a,
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                predecesora=predecesora
            )
            actividad.refresh_from_db()
            
            return JsonResponse({
                'status': 'success',
                'actividad': {
                    'id': actividad.id,
                    'nombre': actividad.nombre,
                    'fecha_inicio': actividad.fecha_inicio.isoformat() if actividad.fecha_inicio else None,
                    'fecha_fin': actividad.fecha_fin.isoformat() if actividad.fecha_fin else None,
                    'dependencies': [str(actividad.predecesora.id)] if actividad.predecesora else [],
                    'color': actividad.color,
                    'estado': actividad.get_estado_display(),
                    'asignado_a_id': actividad.asignado_a_id,
                    'asignado_a_nombre': (actividad.asignado_a.get_full_name() or actividad.asignado_a.username) if actividad.asignado_a else None,
                }
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

@csrf_exempt
@staff_member_required
def actualizar_actividad_api(request, actividad_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            actividad = get_object_or_404(Actividad, pk=actividad_id)
            
            if 'fecha_inicio' in data:
                val = data.get('fecha_inicio')
                actividad.fecha_inicio = val if val else None
            if 'fecha_fin' in data:
                val = data.get('fecha_fin')
                actividad.fecha_fin = val if val else None
            if 'nombre' in data:
                actividad.nombre = data.get('nombre')
            if 'estado' in data:
                actividad.estado = data.get('estado')
            if 'predecesora_id' in data:
                pid = data.get('predecesora_id')
                actividad.predecesora = Actividad.objects.filter(pk=pid).first() if pid else None
            if 'descripcion' in data:
                actividad.descripcion = data.get('descripcion')
            if 'prioridad' in data:
                actividad.prioridad = data.get('prioridad')
            if 'porcentaje_avance' in data:
                actividad.porcentaje_avance = int(data.get('porcentaje_avance'))
            if 'ordenes_trabajo_ids' in data:
                from mantenimiento.models import OrdenTrabajo
                ids = data.get('ordenes_trabajo_ids', [])
                ots = OrdenTrabajo.objects.filter(id__in=ids)
                actividad.ordenes_trabajo.set(ots)

            actividad.save()
            return JsonResponse({'status': 'success', 'message': 'Actividad actualizada'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

@staff_member_required
def cronograma_proyecto(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    actividades = proyecto.actividades.all().order_by('orden', 'fecha_inicio')
    
    # Determinar rango de semanas (Año actual por defecto)
    try:
        year_raw = request.GET.get('year', str(datetime.now().year))
        year = int(str(year_raw).replace('\xa0', '').replace(' ', '').replace(',', ''))
    except (ValueError, TypeError):
        year = datetime.now().year
    
    # Generar estructura de semanas por mes
    meses_data = []
    meses_nombres = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    
    for m in range(1, 13):
        # Encontrar semanas que empiezan en este mes
        semanas_mes = []
        d = datetime(year, m, 1)
        # Avanzar hasta el primer lunes o usar el lunes previo
        # Pero para simplificar, usaremos una lógica de 52 semanas directa
        pass

    # Lógica simplificada: 52 semanas
    semanas = []
    base_date = datetime(year, 1, 1)
    # Ajustar al primer lunes del año
    if base_date.weekday() != 0:
        base_date += timedelta(days=(7 - base_date.weekday()))
    
    for i in range(52):
        start_week = base_date + timedelta(weeks=i)
        end_week = start_week + timedelta(days=6)
        semanas.append({
            'n': i + 1,
            'inicio': start_week,
            'fin': end_week,
            'mes': meses_nombres[start_week.month - 1]
        })

    # Preparar celdas para cada actividad
    for act in actividades:
        act.celdas = []
        for sem in semanas:
            is_active = False
            if act.fecha_inicio and act.fecha_fin:
                # Si la semana se solapa con el rango de la actividad
                if act.fecha_inicio <= sem['fin'].date() and act.fecha_fin >= sem['inicio'].date():
                    is_active = True
            act.celdas.append(is_active)

    # Agrupar semanas por mes para el header
    meses_header = []
    for m_name in meses_nombres:
        sems_en_mes = [s for s in semanas if s['mes'] == m_name]
        if sems_en_mes:
            meses_header.append({
                'nombre': m_name,
                'count': len(sems_en_mes)
            })

    return render(request, 'proyectos/cronograma.html', {
        'proyecto': proyecto,
        'actividades': actividades,
        'semanas': semanas,
        'meses_header': meses_header,
        'year': year,
    })

@staff_member_required
def gantt_proyecto(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    actividades = proyecto.actividades.all().order_by('orden')
    
    tasks = []
    for act in actividades:
        tasks.append({
            'id': str(act.id),
            'name': act.nombre,
            'start': act.fecha_inicio.isoformat() if act.fecha_inicio else (act.creado_en.date().isoformat()),
            'end': act.fecha_fin.isoformat() if act.fecha_fin else ((act.fecha_inicio or act.creado_en.date()) + timedelta(days=1)).isoformat(),
            'progress': 100 if act.estado == 'COMPLETADA' else 0,
            'dependencies': [str(act.predecesora.id)] if act.predecesora else [],
            'custom_class': f'gantt-item-{act.prioridad.lower()}'
        })
    
    return render(request, 'proyectos/gantt_proyecto.html', {
        'proyecto': proyecto,
        'tasks_json': json.dumps(tasks),
        'actividades': actividades,
    })

@csrf_exempt
@staff_member_required
def chatbot_asistente(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            pregunta = data.get('mensaje')
            historial = data.get('historial', [])  # [{role: 'user'|'assistant', content: '...'}]
            if not pregunta:
                return JsonResponse({'status': 'error', 'message': 'Mensaje vacío'}, status=400)
            
            respuesta = ask_gemini(pregunta, historial=historial)
            return JsonResponse({'status': 'success', 'respuesta': respuesta})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    return render(request, 'proyectos/chatbot_asistente.html')

@staff_member_required
def repositorio_documentos(request, proyecto_id):
    """
    Vista de galería para visualizar todos los documentos vinculados a un proyecto.
    """
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    # Obtener documentos a través de la relación ManyToMany inversa definida en DocumentoProyecto
    documentos_vinculados = proyecto.documentos_proyecto.all().select_related('documento__tipo_documento')
    
    # Extraer los objetos documento reales
    documentos = [dv.documento for dv in documentos_vinculados]
    
    # Obtener avisos vinculados al proyecto
    avisos = proyecto.avisos.all()
    
    context = {
        'proyecto': proyecto,
        'documentos': documentos,
        'avisos': avisos,
        'estados': Documento.ESTADOS,
    }
    return render(request, 'proyectos/repositorio_documentos.html', context)

@staff_member_required
def crear_proyecto(request):
    from activos.models import Ubicacion
    from django.contrib.auth.models import User

    class ProyectoForm(forms.ModelForm):
        class Meta:
            model = Proyecto
            fields = ['codigo', 'nombre', 'descripcion', 'estado', 'fecha_inicio', 'fecha_fin_estimada', 'responsable', 'ubicacion', 'nota']
            widgets = {
                'descripcion': forms.Textarea(attrs={'rows': 3}),
                'nota': forms.Textarea(attrs={'rows': 3}),
                'fecha_inicio': forms.DateInput(attrs={'type': 'date'}),
                'fecha_fin_estimada': forms.DateInput(attrs={'type': 'date'}),
                'ubicacion': forms.HiddenInput(),
            }

    ubicaciones_roots = Ubicacion.objects.filter(padre__isnull=True).prefetch_related(
        'sub_ubicaciones',
        'sub_ubicaciones__sub_ubicaciones',
        'sub_ubicaciones__sub_ubicaciones__sub_ubicaciones',
        'sub_ubicaciones__sub_ubicaciones__sub_ubicaciones__sub_ubicaciones',
    ).order_by('orden', 'nombre')

    if request.method == 'POST':
        form = ProyectoForm(request.POST)
        if form.is_valid():
            proyecto = form.save()
            messages.success(request, f'Proyecto {proyecto.codigo} creado exitosamente.')
            return redirect('proyectos:detalle_fiori', pk=proyecto.pk)
    else:
        form = ProyectoForm(initial={'estado': 'PLANIFICACION'})

    return render(request, 'proyectos/proyecto_form.html', {
        'form': form,
        'titulo': 'Nuevo Proyecto',
        'accion': 'Crear',
        'ubicaciones_roots': ubicaciones_roots,
    })

@staff_member_required
def dashboard_proyectos_fiori(request):
    """
    Panel principal de Proyectos con estética SAP Fiori.
    """
    proyectos = Proyecto.objects.all().select_related('responsable', 'ubicacion').prefetch_related('actividades')
    
    # KPIs
    total_proyectos = proyectos.count()
    proyectos_ejecucion = proyectos.filter(estado='EJECUCION').count()
    
    avances = [p.porcentaje_avance for p in proyectos]
    avance_promedio = sum(avances) / len(avances) if avances else 0
    
    # Alertas de proyectos que exceden su fecha fin
    hoy = datetime.now().date()
    proyectos_atrasados = proyectos.filter(
        estado__in=['PLANIFICACION', 'EJECUCION'],
        fecha_fin_estimada__lt=hoy
    ).count()

    context = {
        'proyectos': proyectos,
        'stats': {
            'total': total_proyectos,
            'ejecucion': proyectos_ejecucion,
            'avance_promedio': int(avance_promedio),
            'atrasados': proyectos_atrasados,
        }
    }
    return render(request, 'proyectos/dashboard_fiori.html', context)
@staff_member_required
def proyecto_detalle_fiori(request, pk):
    """
    Vista detallada (Object Page) de un proyecto.
    """
    proyecto = get_object_or_404(Proyecto, pk=pk)
    actividades = proyecto.actividades.all().order_by('orden')
    documentos = proyecto.documentos_proyecto.all().select_related('documento__tipo_documento')
    
    # Datos para los select de edición
    from activos.models import Ubicacion
    from django.contrib.auth.models import User
    
    # Formatear tareas para Gantt
    tasks = []
    for act in actividades:
        tasks.append({
            'id': str(act.id),
            'name': act.nombre,
            'start': act.fecha_inicio.isoformat() if act.fecha_inicio else (act.creado_en.date().isoformat()),
            'end': act.fecha_fin.isoformat() if act.fecha_fin else ((act.fecha_inicio or act.creado_en.date()) + timedelta(days=1)).isoformat(),
            'progress': act.porcentaje_avance,
            'dependencies': [str(act.predecesora.id)] if act.predecesora else [],
            'custom_class': f'gantt-item-{act.prioridad.lower()}'
        })

    # Agregar elementos del proyecto al Gantt (los que tienen fechas)
    for elem in proyecto.elementos.select_related('disciplina').filter(
        fecha_ejecucion_inicio__isnull=False
    ):
        progress = 100 if elem.estado == 'COMPLETADO' else (50 if elem.estado == 'EN_PROCESO' else 0)
        disc_name = elem.disciplina.nombre if elem.disciplina else ''
        prefix = f"[{disc_name}] " if disc_name else ""
        tasks.append({
            'id': f'elem-{elem.id}',
            'name': f'{prefix}{elem.nombre}',
            'start': elem.fecha_ejecucion_inicio.isoformat(),
            'end': (elem.fecha_ejecucion_fin or elem.fecha_ejecucion_inicio).isoformat(),
            'progress': progress,
            'dependencies': [],
            'custom_class': 'gantt-item-elemento'
        })

    from .models import ObservacionProyecto, PinObservacionProyecto
    from documentos.models import Disciplina
    observaciones = ObservacionProyecto.objects.filter(proyecto=proyecto).select_related(
        'usuario', 'documento_proyecto__documento'
    ).prefetch_related('pines_plano__plano').order_by('-fecha_observacion')
    estados_obs = ObservacionProyecto.ESTADOS

    context = {
        'proyecto': proyecto,
        'actividades': actividades,
        'documentos': documentos,
        'visores': proyecto.visores.all(),
        'ubicaciones': Ubicacion.objects.all(),
        'usuarios': User.objects.filter(is_active=True),
        'estados_proyecto': Proyecto.ESTADOS,
        'prioridades': Actividad.PRIORIDADES,
        'estados_actividad': Actividad.ESTADOS,
        'tasks_json': json.dumps(tasks),
        'observaciones': observaciones,
        'estados_obs': estados_obs,
        'cotizaciones': proyecto.cotizaciones.select_related(
            'disciplina', 'creado_por'
        ).prefetch_related('items').order_by('-creado_en'),
        'disciplinas': Disciplina.objects.all().order_by('nombre'),
    }
    return render(request, 'proyectos/proyecto_detalle_fiori.html', context)

@csrf_exempt
@staff_member_required
def update_actividades_bulk_api(request, pk):
    """
    Endpoint AJAX para actualizar múltiples actividades de un proyecto de una sola vez.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            actividades_data = data.get('actividades', [])
            
            for item in actividades_data:
                act_id = item.get('id')
                
                if act_id:
                    actividad = Actividad.objects.filter(pk=act_id, proyecto_id=pk).first()
                else:
                    # Crear nueva actividad si no hay ID
                    if not item.get('nombre'): continue
                    actividad = Actividad.objects.create(proyecto_id=pk, nombre=item.get('nombre'))
                
                if actividad:
                    # Campos permitidos
                    if 'nombre' in item: actividad.nombre = item['nombre']
                    if 'estado' in item: actividad.estado = item['estado']
                    if 'prioridad' in item: actividad.prioridad = item['prioridad']
                    if 'fecha_inicio' in item: actividad.fecha_inicio = item['fecha_inicio'] or None
                    if 'fecha_fin' in item: actividad.fecha_fin = item['fecha_fin'] or None
                    if 'porcentaje_avance' in item: actividad.porcentaje_avance = int(item['porcentaje_avance'] or 0)
                    if 'predecesora_id' in item:
                        pid = item['predecesora_id']
                        if pid and pid != str(actividad.id):
                            actividad.predecesora = Actividad.objects.filter(pk=pid).first()
                        else:
                            actividad.predecesora = None
                    if 'asignado_id' in item:
                        from django.contrib.auth.models import User
                        aid = item['asignado_id']
                        actividad.asignado_a = User.objects.filter(pk=aid).first() if aid else None
                    actividad.save()
            
            return JsonResponse({'status': 'success', 'message': 'Actividades actualizadas correctamente'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

@staff_member_required
def kanban_actividades_api(request, pk):
    """
    GET: Retorna actividades del proyecto agrupadas por estado para el tablero Kanban.
    Incluye lista de responsables que tienen actividades asignadas.
    """
    proyecto = get_object_or_404(Proyecto, pk=pk)
    actividades = proyecto.actividades.select_related('asignado_a').all()

    grupos = {
        'PENDIENTE': [],
        'EN_PROGRESO': [],
        'COMPLETADA': [],
        'BLOQUEADA': [],
    }

    for act in actividades:
        grupos[act.estado].append({
            'id': act.id,
            'nombre': act.nombre,
            'estado': act.estado,
            'prioridad': act.prioridad,
            'porcentaje_avance': act.porcentaje_avance,
            'fecha_inicio': act.fecha_inicio.isoformat() if act.fecha_inicio else None,
            'fecha_fin': act.fecha_fin.isoformat() if act.fecha_fin else None,
            'asignado_a_id': act.asignado_a_id,
            'asignado_a_nombre': (act.asignado_a.get_full_name() or act.asignado_a.username) if act.asignado_a else None,
            'creado_en': act.creado_en.isoformat(),
        })

    # Ordenar cada grupo: prioridad descendente, fecha de creación ascendente
    orden_prioridad = {'CRITICA': 0, 'ALTA': 1, 'MEDIA': 2, 'BAJA': 3}
    for estado, items in grupos.items():
        items.sort(key=lambda x: (orden_prioridad.get(x['prioridad'], 99), x['creado_en']))

    # Obtener responsables que tienen actividades asignadas
    from django.contrib.auth.models import User
    responsables_ids = actividades.values_list('asignado_a', flat=True).distinct()
    responsables = User.objects.filter(id__in=responsables_ids, is_active=True)

    return JsonResponse({
        'status': 'success',
        'actividades': grupos,
        'responsables': [
            {'id': u.id, 'nombre': u.get_full_name() or u.username}
            for u in responsables
        ]
    })


@csrf_exempt
@staff_member_required
def update_proyecto_api(request, pk):
    """
    Endpoint AJAX para actualizar metadata del proyecto.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            proyecto = get_object_or_404(Proyecto, pk=pk)
            
            # Mapeo de campos permitidos
            if 'nombre' in data: proyecto.nombre = data['nombre']
            if 'descripcion' in data: proyecto.descripcion = data['descripcion'] or ""
            if 'nota' in data: proyecto.nota = data['nota'] or ""
            if 'estado' in data: proyecto.estado = data['estado']
            if 'fecha_inicio' in data: proyecto.fecha_inicio = data['fecha_inicio'] or None
            if 'fecha_fin_estimada' in data: proyecto.fecha_fin_estimada = data['fecha_fin_estimada'] or None
            
            if 'responsable_id' in data:
                from django.contrib.auth.models import User
                rid = data.get('responsable_id')
                proyecto.responsable = User.objects.filter(pk=rid).first() if rid else None
            
            if 'ubicacion_id' in data:
                from activos.models import Ubicacion
                uid = data.get('ubicacion_id')
                proyecto.ubicacion = Ubicacion.objects.filter(pk=uid).first() if uid else None
                
            proyecto.save()
            return JsonResponse({'status': 'success', 'message': 'Proyecto actualizado correctamente'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)


@csrf_exempt
@staff_member_required
def delete_actividad_api(request, pk, act_id):
    """
    Endpoint AJAX para eliminar una actividad.
    """
    if request.method == 'DELETE' or request.method == 'POST':
        try:
            actividad = get_object_or_404(Actividad, pk=act_id, proyecto_id=pk)
            actividad.delete()
            return JsonResponse({'status': 'success', 'message': 'Actividad eliminada'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)


@staff_member_required
def activity_detail_api(request, actividad_id):
    """Retorna detalle de una actividad para editar en modal."""
    try:
        act = get_object_or_404(
            Actividad.objects.select_related('asignado_a', 'predecesora'),
            pk=actividad_id
        )
        ots = act.ordenes_trabajo.all().values('id', 'codigo_de_orden')
        data = {
            'id': act.id,
            'nombre': act.nombre,
            'descripcion': act.descripcion,
            'estado': act.estado,
            'prioridad': act.prioridad,
            'fecha_inicio': act.fecha_inicio.isoformat() if act.fecha_inicio else None,
            'fecha_fin': act.fecha_fin.isoformat() if act.fecha_fin else None,
            'porcentaje_avance': act.porcentaje_avance,
            'asignado_a_id': act.asignado_a_id,
            'asignado_a_nombre': act.asignado_a.get_full_name() or act.asignado_a.username if act.asignado_a else None,
            'predecesora_id': act.predecesora_id,
            'predecesora_nombre': act.predecesora.nombre if act.predecesora else None,
            'orden': act.orden,
            'ordenes_trabajo': list(ots),
        }
        return JsonResponse({'status': 'success', 'actividad': data})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
@staff_member_required
def upload_documento_proyecto_api(request, pk):
    """
    Endpoint para subir un documento y vincularlo al proyecto.
    Soporta carpeta opcional.
    """
    if request.method == 'POST':
        try:
            proyecto = get_object_or_404(Proyecto, pk=pk)
            archivo = request.FILES.get('file')
            carpeta_id = request.POST.get('carpeta_id')
            
            if not archivo:
                return JsonResponse({'status': 'error', 'message': 'No se recibió ningún archivo'}, status=400)
            
            carpeta = None
            if carpeta_id and carpeta_id != 'null':
                carpeta = Carpeta.objects.get(pk=carpeta_id, proyecto_id=proyecto.id)
            
            # 1. Crear Documento Maestro
            tipo_doc = TipoDocumento.objects.filter(nombre__icontains='Documento').first() or TipoDocumento.objects.first()
            disciplina = Disciplina.objects.first()
            
            from django.utils import timezone
            timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
            codigo_auto = f"AUTO-{pk}-{timestamp}"
            
            documento = Documento.objects.create(
                codigo=codigo_auto,
                titulo=os.path.splitext(archivo.name)[0],
                tipo_documento=tipo_doc,
                disciplina=disciplina,
                responsable=request.user,
                carpeta=carpeta  # Sincronización con el modelo maestro
            )
            
            # 2. Crear Revisión
            Revision.objects.create(
                documento=documento,
                revision='0',
                archivo=archivo,
                creado_por=request.user,
                comentarios='Carga automática desde proyecto'
            )
            
            # 3. Vincular al Proyecto (con Carpeta)
            DocumentoProyecto.objects.get_or_create(
                proyecto_id=proyecto.id,
                documento=documento,
                carpeta=carpeta,
                defaults={'nota': 'Cargado vía Drag & Drop'}
            )
            
            return JsonResponse({
                'status': 'success', 
                'message': 'Documento cargado y vinculado',
                'doc': {
                    'id': documento.id,
                    'codigo': documento.codigo,
                    'titulo': documento.titulo,
                    'url': documento.ultima_revision.archivo.url if documento.ultima_revision else ""
                }
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)


@staff_member_required
def link_ot_api(request, proyecto_pk):
    """Vincula una Orden de Trabajo existente al proyecto."""
    from mantenimiento.models import OrdenTrabajo
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
    try:
        data = json.loads(request.body)
        ot_id = data.get('ot_id')
        if not ot_id:
            return JsonResponse({'status': 'error', 'message': 'ot_id requerido'}, status=400)
        proyecto = get_object_or_404(Proyecto, pk=proyecto_pk)
        ot = get_object_or_404(OrdenTrabajo, pk=ot_id)
        ot.proyecto = proyecto
        ot.save(update_fields=['proyecto'])
        return JsonResponse({'status': 'success', 'codigo': ot.codigo_de_orden or f'OT #{ot.id}'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@staff_member_required
def link_requisicion_api(request, proyecto_pk):
    """Vincula una Requisicion existente al proyecto."""
    from presupuestos.models import Requisicion
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
    try:
        data = json.loads(request.body)
        req_id = data.get('requisicion_id')
        if not req_id:
            return JsonResponse({'status': 'error', 'message': 'requisicion_id requerido'}, status=400)
        proyecto = get_object_or_404(Proyecto, pk=proyecto_pk)
        req = get_object_or_404(Requisicion, pk=req_id)
        req.proyecto = proyecto
        req.save(update_fields=['proyecto'])
        return JsonResponse({'status': 'success', 'codigo': req.cr8ca_requisicion})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@staff_member_required
def reporte_proyecto(request, pk):
    """Reporte imprimible del proyecto."""
    from django.db import models
    proyecto = get_object_or_404(
        Proyecto.objects.select_related('responsable', 'ubicacion'),
        pk=pk
    )
    actividades = proyecto.actividades.all().order_by('orden', 'fecha_inicio')
    ordenes = proyecto.ordenes_trabajo.all().select_related('tecnico').prefetch_related('archivos')
    requisiciones = proyecto.requisiciones.all()

    total_requisiciones = requisiciones.aggregate(
        total=models.Sum('cr8ca_totalenarticulos')
    )['total'] or 0

    estados_act = {}
    for act in actividades:
        estados_act[act.estado] = estados_act.get(act.estado, 0) + 1

    min_date = None
    max_date = None
    for act in actividades:
        if act.fecha_inicio and (min_date is None or act.fecha_inicio < min_date):
            min_date = act.fecha_inicio
        if act.fecha_fin and (max_date is None or act.fecha_fin > max_date):
            max_date = act.fecha_fin

    # Gantt computation — TIEMPO ACORDADO style
    gantt_total_days = 1
    gantt_markers = []
    if min_date and max_date:
        delta = max_date - min_date
        gantt_total_days = max(delta.days, 1)

        if gantt_total_days <= 14: step = 1
        elif gantt_total_days <= 60: step = 7
        elif gantt_total_days <= 180: step = 14
        elif gantt_total_days <= 365: step = 30
        else: step = 60

        curr = 0
        while curr <= gantt_total_days:
            gantt_markers.append(curr)
            curr += step
        if gantt_markers and gantt_markers[-1] < gantt_total_days:
            gantt_markers.append(gantt_markers[-1] + step)

    for act in actividades:
        if act.fecha_inicio and act.fecha_fin and min_date and max_date:
            total_sec = (max_date - min_date).total_seconds()
            if total_sec <= 0:
                total_sec = 86400
            act_left = max((act.fecha_inicio - min_date).total_seconds(), 0)
            act_width = (act.fecha_fin - act.fecha_inicio).total_seconds()
            act.gantt_left_pct = act_left / total_sec * 100
            act.gantt_width_pct = max(act_width / total_sec * 100, 0.3)
        else:
            act.gantt_left_pct = 0
            act.gantt_width_pct = 0

    context = {
        'proyecto': proyecto,
        'actividades': actividades,
        'ordenes': ordenes,
        'requisiciones': requisiciones,
        'total_requisiciones': total_requisiciones,
        'estados_act': estados_act,
        'min_date': min_date,
        'max_date': max_date,
        'gantt_total_days': gantt_total_days,
        'gantt_markers': gantt_markers,
    }
    return render(request, 'proyectos/reporte_proyecto.html', context)


@staff_member_required
def reporte_observaciones(request, pk):
    proyecto = get_object_or_404(Proyecto, pk=pk)
    observaciones = ObservacionProyecto.objects.filter(proyecto=proyecto).select_related(
        'usuario', 'documento_proyecto__documento'
    ).order_by('-fecha_observacion')
    return render(request, 'proyectos/reporte_observaciones.html', {
        'proyecto': proyecto,
        'observaciones': observaciones,
    })


@csrf_exempt
@staff_member_required
def crear_observacion_api(request, proyecto_pk):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    try:
        data = json.loads(request.body)
        proyecto = get_object_or_404(Proyecto, pk=proyecto_pk)
        doc_proy = None
        if data.get('documento_proyecto_id'):
            doc_proy = get_object_or_404(DocumentoProyecto, pk=data['documento_proyecto_id'], proyecto=proyecto)
        obs = ObservacionProyecto.objects.create(
            proyecto=proyecto,
            documento_proyecto=doc_proy,
            usuario=request.user,
            observacion=data['observacion'],
            estado=data.get('estado', 'ABIERTA'),
            fecha_observacion=datetime.strptime(data['fecha_observacion'], '%Y-%m-%d').date(),
            fecha_resolucion=datetime.strptime(data['fecha_resolucion'], '%Y-%m-%d').date() if data.get('fecha_resolucion') else None,
        )
        return JsonResponse({'status': 'success', 'id': obs.id})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@csrf_exempt
@staff_member_required
def actualizar_observacion_api(request, proyecto_pk, obs_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    try:
        data = json.loads(request.body)
        obs = get_object_or_404(ObservacionProyecto, pk=obs_id, proyecto_id=proyecto_pk)
        if 'observacion' in data:
            obs.observacion = data['observacion']
        if 'estado' in data:
            obs.estado = data['estado']
        if 'fecha_observacion' in data:
            obs.fecha_observacion = datetime.strptime(data['fecha_observacion'], '%Y-%m-%d').date()
        if 'fecha_resolucion' in data:
            obs.fecha_resolucion = datetime.strptime(data['fecha_resolucion'], '%Y-%m-%d').date() if data['fecha_resolucion'] else None
        if 'documento_proyecto_id' in data:
            obs.documento_proyecto = get_object_or_404(DocumentoProyecto, pk=data['documento_proyecto_id'], proyecto_id=proyecto_pk)
        obs.save()
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@staff_member_required
def detalle_observacion_api(request, proyecto_pk, obs_id):
    obs = get_object_or_404(ObservacionProyecto, pk=obs_id, proyecto_id=proyecto_pk)
    return JsonResponse({
        'id': obs.id,
        'documento_proyecto_id': obs.documento_proyecto_id,
        'documento_codigo': obs.documento_proyecto.documento.codigo,
        'documento_titulo': obs.documento_proyecto.documento.titulo,
        'observacion': obs.observacion,
        'estado': obs.estado,
        'fecha_observacion': obs.fecha_observacion.isoformat(),
        'fecha_resolucion': obs.fecha_resolucion.isoformat() if obs.fecha_resolucion else None,
        'usuario': obs.usuario.get_full_name() or obs.usuario.username,
    })


@csrf_exempt
@staff_member_required
def eliminar_observacion_api(request, proyecto_pk, obs_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    try:
        obs = get_object_or_404(ObservacionProyecto, pk=obs_id, proyecto_id=proyecto_pk)
        obs.delete()
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


# ============================================================
# Endpoints API de Planos PDF
# ============================================================

@csrf_exempt
@staff_member_required
def listar_planos_api(request, pk):
    """
    GET: Retorna lista paginada de planos PDF asociados al proyecto.
    """
    if request.method != 'GET':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

    proyecto = get_object_or_404(Proyecto, pk=pk)
    planos_qs = proyecto.planos_pdf.select_related('subido_por').all()

    page_number = request.GET.get('page', 1)
    paginator = Paginator(planos_qs, 20)
    page_obj = paginator.get_page(page_number)

    planos_data = []
    for plano in page_obj:
        usuario_nombre = ''
        if plano.subido_por:
            usuario_nombre = plano.subido_por.get_full_name() or plano.subido_por.username
        planos_data.append({
            'id': plano.id,
            'titulo': plano.titulo,
            'descripcion': plano.descripcion,
            'fecha_carga': plano.fecha_carga.isoformat(),
            'usuario_nombre': usuario_nombre,
            'url_archivo': reverse('proyectos:download_plano', kwargs={'pk': pk, 'plano_id': plano.id}),
        })

    return JsonResponse({
        'status': 'success',
        'data': {
            'planos': planos_data,
            'total': paginator.count,
            'page': page_obj.number,
            'total_pages': paginator.num_pages,
        }
    })


@csrf_exempt
@staff_member_required
def upload_plano_api(request, pk):
    """
    POST: Sube un plano PDF y lo asocia al proyecto.
    Acepta multipart/form-data con campos: archivo, titulo, descripcion.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

    proyecto = get_object_or_404(Proyecto, pk=pk)

    # Validar archivo
    archivo = request.FILES.get('archivo')
    if not archivo:
        return JsonResponse({'status': 'error', 'message': 'No se recibió ningún archivo'}, status=400)

    # Validar extensión .pdf
    nombre_archivo = archivo.name.lower()
    if not nombre_archivo.endswith('.pdf'):
        return JsonResponse({'status': 'error', 'message': 'Solo se aceptan archivos PDF'}, status=400)

    # Validar content-type
    if archivo.content_type != 'application/pdf':
        return JsonResponse({'status': 'error', 'message': 'Solo se aceptan archivos PDF'}, status=400)

    # Validar tamaño (50 MB máximo)
    max_size = 50 * 1024 * 1024
    if archivo.size > max_size:
        return JsonResponse({'status': 'error', 'message': 'El archivo excede el tamaño máximo permitido (50 MB)'}, status=400)

    # Validar título
    titulo = request.POST.get('titulo', '').strip()
    if not titulo or len(titulo) > 200:
        return JsonResponse({'status': 'error', 'message': 'El título es obligatorio (máx. 200 caracteres)'}, status=400)

    # Validar descripción
    descripcion = request.POST.get('descripcion', '').strip()
    if len(descripcion) > 500:
        return JsonResponse({'status': 'error', 'message': 'La descripción no puede exceder 500 caracteres'}, status=400)

    # Crear registro
    try:
        plano = PlanoProyecto.objects.create(
            proyecto=proyecto,
            titulo=titulo,
            descripcion=descripcion,
            archivo=archivo,
            subido_por=request.user,
        )
        return JsonResponse({
            'status': 'success',
            'message': 'Plano cargado exitosamente',
            'data': {
                'id': plano.id,
                'titulo': plano.titulo,
                'fecha_carga': plano.fecha_carga.isoformat(),
            }
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': 'Error al almacenar el archivo. Intente nuevamente.'}, status=500)


@csrf_exempt
@staff_member_required
def delete_plano_api(request, pk, plano_id):
    """
    DELETE o POST: Elimina un plano PDF del proyecto.
    La señal post_delete se encarga de eliminar el archivo de MinIO.
    """
    if request.method not in ('DELETE', 'POST'):
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

    proyecto = get_object_or_404(Proyecto, pk=pk)
    plano = get_object_or_404(PlanoProyecto, pk=plano_id, proyecto_id=proyecto.id)

    try:
        plano.delete()
        return JsonResponse({'status': 'success', 'message': 'Plano eliminado exitosamente'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': 'Error al eliminar el archivo. El plano no fue modificado.'}, status=500)


@staff_member_required
def download_plano(request, pk, plano_id):
    """
    GET: Descarga el archivo PDF del plano.
    Retorna FileResponse con Content-Disposition attachment.
    """
    proyecto = get_object_or_404(Proyecto, pk=pk)
    plano = get_object_or_404(PlanoProyecto, pk=plano_id, proyecto_id=proyecto.id)

    # Verificar que el archivo existe en storage
    if not plano.archivo or not plano.archivo.storage.exists(plano.archivo.name):
        return JsonResponse({'status': 'error', 'message': 'El archivo no se encuentra disponible'}, status=404)

    try:
        response = FileResponse(plano.archivo.open('rb'), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{plano.titulo}.pdf"'
        return response
    except Exception:
        return JsonResponse({'status': 'error', 'message': 'El archivo no se encuentra disponible'}, status=404)


@staff_member_required
def visor_plano_proyecto(request, pk, plano_id):
    """
    GET: Renderiza el visor de PDF standalone para un plano del proyecto.
    Inyecta pines existentes y observaciones disponibles como JSON en el contexto.
    """
    proyecto = get_object_or_404(Proyecto, pk=pk)
    plano = get_object_or_404(PlanoProyecto, pk=plano_id, proyecto_id=proyecto.id)

    # Verificar si el archivo existe
    archivo_disponible = True
    pdf_url = ''
    try:
        if plano.archivo and plano.archivo.storage.exists(plano.archivo.name):
            pdf_url = plano.archivo.url
        else:
            archivo_disponible = False
    except Exception:
        archivo_disponible = False

    # Consultar pines del plano actual con datos de observación y usuario
    pines = PinObservacionProyecto.objects.filter(plano=plano).select_related(
        'observacion', 'observacion__usuario'
    ).prefetch_related('fotos')

    # Serializar pines a lista de dicts
    pines_data = []
    for pin in pines:
        obs = pin.observacion
        pines_data.append({
            'id': pin.id,
            'x': pin.coordenada_x,
            'y': pin.coordenada_y,
            'pagina': pin.pagina,
            'color': pin.color,
            'nota': pin.nota,
            'observacion_id': obs.id,
            'observacion_texto': obs.observacion,
            'observacion_estado': obs.estado,
            'observacion_usuario': obs.usuario.get_full_name() or obs.usuario.username,
            'observacion_fecha': obs.fecha_observacion.isoformat() if obs.fecha_observacion else '',
            'fotos': [{'id': f.id, 'url': f.imagen.url} for f in pin.fotos.all()],
        })

    # Consultar observaciones del proyecto NO vinculadas al plano actual
    observaciones_disponibles_qs = ObservacionProyecto.objects.filter(
        proyecto=proyecto
    ).exclude(
        id__in=pines.values_list('observacion_id', flat=True)
    )

    # Serializar observaciones disponibles
    observaciones_disponibles_data = []
    for obs in observaciones_disponibles_qs:
        observaciones_disponibles_data.append({
            'id': obs.id,
            'texto': obs.observacion[:100],
            'estado': obs.estado,
        })

    # Consultar áreas del plano
    areas_qs = AreaPlanoProyecto.objects.filter(plano=plano)
    areas_data = []
    for area in areas_qs:
        areas_data.append({
            'id': area.id,
            'nombre': area.nombre,
            'color': area.color,
            'x1': area.x1,
            'y1': area.y1,
            'x2': area.x2,
            'y2': area.y2,
            'pagina': area.pagina,
        })

    return render(request, 'proyectos/visor_plano_proyecto.html', {
        'plano': plano,
        'proyecto': proyecto,
        'pdf_url': pdf_url,
        'archivo_disponible': archivo_disponible,
        'pines_json': json.dumps(pines_data, ensure_ascii=False),
        'observaciones_disponibles_json': json.dumps(observaciones_disponibles_data, ensure_ascii=False),
        'areas_json': json.dumps(areas_data, ensure_ascii=False),
    })


@staff_member_required
def visor_plano_proyecto_mobile(request, pk, plano_id):
    """Visor de plano PDF optimizado para móvil con pines interactivos."""
    proyecto = get_object_or_404(Proyecto, pk=pk)
    plano = get_object_or_404(PlanoProyecto, pk=plano_id, proyecto_id=proyecto.id)

    archivo_disponible = True
    pdf_url = ''
    try:
        if plano.archivo and plano.archivo.storage.exists(plano.archivo.name):
            pdf_url = plano.archivo.url
        else:
            archivo_disponible = False
    except Exception:
        archivo_disponible = False

    pines = PinObservacionProyecto.objects.filter(plano=plano).select_related(
        'observacion', 'observacion__usuario'
    ).prefetch_related('fotos')

    pines_data = []
    for pin in pines:
        obs = pin.observacion
        pines_data.append({
            'id': pin.id,
            'x': pin.coordenada_x,
            'y': pin.coordenada_y,
            'pagina': pin.pagina,
            'color': pin.color,
            'nota': pin.nota,
            'observacion_id': obs.id,
            'observacion_texto': obs.observacion,
            'observacion_estado': obs.estado,
            'observacion_usuario': obs.usuario.get_full_name() or obs.usuario.username,
            'observacion_fecha': obs.fecha_observacion.isoformat() if obs.fecha_observacion else '',
            'fotos': [{'id': f.id, 'url': f.imagen.url} for f in pin.fotos.all()],
        })

    return render(request, 'proyectos/visor_plano_mobile.html', {
        'plano': plano,
        'proyecto': proyecto,
        'pdf_url': pdf_url,
        'archivo_disponible': archivo_disponible,
        'pines_json': json.dumps(pines_data, ensure_ascii=False),
    })


@csrf_exempt
@staff_member_required
def listar_pines_plano_api(request, pk, plano_id):
    """
    GET: Retorna la lista de pines de observación de un plano en formato JSON.
    """
    if request.method != 'GET':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

    proyecto = get_object_or_404(Proyecto, pk=pk)
    plano = get_object_or_404(PlanoProyecto, pk=plano_id)

    # Validar que el plano pertenece al proyecto
    if plano.proyecto_id != proyecto.id:
        return JsonResponse({'status': 'error', 'message': 'El plano no pertenece a este proyecto.'}, status=404)

    pines = PinObservacionProyecto.objects.filter(plano=plano).select_related(
        'observacion', 'observacion__usuario'
    )

    pines_data = []
    for pin in pines:
        obs = pin.observacion
        observacion_usuario = ''
        if obs.usuario:
            observacion_usuario = obs.usuario.get_full_name() or obs.usuario.username

        pines_data.append({
            'id': pin.id,
            'x': pin.coordenada_x,
            'y': pin.coordenada_y,
            'pagina': pin.pagina,
            'color': pin.color,
            'nota': pin.nota,
            'observacion_id': obs.id,
            'observacion_texto': obs.observacion[:80] if obs.observacion else '',
            'observacion_estado': obs.estado,
            'observacion_usuario': observacion_usuario,
            'observacion_fecha': obs.fecha_observacion.isoformat() if obs.fecha_observacion else '',
        })

    return JsonResponse({'status': 'success', 'pines': pines_data})


@csrf_exempt
@staff_member_required
def crear_pin_plano_api(request, pk, plano_id):
    """
    POST: Crea un pin de observación vinculado a un plano del proyecto.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

    proyecto = get_object_or_404(Proyecto, pk=pk)
    plano = get_object_or_404(PlanoProyecto, pk=plano_id, proyecto_id=proyecto.id)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'status': 'error', 'message': 'JSON inválido.'}, status=400)

    x = data.get('x')
    y = data.get('y')
    pagina = data.get('pagina', 1)
    observacion_id = data.get('observacion_id')
    color = data.get('color', '#EF4444')
    nota = data.get('nota', '')

    # Validar que la observación existe
    try:
        observacion = ObservacionProyecto.objects.get(pk=observacion_id)
    except ObservacionProyecto.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Observación no encontrada.'}, status=400)

    # Validar que la observación pertenece al mismo proyecto que el plano
    if observacion.proyecto_id != proyecto.id:
        return JsonResponse({'status': 'error', 'message': 'La observación no pertenece a este proyecto.'}, status=400)

    # Crear el pin, manejando la restricción de unicidad
    try:
        pin = PinObservacionProyecto.objects.create(
            plano=plano,
            observacion=observacion,
            coordenada_x=x,
            coordenada_y=y,
            pagina=pagina,
            color=color,
            nota=nota,
        )
    except IntegrityError:
        return JsonResponse({'status': 'error', 'message': 'Esta observación ya está vinculada a este plano.'}, status=400)

    return JsonResponse({
        'status': 'success',
        'pin': {
            'id': pin.id,
            'x': pin.coordenada_x,
            'y': pin.coordenada_y,
            'pagina': pin.pagina,
            'color': pin.color,
            'nota': pin.nota,
            'observacion_id': observacion.id,
            'observacion_texto': observacion.observacion[:80] if observacion.observacion else '',
            'observacion_estado': observacion.estado,
        }
    })


@csrf_exempt
@staff_member_required
def eliminar_pin_plano_api(request, pk, plano_id, pin_id):
    """
    POST: Elimina un pin de observación de un plano.
    Solo elimina el registro PinObservacionProyecto, NO la observación vinculada.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

    proyecto = get_object_or_404(Proyecto, pk=pk)
    plano = get_object_or_404(PlanoProyecto, pk=plano_id, proyecto_id=proyecto.id)
    pin = get_object_or_404(PinObservacionProyecto, pk=pin_id, plano=plano)

    pin.delete()
    return JsonResponse({'status': 'success'})


@csrf_exempt
@staff_member_required
def mover_pin_plano_api(request, pk, plano_id, pin_id):
    """
    POST: Mueve un pin a nuevas coordenadas (x, y) en el plano.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

    proyecto = get_object_or_404(Proyecto, pk=pk)
    plano = get_object_or_404(PlanoProyecto, pk=plano_id, proyecto_id=proyecto.id)
    pin = get_object_or_404(PinObservacionProyecto, pk=pin_id, plano=plano)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'status': 'error', 'message': 'JSON inválido.'}, status=400)

    x = data.get('x')
    y = data.get('y')

    if x is None or y is None:
        return JsonResponse({'status': 'error', 'message': 'Coordenadas x, y son requeridas.'}, status=400)

    pin.coordenada_x = float(x)
    pin.coordenada_y = float(y)
    pin.save(update_fields=['coordenada_x', 'coordenada_y'])

    return JsonResponse({'status': 'success', 'x': pin.coordenada_x, 'y': pin.coordenada_y})


@csrf_exempt
@staff_member_required
def subir_fotos_pin_api(request, pk, plano_id, pin_id):
    """
    POST multipart/form-data: Sube una o más fotos a un pin existente.
    Campo de archivos: 'fotos' (múltiple). Máximo 5 fotos por pin.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

    proyecto = get_object_or_404(Proyecto, pk=pk)
    plano = get_object_or_404(PlanoProyecto, pk=plano_id, proyecto_id=proyecto.id)
    pin = get_object_or_404(PinObservacionProyecto, pk=pin_id, plano=plano)

    archivos = request.FILES.getlist('fotos')
    if not archivos:
        return JsonResponse({'status': 'error', 'message': 'No se enviaron archivos.'}, status=400)

    # Validar límite de 5 fotos
    fotos_actuales = pin.fotos.count()
    if fotos_actuales + len(archivos) > 5:
        disponibles = 5 - fotos_actuales
        return JsonResponse({
            'status': 'error',
            'message': f'Solo puede agregar {disponibles} foto(s) más. El pin ya tiene {fotos_actuales}.'
        }, status=400)

    # Validar MIME de cada archivo
    MIMES_VALIDOS = {'image/jpeg', 'image/png'}
    for archivo in archivos:
        if archivo.content_type not in MIMES_VALIDOS:
            return JsonResponse({
                'status': 'error',
                'message': 'Solo se permiten archivos JPG o PNG.'
            }, status=400)

    # Guardar fotos
    fotos_creadas = []
    for archivo in archivos:
        foto = FotoPinObservacion(pin=pin, imagen=archivo)
        foto.save()
        fotos_creadas.append({'id': foto.id, 'url': foto.imagen.url})

    return JsonResponse({'status': 'success', 'fotos': fotos_creadas})


@csrf_exempt
@staff_member_required
def eliminar_foto_pin_api(request, pk, plano_id, pin_id, foto_id):
    """
    POST: Elimina una foto específica de un pin de observación.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

    proyecto = get_object_or_404(Proyecto, pk=pk)
    plano = get_object_or_404(PlanoProyecto, pk=plano_id, proyecto_id=proyecto.id)
    pin = get_object_or_404(PinObservacionProyecto, pk=pin_id, plano=plano)
    foto = get_object_or_404(FotoPinObservacion, pk=foto_id, pin=pin)

    foto.delete()
    return JsonResponse({'status': 'success'})


# ─── Áreas de Plano ─────────────────────────────────────────────────────────────

@csrf_exempt
@staff_member_required
def crear_area_plano_api(request, pk, plano_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
    proyecto = get_object_or_404(Proyecto, pk=pk)
    plano = get_object_or_404(PlanoProyecto, pk=plano_id, proyecto_id=proyecto.id)
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'status': 'error', 'message': 'JSON inválido.'}, status=400)

    xa, ya = float(data.get('x1', 0)), float(data.get('y1', 0))
    xb, yb = float(data.get('x2', 0)), float(data.get('y2', 0))
    x1, x2 = min(xa, xb), max(xa, xb)
    y1, y2 = min(ya, yb), max(ya, yb)

    if (x2 - x1) < 10 or (y2 - y1) < 10:
        return JsonResponse({'status': 'error', 'message': 'El área es demasiado pequeña (mínimo 10x10 píxeles).'}, status=400)

    nombre = (data.get('nombre') or '').strip()
    if not nombre:
        return JsonResponse({'status': 'error', 'message': 'El nombre del área es obligatorio.'}, status=400)

    color = data.get('color', '#3B82F6')
    pagina = int(data.get('pagina', 1))

    area = AreaPlanoProyecto.objects.create(
        plano=plano, nombre=nombre, color=color,
        x1=x1, y1=y1, x2=x2, y2=y2, pagina=pagina
    )
    return JsonResponse({'status': 'success', 'area': {
        'id': area.id, 'nombre': area.nombre, 'color': area.color,
        'x1': area.x1, 'y1': area.y1, 'x2': area.x2, 'y2': area.y2, 'pagina': area.pagina
    }})


@csrf_exempt
@staff_member_required
def editar_area_plano_api(request, pk, plano_id, area_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
    proyecto = get_object_or_404(Proyecto, pk=pk)
    plano = get_object_or_404(PlanoProyecto, pk=plano_id, proyecto_id=proyecto.id)
    area = get_object_or_404(AreaPlanoProyecto, pk=area_id, plano=plano)
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'status': 'error', 'message': 'JSON inválido.'}, status=400)

    update_fields = []

    # Update name/color if provided
    nombre = (data.get('nombre') or '').strip()
    if nombre:
        area.nombre = nombre
        update_fields.append('nombre')
    elif 'nombre' in data:
        return JsonResponse({'status': 'error', 'message': 'El nombre del área es obligatorio.'}, status=400)

    if 'color' in data:
        area.color = data['color']
        update_fields.append('color')

    # Update coordinates if provided (for move/resize)
    if 'x1' in data and 'y1' in data and 'x2' in data and 'y2' in data:
        area.x1 = float(data['x1'])
        area.y1 = float(data['y1'])
        area.x2 = float(data['x2'])
        area.y2 = float(data['y2'])
        update_fields.extend(['x1', 'y1', 'x2', 'y2'])

    if not update_fields:
        return JsonResponse({'status': 'error', 'message': 'No se proporcionaron campos para actualizar.'}, status=400)

    area.save(update_fields=update_fields)
    return JsonResponse({'status': 'success', 'area': {
        'id': area.id, 'nombre': area.nombre, 'color': area.color,
        'x1': area.x1, 'y1': area.y1, 'x2': area.x2, 'y2': area.y2, 'pagina': area.pagina
    }})


@csrf_exempt
@staff_member_required
def eliminar_area_plano_api(request, pk, plano_id, area_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
    proyecto = get_object_or_404(Proyecto, pk=pk)
    plano = get_object_or_404(PlanoProyecto, pk=plano_id, proyecto_id=proyecto.id)
    area = get_object_or_404(AreaPlanoProyecto, pk=area_id, plano=plano)
    area.delete()
    return JsonResponse({'status': 'success'})


@staff_member_required
def api_elementos_lista(request, pk):
    """Lista los elementos del proyecto."""
    proyecto = get_object_or_404(Proyecto, pk=pk)
    elementos = proyecto.elementos.select_related('item_cotizacion__cotizacion', 'disciplina').prefetch_related('documentos').order_by('disciplina__nombre', 'area', 'orden')
    data = []
    for e in elementos:
        docs = [{'id': d.id, 'url': d.archivo.url, 'descripcion': d.descripcion, 'tipo': d.tipo} for d in e.documentos.all()]
        data.append({
            'id': e.id,
            'nombre': e.nombre,
            'descripcion': e.descripcion,
            'estado': e.estado,
            'disciplina': e.disciplina.nombre if e.disciplina else None,
            'disciplina_id': e.disciplina_id,
            'area': e.area or '',
            'unidad_medida': e.unidad_medida or '',
            'precio_unitario': float(e.precio_unitario),
            'total': float(e.total),
            'fecha_inicio': e.fecha_ejecucion_inicio.isoformat() if e.fecha_ejecucion_inicio else None,
            'fecha_fin': e.fecha_ejecucion_fin.isoformat() if e.fecha_ejecucion_fin else None,
            'cantidad': float(e.cantidad),
            'orden': e.orden,
            'item_cotizacion_id': e.item_cotizacion_id,
            'item_descripcion': str(e.item_cotizacion) if e.item_cotizacion else None,
            'cotizacion_numero': e.item_cotizacion.cotizacion.numero if e.item_cotizacion and e.item_cotizacion.cotizacion else None,
            'documentos': docs,
        })
    return JsonResponse(data, safe=False)


@staff_member_required
@require_POST
def api_elemento_crear(request, pk):
    """Crea un elemento manualmente o desde item de cotización."""
    import json
    proyecto = get_object_or_404(Proyecto, pk=pk)
    data = json.loads(request.body)
    item_id = data.get('item_cotizacion_id')

    if item_id:
        from presupuestos.models import ItemCotizacion
        item = get_object_or_404(ItemCotizacion, pk=item_id)
        nombre = data.get('nombre') or item.descripcion[:300]
        elemento = ElementoProyecto.objects.create(
            proyecto=proyecto,
            item_cotizacion=item,
            nombre=nombre,
            descripcion=data.get('descripcion', ''),
            cantidad=float(data.get('cantidad', item.cantidad)),
            estado='PENDIENTE',
            orden=proyecto.elementos.count() + 1,
        )
    else:
        elemento = ElementoProyecto.objects.create(
            proyecto=proyecto,
            nombre=data['nombre'],
            descripcion=data.get('descripcion', ''),
            cantidad=float(data.get('cantidad', 1)),
            fecha_ejecucion_inicio=data.get('fecha_inicio') or None,
            fecha_ejecucion_fin=data.get('fecha_fin') or None,
            estado='PENDIENTE',
            orden=proyecto.elementos.count() + 1,
        )
    return JsonResponse({'ok': True, 'id': elemento.id})


@staff_member_required
@require_POST
def api_elemento_actualizar(request, pk, elemento_id):
    """Actualiza un elemento del proyecto."""
    import json
    elemento = get_object_or_404(ElementoProyecto, pk=elemento_id, proyecto_id=pk)
    data = json.loads(request.body)
    if 'nombre' in data:
        elemento.nombre = data['nombre']
    if 'descripcion' in data:
        elemento.descripcion = data['descripcion']
    if 'estado' in data and data['estado'] in dict(ElementoProyecto.ESTADOS):
        elemento.estado = data['estado']
    if 'fecha_inicio' in data:
        elemento.fecha_ejecucion_inicio = data['fecha_inicio'] or None
    if 'fecha_fin' in data:
        elemento.fecha_ejecucion_fin = data['fecha_fin'] or None
    if 'cantidad' in data:
        elemento.cantidad = float(data['cantidad'])
    elemento.save()
    return JsonResponse({'ok': True})


@staff_member_required
@require_POST
def api_elemento_eliminar(request, pk, elemento_id):
    """Elimina un elemento del proyecto."""
    elemento = get_object_or_404(ElementoProyecto, pk=elemento_id, proyecto_id=pk)
    elemento.delete()
    return JsonResponse({'ok': True})


@staff_member_required
def api_elemento_documentos(request, pk, elemento_id):
    """Lista documentos de un elemento."""
    elemento = get_object_or_404(ElementoProyecto, pk=elemento_id, proyecto_id=pk)
    docs = [{
        'id': d.id,
        'url': d.archivo.url,
        'descripcion': d.descripcion,
        'tipo': d.tipo,
        'creado_en': d.creado_en.isoformat(),
    } for d in elemento.documentos.all()]
    return JsonResponse(docs, safe=False)


@staff_member_required
@require_POST
def api_elemento_subir_documento(request, pk, elemento_id):
    """Sube un documento/foto a un elemento."""
    elemento = get_object_or_404(ElementoProyecto, pk=elemento_id, proyecto_id=pk)
    archivo = request.FILES.get('archivo') or request.FILES.get('foto')
    if not archivo:
        return JsonResponse({'error': 'No se recibió archivo'}, status=400)
    doc = ElementoDocumento.objects.create(
        elemento=elemento,
        archivo=archivo,
        descripcion=request.POST.get('descripcion', ''),
        tipo=request.POST.get('tipo', 'FOTO'),
        subido_por=request.user,
    )
    return JsonResponse({'ok': True, 'id': doc.id, 'url': doc.archivo.url})


@staff_member_required
@require_POST
def api_elemento_eliminar_documento(request, pk, elemento_id, doc_id):
    """Elimina un documento de un elemento."""
    doc = get_object_or_404(ElementoDocumento, pk=doc_id, elemento_id=elemento_id, elemento__proyecto_id=pk)
    doc.delete()
    return JsonResponse({'ok': True})
