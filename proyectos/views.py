from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.admin.views.decorators import staff_member_required
from .models import Actividad, Proyecto, DocumentoProyecto
from documentos.models import Documento
import json
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
                actividad.fecha_inicio = data.get('fecha_inicio')
            if 'fecha_fin' in data:
                actividad.fecha_fin = data.get('fecha_fin')
            if 'nombre' in data:
                actividad.nombre = data.get('nombre')
            if 'estado' in data:
                actividad.estado = data.get('estado')
            if 'predecesora_id' in data:
                pid = data.get('predecesora_id')
                actividad.predecesora = Actividad.objects.filter(pk=pid).first() if pid else None
                
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
    
    context = {
        'proyecto': proyecto,
        'documentos': documentos,
        'estados': Documento.ESTADOS,
    }
    return render(request, 'proyectos/repositorio_documentos.html', context)
