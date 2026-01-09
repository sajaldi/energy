from django.shortcuts import render, get_object_or_404
from django.db import models
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from .models import Auditoria, ResultadoAuditoria
from activos.models import Activo, Ubicacion, Categoria
from django.db import transaction

@require_POST
def api_inicializar_auditoria(request, auditoria_id):
    """
    Busca todos los activos que coinciden con las ubicaciones y categorías
    seleccionadas en la auditoría y crea los registros de ResultadoAuditoria vacíos.
    """
    auditoria = get_object_or_404(Auditoria, id=auditoria_id)
    
    if auditoria.estado != 'BORRADOR':
        return JsonResponse({'error': 'La auditoría ya ha sido inicializada o finalizada.'}, status=400)

    ubicaciones = auditoria.ubicaciones.all()
    categorias = auditoria.categorias.all()

    # Obtener todos los descendientes de las ubicaciones seleccionadas
    all_ubicaciones_ids = set()
    for ubi in ubicaciones:
        desc = ubi.get_descendants(include_self=True).values_list('id', flat=True)
        all_ubicaciones_ids.update(desc)

    # Obtener todos los descendientes de las categorías seleccionadas
    all_categorias_ids = set()
    for cat in categorias:
        desc = cat.get_descendants(include_self=True).values_list('id', flat=True)
        all_categorias_ids.update(desc)

    # Filtrar activos
    queryset = Activo.objects.all()
    if all_ubicaciones_ids:
        queryset = queryset.filter(ubicacion_id__in=all_ubicaciones_ids)
    if all_categorias_ids:
        queryset = queryset.filter(modelo__categoria_id__in=all_categorias_ids)

    # Crear resultados por cada activo si no existen ya
    count = 0
    with transaction.atomic():
        for activo in queryset:
            res, created = ResultadoAuditoria.objects.get_or_create(
                auditoria=auditoria,
                activo=activo,
                defaults={'ubicacion_esperada': activo.ubicacion}
            )
            if created:
                count += 1
        
        auditoria.estado = 'EN_CURSO'
        auditoria.save()

    return JsonResponse({
        'status': 'success',
        'message': f'Auditoria inicializada con {count} activos pendientes.',
        'total_activos': ResultadoAuditoria.objects.filter(auditoria=auditoria).count()
    })

@require_POST
def api_procesar_escaneo(request, auditoria_id):
    """
    Procesa el escaneo de un código de barras o entrada manual.
    """
    auditoria = get_object_or_404(Auditoria, id=auditoria_id)
    barcode = request.POST.get('barcode', '').strip()
    ubicacion_encontrada_id = request.POST.get('ubicacion_id') # Opcional
    
    if not barcode:
        return JsonResponse({'error': 'No se proporcionó un código.'}, status=400)

    # Buscar el activo por código interno o número de serie
    activo = Activo.objects.filter(models.Q(codigo_interno=barcode) | models.Q(serie=barcode)).first()
    
    if not activo:
        return JsonResponse({'error': f'Activo "{barcode}" no encontrado.', 'barcode': barcode}, status=404)

    # Buscar si está en esta auditoría
    resultado = ResultadoAuditoria.objects.filter(auditoria=auditoria, activo=activo).first()
    
    ubicacion_encontrada = None
    if ubicacion_encontrada_id:
        ubicacion_encontrada = Ubicacion.objects.filter(id=ubicacion_encontrada_id).first()

    status_code = 'ENCONTRADO'
    if resultado:
        # Verificar ubicación
        target_ubi = ubicacion_encontrada or activo.ubicacion
        if resultado.ubicacion_esperada != target_ubi:
            status_code = 'UBICACION_ERRONEA'
        
        resultado.estado = status_code
        resultado.ubicacion_encontrada = ubicacion_encontrada or activo.ubicacion
        resultado.fecha_escaneo = timezone.now()
        resultado.save()
    else:
        # El activo no estaba en el alcance inicial de la auditoría
        resultado = ResultadoAuditoria.objects.create(
            auditoria=auditoria,
            activo=activo,
            estado='NO_PERTENECE',
            ubicacion_esperada=activo.ubicacion,
            ubicacion_encontrada=ubicacion_encontrada or activo.ubicacion,
            fecha_escaneo=timezone.now(),
            observaciones='Detectado durante escaneo fuera de rango inicial.'
        )
        status_code = 'NO_PERTENECE'

    return JsonResponse({
        'status': 'success',
        'activo': {
            'id': activo.id,
            'nombre': activo.nombre,
            'codigo': activo.codigo_interno,
            'ubicacion': activo.ubicacion.nombre if activo.ubicacion else 'N/A'
        },
        'resultado_estado': status_code,
        'display_estado': resultado.get_estado_display(),
        'stats': {
            'encontrados': ResultadoAuditoria.objects.filter(auditoria=auditoria).exclude(estado='PENDIENTE').count(),
            'total': ResultadoAuditoria.objects.filter(auditoria=auditoria).count()
        }
    })

def lista_auditorias(request):
    """Lists audits for the user."""
    auditorias = Auditoria.objects.all().order_by('-fecha_inicio')
    return render(request, 'auditorias/lista_auditorias.html', {'auditorias': auditorias})

def ejecutar_auditoria(request, auditoria_id):
    """Renders the scanning interface."""
    auditoria = get_object_or_404(Auditoria, id=auditoria_id)
    resultados = auditoria.resultados.all().select_related('activo', 'ubicacion_esperada')
    
    context = {
        'auditoria': auditoria,
        'pendientes': resultados.filter(estado='PENDIENTE').count(),
        'encontrados': resultados.filter(estado__in=['ENCONTRADO', 'UBICACION_ERRONEA', 'NO_PERTENECE']).count(),
        'total': resultados.count(),
        'resultados_recientes': resultados.exclude(estado='PENDIENTE').order_by('-fecha_escaneo')[:10],
    }
    return render(request, 'auditorias/ejecutar_auditoria.html', context)

@require_POST
def api_finalizar_auditoria(request, auditoria_id):
    """Finaliza la auditoría y marca extraviados."""
    auditoria = get_object_or_404(Auditoria, id=auditoria_id)
    if auditoria.estado == 'FINALIZADA':
        return JsonResponse({'error': 'La auditoría ya está finalizada.'}, status=400)
    
    with transaction.atomic():
        auditoria.resultados.filter(estado='PENDIENTE').update(estado='EXTRAVIADO')
        auditoria.estado = 'FINALIZADA'
        auditoria.fecha_fin = timezone.now()
        auditoria.save()
        
    return JsonResponse({'status': 'success', 'message': 'Auditoría finalizada correctamente.'})
