from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Q
from .models import Ubicacion
from mantenimiento.models import Rutina, Tipo

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
    
    # 1. Encontrar los Tipos de mantenimiento vinculados a esta categoría de activo
    tipo_ids = set(Tipo.objects.filter(categoria_activo=activos_cat).values_list('id', flat=True))
    
    m_cat_mgr = getattr(activos_cat, 'mantenimiento_tipo', None)
    if m_cat_mgr is not None:
        tipo_ids.update(m_cat_mgr.values_list('id', flat=True))

    if not tipo_ids:
        # Even without linked Tipos, check for Rutinas with direct categoria_activo
        pass

    # 2. Recopilar IDs de los tipos y sus ancestros
    direct_tipo_ids = set(tipo_ids)
    all_tipo_ids = set(tipo_ids)
    queue = list(tipo_ids)
    while queue:
        children = Tipo.objects.filter(padre_id__in=queue).values_list('id', flat=True)
        new_ids = set(children) - all_tipo_ids
        all_tipo_ids.update(new_ids)
        queue = list(new_ids)

    # 3. Buscar todas las rutinas que pertenezcan a cualquiera de esos tipos
    #    O que tengan categoria_activo apuntando directamente a esta categoría
    q = Q(categoria_activo=activos_cat)
    if all_tipo_ids:
        q |= Q(tipo_id__in=all_tipo_ids)
    rutinas = Rutina.objects.filter(
        q
    ).select_related('frecuencia', 'tipo', 'puesto_trabajo').order_by('tipo__nombre', 'nombre')
    
    data_rutinas = []
    for r in rutinas:
        titulo_cat = r.tipo.nombre if r.tipo else 'General'
        if r.tipo and r.tipo.id not in direct_tipo_ids:
            titulo_cat += " (Heredada)"
            
        data_rutinas.append({
            'id': r.id,
            'nombre': r.nombre,
            'frecuencia': r.frecuencia.nombre if r.frecuencia else 'Eventual',
            'categoria': titulo_cat,
            'tiempo': f"{int(r.tiempo_estimado.total_seconds() // 60)} min" if r.tiempo_estimado else "N/A"
        })
        
    return JsonResponse({'rutinas': data_rutinas})


@staff_member_required
def punto_medicion_qr_pdf(request, pk):
    """Genera la etiqueta QR PDF 3x2 pulgadas para un Punto de Medición."""
    import io
    import qrcode
    import base64
    from django.http import HttpResponse
    from django.template.loader import get_template
    from xhtml2pdf import pisa
    from activos.models import PuntoMedicion
    from django.conf import settings
    
    punto = get_object_or_404(PuntoMedicion, pk=pk)
    
    base_url = settings.SITE_URL.rstrip('/')
    qr_data = f"{base_url}/activos/app/buscar/?q=PM-{punto.id}"
    
    qr = qrcode.QRCode(version=1, box_size=5, border=1)
    qr.add_data(qr_data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    qr_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    context = {
        'punto': punto,
        'qr_code': qr_b64
    }
    
    template = get_template('activos/punto_medicion_etiqueta_pdf.html')
    html = template.render(context)
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="etiqueta_pm_{punto.id}.pdf"'
    
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse(f'Error al generar PDF: {pisa_status.err}', status=500)
        
    return response
