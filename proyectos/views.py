from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.admin.views.decorators import staff_member_required
from .models import Actividad, Proyecto
import json
from datetime import datetime, timedelta

@csrf_exempt
@staff_member_required
def crear_actividad_api(request):
    # ... (existing code remains same)
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            nombre = data.get('nombre')
            proyecto_id = data.get('proyecto_id')
            prioridad = data.get('prioridad', 'MEDIA')
            
            if not nombre or not proyecto_id:
                return JsonResponse({'status': 'error', 'message': 'Faltan datos obligatorios'}, status=400)
            
            proyecto = Proyecto.objects.get(pk=proyecto_id)
            
            ultimo_orden = Actividad.objects.filter(proyecto=proyecto).order_by('-orden').first()
            orden = (ultimo_orden.orden + 1) if ultimo_orden else 1
            
            actividad = Actividad.objects.create(
                proyecto=proyecto,
                nombre=nombre,
                prioridad=prioridad,
                estado='PENDIENTE',
                orden=orden,
                asignado_a=request.user
            )
            
            return JsonResponse({
                'status': 'success',
                'actividad': {
                    'id': actividad.id,
                    'nombre': actividad.nombre,
                    'color': actividad.color,
                    'estado': actividad.get_estado_display(),
                    'proyecto_codigo': proyecto.codigo
                }
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

@staff_member_required
def cronograma_proyecto(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    actividades = proyecto.actividades.all().order_by('orden', 'fecha_inicio')
    
    # Determinar rango de semanas (Año actual por defecto)
    year = int(request.GET.get('year', datetime.now().year))
    
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
