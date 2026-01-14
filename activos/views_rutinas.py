from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from .models import Ubicacion
from mantenimiento.models import Rutina

@staff_member_required
def get_rutinas_ubicacion(request):
    """
    Retorna las rutinas de mantenimiento aplicables a la categoría de la ubicación dada.
    Endpoint: /activos/api/get_rutinas_ubicacion/?id=<ubicacion_id>
    """
    ubi_id = request.GET.get('id')
    if not ubi_id:
        return JsonResponse({'error': 'ID faltante'}, status=400)
    
    try:
        ubicacion = Ubicacion.objects.select_related('categoria').get(id=ubi_id)
    except Ubicacion.DoesNotExist:
        return JsonResponse({'error': 'Ubicación no encontrada'}, status=404)
    
    activos_cat = ubicacion.categoria
    if not activos_cat:
        return JsonResponse({'rutinas': []})
    
    # 1. Encontrar la categoría de mantenimiento vinculada a esta categoría de activo
    # La relación es OneToOne en Mantenimiento.Categoria hacia Activos.Categoria
    m_cat = getattr(activos_cat, 'mantenimiento_categoria', None)
    
    if not m_cat:
        # Intento de fallback: buscar si algún ANCESTRO de la categoría de activo tiene vínculo
        # (Opción avanzada, por ahora devolvemos vacío si no hay link directo)
        return JsonResponse({'rutinas': []})

    # 2. Recopilar IDs de la categoría de mantenimiento y sus ancestros
    # Esto permite que las rutinas definidas en "Sistemas Generales" apliquen a "Sistema Eléctrico"
    m_cats_ids = []
    curr = m_cat
    while curr:
        m_cats_ids.append(curr.id)
        curr = curr.padre
        
    # 3. Buscar todas las rutinas que pertenezcan a cualquiera de esas categorías
    rutinas = Rutina.objects.filter(
        categoria_id__in=m_cats_ids
    ).select_related('frecuencia', 'categoria', 'puesto_trabajo').order_by('categoria__nombre', 'nombre')
    
    data_rutinas = []
    for r in rutinas:
        titulo_cat = r.categoria.nombre if r.categoria else 'General'
        if r.categoria and r.categoria.id != m_cat.id:
            titulo_cat += " (Heredada)"
            
        data_rutinas.append({
            'id': r.id,
            'nombre': r.nombre,
            'frecuencia': r.frecuencia.nombre if r.frecuencia else 'Eventual',
            'categoria': titulo_cat,
            'tiempo': f"{int(r.tiempo_estimado.total_seconds() // 60)} min" if r.tiempo_estimado else "N/A"
        })
        
    return JsonResponse({'rutinas': data_rutinas})
