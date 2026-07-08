from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django import forms
from .models import Actividad, Proyecto, DocumentoProyecto, ObservacionProyecto
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
                estado='PENDIENTE',
                orden=orden,
                asignado_a=request.user,
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
            if not pregunta:
                return JsonResponse({'status': 'error', 'message': 'Mensaje vacío'}, status=400)
            
            respuesta = ask_gemini(pregunta)
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

    from .models import ObservacionProyecto
    observaciones = ObservacionProyecto.objects.filter(proyecto=proyecto).select_related(
        'usuario', 'documento_proyecto__documento'
    ).order_by('-fecha_observacion')
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
