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
    # La relación es OneToOne en Mantenimiento.Tipo hacia Activos.Categoria
    m_cat = getattr(activos_cat, 'mantenimiento_tipo', None)
    
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
        tipo_id__in=m_cats_ids
    ).select_related('frecuencia', 'tipo', 'puesto_trabajo').order_by('tipo__nombre', 'nombre')
    
    data_rutinas = []
    for r in rutinas:
        titulo_cat = r.tipo.nombre if r.tipo else 'General'
        if r.tipo and r.tipo.id != m_cat.id:
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
