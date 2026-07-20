from django.shortcuts import render, get_object_or_404
from django.db import models
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from core.decorators import mobile_permission_required
from django.utils import timezone
from .models import Auditoria, ResultadoAuditoria, ConteoAuditoria
from activos.models import Activo, Ubicacion, Categoria
from django.db import transaction

@require_POST
@login_required
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
@login_required
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

@require_POST
@login_required
@mobile_permission_required('auditoria')
def api_actualizar_conteo(request, auditoria_id):
    """Actualiza la cantidad encontrada para una categoría y ubicación."""
    auditoria = get_object_or_404(Auditoria, id=auditoria_id)
    conteo_id = request.POST.get('conteo_id')
    cantidad = request.POST.get('cantidad', 0)
    
    conteo = get_object_or_404(ConteoAuditoria, id=conteo_id, auditoria=auditoria)
    
    try:
        conteo.cantidad_encontrada = int(cantidad)
        conteo.fecha_conteo = timezone.now()
        conteo.usuario_conteo = request.user
        conteo.save()
        
        return JsonResponse({
            'status': 'success',
            'cantidad_encontrada': conteo.cantidad_encontrada,
            'diferencia': conteo.cantidad_encontrada - conteo.cantidad_esperada
        })
    except ValueError:
        return JsonResponse({'error': 'Cantidad inválida'}, status=400)

@login_required
@mobile_permission_required('auditoria')
def lista_auditorias(request):
    """Lists audits for the user."""
    auditorias = Auditoria.objects.all().order_by('-fecha_inicio')
    return render(request, 'auditorias/lista_auditorias.html', {'auditorias': auditorias})

@login_required
@mobile_permission_required('auditoria')
def ejecutar_auditoria(request, auditoria_id):
    """Renders the scanning interface or counting interface."""
    auditoria = get_object_or_404(Auditoria, id=auditoria_id)
    
    if auditoria.tipo == 'CONTEO':
        from collections import OrderedDict
        conteos = list(auditoria.conteos.all().select_related(
            'ubicacion', 'ubicacion__padre', 'ubicacion__padre__padre', 
            'categoria', 'modelo', 'modelo__marca'
        ))

        def get_root(ubicacion):
            """Return the top-most ancestor."""
            if not ubicacion:
                return None
            curr = ubicacion
            visited = {curr.id}
            while curr.padre_id:
                if curr.padre and curr.padre.id not in visited:
                    visited.add(curr.padre.id)
                    curr = curr.padre
                else:
                    break
            return curr

        # Build: { ubi_raiz: { sub_ubi: { categoria: { modelo: [ConteoAuditoria] } } } }
        arbol_conteo = OrderedDict()
        for c in conteos:
            raiz_obj = get_root(c.ubicacion)
            raiz_nombre = raiz_obj.nombre if raiz_obj else 'Sin Ubicación'
            sub_nombre = c.ubicacion.nombre if c.ubicacion else 'Sin Ubicación'
            cat_nombre = c.categoria.nombre if c.categoria else 'Sin Categoría'
            mod_nombre = str(c.modelo) if c.modelo else 'Sin Modelo'
            mod_id = c.modelo_id if c.modelo else 0

            arbol_conteo\
                .setdefault(raiz_nombre, OrderedDict())\
                .setdefault(sub_nombre, OrderedDict())\
                .setdefault(cat_nombre, OrderedDict())\
                .setdefault((mod_nombre, mod_id), [])\
                .append(c)


        context = {
            'auditoria': auditoria,
            'conteos': conteos,
            'arbol_conteo': arbol_conteo,
            'total_esperado': sum(c.cantidad_esperada for c in conteos),
            'total_encontrado': sum(c.cantidad_encontrada for c in conteos),
        }
        return render(request, 'auditorias/ejecutar_conteo.html', context)




    resultados = auditoria.resultados.all().select_related(
        'activo',
        'activo__modelo',
        'activo__modelo__categoria',
        'activo__modelo__marca',
        'ubicacion_esperada',
        'ubicacion_esperada__padre',
    )

    # ── 3-level grouped tree: UbicaciónRaíz → Categoría → Modelo ──────────
    # Each level is an ordered dict/list so the template can iterate predictably.
    from collections import OrderedDict

    def get_root_nombre(ubicacion):
        """Walk up the hierarchy to get the top-most ancestor's name."""
        if not ubicacion:
            return 'Sin Ubicación'
        curr = ubicacion
        while curr.padre_id:
            if curr.padre:
                curr = curr.padre
            else:
                break
        return curr.nombre

    # Build: { ubi_raiz_nombre: { categoria_nombre: { modelo_nombre: [ResultadoAuditoria] } } }
    tree = OrderedDict()
    for res in resultados:
        ubi_raiz = get_root_nombre(res.ubicacion_esperada)
        modelo = res.activo.modelo if res.activo and res.activo.modelo else None
        categoria = modelo.categoria.nombre if (modelo and modelo.categoria) else 'Sin Categoría'
        modelo_nombre = f"{modelo.marca.nombre + ' ' if (modelo and modelo.marca) else ''}{modelo.nombre}" if modelo else 'Sin Modelo'

        if ubi_raiz not in tree:
            tree[ubi_raiz] = OrderedDict()
        if categoria not in tree[ubi_raiz]:
            tree[ubi_raiz][categoria] = OrderedDict()
        if modelo_nombre not in tree[ubi_raiz][categoria]:
            tree[ubi_raiz][categoria][modelo_nombre] = []
        tree[ubi_raiz][categoria][modelo_nombre].append(res)

    context = {
        'auditoria': auditoria,
        'pendientes': resultados.filter(estado='PENDIENTE').count(),
        'encontrados': resultados.filter(estado__in=['ENCONTRADO', 'UBICACION_ERRONEA', 'NO_PERTENECE']).count(),
        'total': resultados.count(),
        'resultados_recientes': resultados.exclude(estado='PENDIENTE').order_by('-fecha_escaneo')[:10],
        'arbol_jerarquico': tree,
    }
    return render(request, 'auditorias/ejecutar_auditoria.html', context)


@require_POST
@login_required
def api_finalizar_auditoria(request, auditoria_id):
    """Finaliza la auditoría y marca extraviados."""
    auditoria = get_object_or_404(Auditoria, id=auditoria_id)
    if auditoria.estado == 'FINALIZADA':
        return JsonResponse({'error': 'La auditoría ya está finalizada.'}, status=400)
    
    with transaction.atomic():
        if auditoria.tipo == 'ACTIVOS':
            auditoria.resultados.filter(estado='PENDIENTE').update(estado='EXTRAVIADO')
        elif auditoria.tipo == 'CONTEO':
            # Distribuir sobrantes de los hijos hacia los faltantes de los padres
            conteos = list(auditoria.conteos.all().select_related('ubicacion'))
            conteo_map = {(c.ubicacion_id, c.categoria_id): c for c in conteos}
            
            sobrantes = [c for c in conteos if c.cantidad_encontrada > c.cantidad_esperada]
            
            for sobrante in sobrantes:
                surplus_amount = sobrante.cantidad_encontrada - sobrante.cantidad_esperada
                
                # Buscar hacia arriba en la jerarquía de ubicaciones
                curr_ubi = sobrante.ubicacion.padre
                while curr_ubi and surplus_amount > 0:
                    parent_conteo = conteo_map.get((curr_ubi.id, sobrante.categoria_id))
                    
                    if parent_conteo and parent_conteo.cantidad_esperada > parent_conteo.cantidad_encontrada:
                        shortage = parent_conteo.cantidad_esperada - parent_conteo.cantidad_encontrada
                        transfer_amount = min(surplus_amount, shortage)
                        
                        # Transferir cantidad esperada del padre al hijo
                        parent_conteo.cantidad_esperada -= transfer_amount
                        sobrante.cantidad_esperada += transfer_amount
                        
                        surplus_amount -= transfer_amount
                    
                    curr_ubi = curr_ubi.padre
            
            # Guardar los conteos que hayan sido modificados (las nuevas cantidades esperadas)
            ConteoAuditoria.objects.bulk_update(conteos, ['cantidad_esperada'])
            
            # Reasignación física de Activos
            for conteo in conteos:
                if conteo.cantidad_encontrada > 0:
                    # Contar cuántos activos YA ESTÁN en esta ubicación
                    activos_actuales_count = Activo.objects.filter(
                        ubicacion=conteo.ubicacion,
                        modelo__categoria=conteo.categoria
                    ).count()
                    
                    faltan_por_mover = conteo.cantidad_encontrada - activos_actuales_count
                    
                    if faltan_por_mover > 0:
                        # Prioridad 1: Buscar en el nivel padre (hacia arriba)
                        curr_padre = conteo.ubicacion.padre
                        while curr_padre and faltan_por_mover > 0:
                            candidatos_padre = list(Activo.objects.filter(
                                ubicacion=curr_padre,
                                modelo__categoria=conteo.categoria
                            )[:faltan_por_mover])
                            
                            for activo in candidatos_padre:
                                activo.ubicacion = conteo.ubicacion
                                activo.save()
                                faltan_por_mover -= 1
                            
                            curr_padre = curr_padre.padre
                            
                        # Prioridad 2: Buscar en oficinas hermanas que tengan FALTANTES
                        if faltan_por_mover > 0:
                            otros_conteos = [c for c in conteos if c.categoria == conteo.categoria and c.id != conteo.id]
                            for otro in otros_conteos:
                                if faltan_por_mover == 0:
                                    break
                                
                                # Si ese otro lugar encontró MENOS de los que realmente tiene asignados
                                activos_en_otro = Activo.objects.filter(
                                    ubicacion=otro.ubicacion,
                                    modelo__categoria=otro.categoria
                                )
                                qty_en_otro = activos_en_otro.count()
                                
                                if qty_en_otro > otro.cantidad_encontrada:
                                    disponibles = qty_en_otro - otro.cantidad_encontrada
                                    a_robar = min(faltan_por_mover, disponibles)
                                    
                                    candidatos_hermano = list(activos_en_otro[:a_robar])
                                    for activo in candidatos_hermano:
                                        activo.ubicacion = conteo.ubicacion
                                        activo.save()
                                        faltan_por_mover -= 1
                                        
                        # Prioridad 3: Crear alerta si aún sobran y no sabemos de dónde salieron
                        if faltan_por_mover > 0:
                            observacion_alerta = f"ALERTA: Se encontraron {faltan_por_mover} activos excedentes sin origen claro en el nivel padre o ubicaciones hermanas."
                            if conteo.observaciones:
                                conteo.observaciones += "\n" + observacion_alerta
                            else:
                                conteo.observaciones = observacion_alerta
                            conteo.save()
                            
        auditoria.estado = 'FINALIZADA'
        auditoria.fecha_fin = timezone.now()
        auditoria.save()
        
    return JsonResponse({'status': 'success', 'message': 'Auditoría finalizada correctamente.'})
