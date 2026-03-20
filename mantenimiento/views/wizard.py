import json
from datetime import datetime
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from ..models import Rutina, Horario, Programacion
from activos.models import Ubicacion, Categoria as CategoriaActivo

@staff_member_required
def programar_rutina_wizard(request):
    rutina_id = request.GET.get('rutina')
    rutina = get_object_or_404(Rutina, id=rutina_id) if rutina_id else None
    today = timezone.now().date()
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            prog = Programacion.objects.create(
                rutina_id=data['rutina_id'],
                horario_id=data['horario_id'],
                fecha_inicio=datetime.strptime(data['fecha_inicio'], '%Y-%m-%d').date(),
                fecha_fin=datetime.strptime(data['fecha_fin'], '%Y-%m-%d').date() if data.get('fecha_fin') else None,
                procesada=False
            )
            if data.get('areas'): prog.areas.set(data['areas'])
            if data.get('activos'): prog.activos.set(data['activos'])
            
            if data.get('solo_proyeccion'):
                return JsonResponse({'status': 'projection', 'prog_id': prog.id, 'message': 'P proyectada.'})
            
            count = prog.generar_ordenes()
            return JsonResponse({'status': 'success', 'prog_id': prog.id, 'count': count, 'message': f'Se generaron {count} órdenes.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    horarios = Horario.objects.all().prefetch_related('dias')
    ubicaciones_roots = Ubicacion.objects.filter(padre__isnull=True).order_by('nombre')
    categorias_activos = CategoriaActivo.objects.all().order_by('nombre')
    rutinas = Rutina.objects.all().select_related('tipo', 'frecuencia')
    pre_cat = rutina.tipo.categoria_activo.id if rutina and rutina.tipo and rutina.tipo.categoria_activo else None

    return render(request, 'mantenimiento/visual_scheduler.html', {
        'rutina_preselected': rutina, 'rutinas': rutinas, 'horarios': horarios, 'ubicaciones_roots': ubicaciones_roots, 'categorias_activos': categorias_activos, 'preselected_cat_id': pre_cat, 'today': today,
    })
