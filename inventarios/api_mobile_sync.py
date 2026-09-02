"""
APIs para la app móvil de inventario (offline-first sync).
- Login con token
- Master data sync (materiales, ubicaciones, stock)
- Push de operaciones pendientes
- Push de conteos de inventario
"""
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from django.contrib.auth import authenticate
from django.contrib.auth.decorators import login_required
from .models import Material, StockRecord, SolicitudMaterial, MovimientoInventario
from activos.models import Ubicacion
from decimal import Decimal
from django.utils import timezone
import hashlib


def _generate_token(user):
    """Genera un token simple basado en el usuario."""
    raw = f"{user.id}-{user.username}-{user.date_joined.isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _get_user_from_token(request):
    """Extrae el usuario del header Authorization: Token xxx"""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    auth = request.META.get('HTTP_AUTHORIZATION', '')
    if auth.startswith('Token '):
        token_key = auth[6:]
        # Buscar usuario cuyo token coincida
        for user in User.objects.filter(is_active=True):
            if _generate_token(user) == token_key:
                return user
    return None


@csrf_exempt
@require_POST
def api_mobile_login(request):
    """
    Autenticación por token para la app móvil.
    POST { "username": "...", "password": "..." }
    Returns { "token": "...", "user": {...} }
    """
    try:
        data = json.loads(request.body)
        username = data.get('username', '')
        password = data.get('password', '')
        
        user = authenticate(username=username, password=password)
        if not user:
            return JsonResponse({'error': 'Credenciales inválidas'}, status=401)
        
        token = _generate_token(user)

        # Determinar el rol para que la app muestre la interfaz correcta
        perfil = getattr(user, 'perfil', None)
        es_aprobador_salidas = bool(perfil and getattr(perfil, 'aprobador_salidas', False))
        departamento = getattr(getattr(perfil, 'departamento', None), 'nombre', '') or ''
        es_almacen = user.groups.filter(name__iexact='Almacenes').exists()

        # rol principal para la UI: 'almacen' > 'aprobador' > 'usuario'
        if es_almacen:
            rol = 'almacen'
        elif es_aprobador_salidas:
            rol = 'aprobador'
        else:
            rol = 'usuario'

        return JsonResponse({
            'token': token,
            'user': {
                'id': user.id,
                'username': user.username,
                'nombre': user.get_full_name() or user.username,
                'email': user.email,
                'is_staff': user.is_staff,
                'rol': rol,
                'es_aprobador_salidas': es_aprobador_salidas,
                'es_almacen': es_almacen,
                'departamento': departamento,
            }
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@csrf_exempt
@require_GET
def api_mobile_master_sync(request):
    """
    Retorna el catálogo completo para sync offline:
    - Materiales con stock total
    - Ubicaciones (bodegas/almacenes)
    - Stock por ubicación
    """
    user = _get_user_from_token(request)
    if not user:
        return JsonResponse({'error': 'No autorizado'}, status=401)
    
    # Materiales
    materiales = Material.objects.select_related('unidad_medida', 'categoria').all()
    materials_data = []
    for m in materiales:
        stock_total = sum(sr.cantidad for sr in m.existencias.all())
        materials_data.append({
            'id': m.id,
            'nombre': m.nombre,
            'sku': m.sku or '',
            'codigo_barras': m.codigo_barras or '',
            'descripcion': m.descripcion or '',
            'unidad': m.unidad_medida.nombre if m.unidad_medida else 'Unidad',
            'categoria': m.categoria.nombre if m.categoria else '',
            'imagen_url': m.imagen.url if m.imagen else '',
            'stock_total': float(stock_total),
            'updated_at': m.actualizado_en.isoformat() if m.actualizado_en else '',
        })
    
    # Ubicaciones (bodegas y almacenes)
    from django.db.models import Q
    ubicaciones = Ubicacion.objects.filter(
        Q(tipo='BODEGA') | Q(tipo='ALMACEN') | Q(es_almacen=True)
    ).order_by('nombre')
    locations_data = [{
        'id': u.id,
        'nombre': u.nombre,
        'tipo': u.tipo or 'BODEGA',
        'padre_id': u.padre_id,
    } for u in ubicaciones]
    
    # Stock por ubicación
    stock_records = StockRecord.objects.select_related('material', 'ubicacion').all()
    stock_data = [{
        'id': sr.id,
        'material_id': sr.material_id,
        'location_id': sr.ubicacion_id,
        'cantidad': float(sr.cantidad),
    } for sr in stock_records]
    
    return JsonResponse({
        'materials': materials_data,
        'locations': locations_data,
        'stock': stock_data,
        'timestamp': timezone.now().isoformat(),
    })


@csrf_exempt
@require_POST
def api_mobile_push_operations(request):
    """
    Recibe operaciones pendientes desde la app móvil.
    POST { "operations": [{ "id": 1, "tipo": "SALIDA|ENTRADA|TRANSFERENCIA", "payload": {...} }] }
    """
    user = _get_user_from_token(request)
    if not user:
        return JsonResponse({'error': 'No autorizado'}, status=401)
    
    try:
        data = json.loads(request.body)
        operations = data.get('operations', [])
        synced_ids = []
        material_id_map = {}  # temp_id (negativo) -> id real creado
        
        from .models import UnidadMedida, CategoriaMaterial
        import uuid as _uuid

        for op in operations:
            op_id = op.get('id')
            tipo = op.get('tipo')
            payload = op.get('payload', {})

            try:
                # --- CREAR MATERIAL OFFLINE ---
                if tipo == 'CREAR_MATERIAL':
                    nombre = (payload.get('nombre') or '').strip()
                    if not nombre:
                        continue
                    sku = (payload.get('sku') or '').strip() or f"MAT-{_uuid.uuid4().hex[:8].upper()}"
                    if Material.objects.filter(sku=sku).exists():
                        sku = f"MAT-{_uuid.uuid4().hex[:8].upper()}"
                    unidad_obj = None
                    if payload.get('unidad'):
                        unidad_obj = UnidadMedida.objects.filter(nombre__iexact=str(payload['unidad'])).first()
                    if not unidad_obj:
                        unidad_obj = UnidadMedida.objects.first()
                    nuevo = Material.objects.create(
                        nombre=nombre,
                        sku=sku,
                        codigo_barras=(payload.get('codigo_barras') or '').strip() or None,
                        unidad_medida=unidad_obj,
                        descripcion=(payload.get('descripcion') or '').strip(),
                    )
                    # Mapear el id temporal (negativo del cliente) al real
                    temp_id = payload.get('temp_id')
                    if temp_id is not None:
                        material_id_map[str(temp_id)] = nuevo.id
                    synced_ids.append(op_id)
                    continue

                # --- EDITAR MATERIAL OFFLINE ---
                if tipo == 'EDITAR_MATERIAL':
                    mat = Material.objects.filter(id=payload.get('material_id')).first()
                    if mat:
                        if payload.get('nombre'):
                            mat.nombre = payload['nombre'].strip()
                        if 'codigo_barras' in payload:
                            mat.codigo_barras = (payload.get('codigo_barras') or '').strip() or None
                        if 'descripcion' in payload:
                            mat.descripcion = (payload.get('descripcion') or '').strip()
                        mat.save()
                    synced_ids.append(op_id)
                    continue

                # --- MOVIMIENTOS DE STOCK ---
                # Resolver material_id (puede ser temporal si fue creado offline)
                raw_mat_id = payload.get('material_id')
                if str(raw_mat_id) in material_id_map:
                    raw_mat_id = material_id_map[str(raw_mat_id)]
                material = Material.objects.get(id=raw_mat_id)
                location_id = payload.get('location_id')
                ubicacion = Ubicacion.objects.filter(id=location_id).first() if location_id else None
                
                if tipo == 'SALIDA':
                    MovimientoInventario.objects.create(
                        material=material,
                        tipo='SALIDA',
                        cantidad=Decimal(str(payload.get('cantidad', 0))),
                        ubicacion_origen=ubicacion,
                        usuario=user,
                        estado='APROBADO',
                        fecha_movimiento=payload.get('timestamp', timezone.now()),
                        comentarios=f"Despacho desde app móvil",
                    )
                    synced_ids.append(op_id)
                    
                elif tipo == 'ENTRADA':
                    MovimientoInventario.objects.create(
                        material=material,
                        tipo='ENTRADA',
                        cantidad=Decimal(str(payload.get('cantidad', 0))),
                        ubicacion_destino=ubicacion,
                        usuario=user,
                        estado='APROBADO',
                        fecha_movimiento=payload.get('timestamp', timezone.now()),
                        comentarios=f"Recepción desde app móvil",
                    )
                    synced_ids.append(op_id)
                    
                elif tipo == 'TRANSFERENCIA':
                    origen = Ubicacion.objects.filter(id=payload.get('origen_id')).first()
                    destino = Ubicacion.objects.filter(id=payload.get('destino_id')).first()
                    cantidad = Decimal(str(payload.get('cantidad', 0)))
                    
                    MovimientoInventario.objects.create(
                        material=material,
                        tipo='TRASLADO',
                        cantidad=cantidad,
                        ubicacion_origen=origen,
                        ubicacion_destino=destino,
                        usuario=user,
                        estado='APROBADO',
                        comentarios=f"Transferencia {payload.get('origen_nombre', '')} → {payload.get('destino_nombre', '')} (app móvil)",
                    )
                    synced_ids.append(op_id)
                    
            except Exception as e:
                print(f"[MOBILE SYNC] Error procesando op {op_id}: {e}")
                continue
        
        return JsonResponse({'status': 'success', 'synced': synced_ids, 'total': len(synced_ids), 'material_id_map': material_id_map})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@csrf_exempt
@require_POST
def api_mobile_inventory_counts(request):
    """
    Recibe conteos de inventario físico desde la app móvil.
    POST { "counts": [{ "material_id": 1, "location_id": 1, "cantidad_sistema": 10, "cantidad_contada": 8 }] }
    """
    user = _get_user_from_token(request)
    if not user:
        return JsonResponse({'error': 'No autorizado'}, status=401)
    
    try:
        data = json.loads(request.body)
        counts = data.get('counts', [])
        processed = 0
        
        for count in counts:
            material_id = count.get('material_id')
            location_id = count.get('location_id')
            cantidad_contada = count.get('cantidad_contada')
            cantidad_sistema = count.get('cantidad_sistema')
            
            if material_id is None or cantidad_contada is None:
                continue
            
            material = Material.objects.filter(id=material_id).first()
            if not material:
                continue
            
            ubicacion = Ubicacion.objects.filter(id=location_id).first() if location_id else None
            diferencia = Decimal(str(cantidad_contada)) - Decimal(str(cantidad_sistema or 0))
            
            if diferencia != 0:
                # Positivo = hay más de lo esperado (entrada)
                # Negativo = hay menos de lo esperado (salida)
                MovimientoInventario.objects.create(
                    material=material,
                    tipo='AJUSTE',
                    cantidad=abs(diferencia),
                    ubicacion_origen=ubicacion if diferencia < 0 else None,
                    ubicacion_destino=ubicacion if diferencia > 0 else None,
                    usuario=user,
                    estado='APROBADO',
                    comentarios=f"Ajuste por inventario físico (app móvil). Sistema: {cantidad_sistema}, Contado: {cantidad_contada}",
                    es_inconsistente=True,
                )
            
            processed += 1
        
        return JsonResponse({'status': 'success', 'processed': processed})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@csrf_exempt
@require_POST
def api_mobile_create_material(request):
    """
    Crea un material nuevo desde la app móvil (autenticado por token).
    POST { "nombre": "...", "sku": "...", "unidad": "...", "categoria_id": ... }
    Returns el material creado con el mismo formato del master sync.
    """
    import uuid
    from .models import CategoriaMaterial, UnidadMedida

    user = _get_user_from_token(request)
    if not user:
        return JsonResponse({'error': 'No autorizado'}, status=401)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    nombre = (data.get('nombre') or '').strip()
    if not nombre:
        return JsonResponse({'error': 'El nombre es requerido.'}, status=400)

    sku = (data.get('sku') or '').strip()
    if not sku:
        sku = f"MAT-{uuid.uuid4().hex[:8].upper()}"

    if Material.objects.filter(sku=sku).exists():
        return JsonResponse({'error': f'El SKU "{sku}" ya existe.'}, status=400)

    # Unidad de medida (por nombre o id)
    unidad_obj = None
    unidad_val = data.get('unidad')
    if unidad_val:
        unidad_obj = UnidadMedida.objects.filter(nombre__iexact=str(unidad_val)).first()
    if not unidad_obj:
        unidad_obj = UnidadMedida.objects.first()  # fallback

    # Categoría opcional
    categoria_obj = None
    cat_id = data.get('categoria_id')
    if cat_id:
        categoria_obj = CategoriaMaterial.objects.filter(id=cat_id).first()

    try:
        precio = float(data.get('precio_estimado') or 0)
    except (ValueError, TypeError):
        precio = 0

    material = Material.objects.create(
        nombre=nombre,
        sku=sku,
        codigo_barras=(data.get('codigo_barras') or '').strip() or None,
        unidad_medida=unidad_obj,
        categoria=categoria_obj,
        precio_estimado=precio,
        descripcion=(data.get('descripcion') or '').strip(),
    )

    return JsonResponse({
        'id': material.id,
        'nombre': material.nombre,
        'sku': material.sku,
        'codigo_barras': material.codigo_barras or '',
        'descripcion': material.descripcion or '',
        'unidad': material.unidad_medida.nombre if material.unidad_medida else 'Unidad',
        'categoria': material.categoria.nombre if material.categoria else '',
        'imagen_url': '',
        'stock_total': 0,
        'updated_at': material.actualizado_en.isoformat() if material.actualizado_en else '',
    })


@csrf_exempt
@require_POST
def api_mobile_update_material(request, material_id):
    """
    Actualiza datos de un material desde la app móvil (nombre, código de barras, descripción, unidad).
    """
    from .models import UnidadMedida
    user = _get_user_from_token(request)
    if not user:
        return JsonResponse({'error': 'No autorizado'}, status=401)

    material = Material.objects.filter(id=material_id).first()
    if not material:
        return JsonResponse({'error': 'Material no encontrado'}, status=404)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    if 'nombre' in data and data['nombre'].strip():
        material.nombre = data['nombre'].strip()
    if 'codigo_barras' in data:
        material.codigo_barras = (data.get('codigo_barras') or '').strip() or None
    if 'descripcion' in data:
        material.descripcion = (data.get('descripcion') or '').strip()
    if data.get('unidad'):
        unidad_obj = UnidadMedida.objects.filter(nombre__iexact=str(data['unidad'])).first()
        if unidad_obj:
            material.unidad_medida = unidad_obj

    material.save()

    return JsonResponse({
        'id': material.id,
        'nombre': material.nombre,
        'sku': material.sku,
        'codigo_barras': material.codigo_barras or '',
        'descripcion': material.descripcion or '',
        'unidad': material.unidad_medida.nombre if material.unidad_medida else 'Unidad',
    })


@csrf_exempt
@require_GET
def api_mobile_categorias(request):
    """Lista de categorías de material para la app móvil."""
    from .models import CategoriaMaterial
    user = _get_user_from_token(request)
    if not user:
        return JsonResponse({'error': 'No autorizado'}, status=401)
    cats = CategoriaMaterial.objects.all().order_by('nombre').values('id', 'nombre')
    return JsonResponse({'categorias': list(cats)})


# ==========================================================================
# APIs móviles por rol: aprobaciones, despachos, mis solicitudes, push token
# ==========================================================================

def _serialize_items(solicitud):
    items = []
    for mov in solicitud.items.select_related('material', 'material__unidad_medida').all():
        items.append({
            'mov_id': mov.id,
            'material_id': mov.material_id,
            'material_nombre': mov.material.nombre if mov.material else '',
            'sku': mov.material.sku if mov.material else '',
            'cantidad': float(mov.cantidad_solicitada or mov.cantidad or 0),
            'unidad': mov.material.unidad_medida.abreviatura if (mov.material and mov.material.unidad_medida) else 'UND',
        })
    return items


def _serialize_solicitud(solicitud, full=False):
    data = {
        'id': solicitud.id,
        'estado': solicitud.estado,
        'estado_display': solicitud.get_estado_display(),
        'solicitante': solicitud.solicitante_nombre,
        'fecha': timezone.localtime(solicitud.fecha_solicitud).strftime('%d/%m/%Y %H:%M') if solicitud.fecha_solicitud else '',
        'ubicacion_origen': solicitud.ubicacion_origen.nombre if solicitud.ubicacion_origen else '',
        'orden_trabajo': solicitud.orden_trabajo.codigo_de_orden if solicitud.orden_trabajo else '',
        'comentarios': solicitud.comentarios_solicitud or '',
        'num_items': solicitud.items.count(),
    }
    if solicitud.autorizado_por:
        data['autorizado_por'] = solicitud.autorizado_por.get_full_name() or solicitud.autorizado_por.username
    if full:
        data['items'] = _serialize_items(solicitud)
    return data


@csrf_exempt
@require_GET
def api_mobile_aprobaciones(request):
    """Solicitudes pendientes de autorización del departamento del aprobador."""
    user = _get_user_from_token(request)
    if not user:
        return JsonResponse({'error': 'No autorizado'}, status=401)

    perfil = getattr(user, 'perfil', None)
    departamento = getattr(perfil, 'departamento', None)
    if not departamento or not getattr(perfil, 'aprobador_salidas', False):
        return JsonResponse({'solicitudes': []})

    qs = (SolicitudMaterial.objects
          .filter(estado='PENDIENTE_AUTORIZACION', usuario__perfil__departamento=departamento)
          .select_related('usuario', 'orden_trabajo', 'ubicacion_origen')
          .distinct().order_by('-fecha_solicitud'))
    return JsonResponse({'solicitudes': [_serialize_solicitud(s) for s in qs]})


@csrf_exempt
@require_POST
def api_mobile_aprobar(request, pk):
    """Aprueba o rechaza una solicitud (aprobador de salidas del departamento)."""
    user = _get_user_from_token(request)
    if not user:
        return JsonResponse({'error': 'No autorizado'}, status=401)

    perfil = getattr(user, 'perfil', None)
    departamento = getattr(perfil, 'departamento', None)
    if not departamento or not getattr(perfil, 'aprobador_salidas', False):
        return JsonResponse({'status': 'error', 'message': 'No tienes permisos de aprobador.'}, status=403)

    solicitud = SolicitudMaterial.objects.filter(pk=pk).first()
    if not solicitud:
        return JsonResponse({'status': 'error', 'message': 'Solicitud no encontrada.'}, status=404)

    sol_dep = getattr(getattr(solicitud.usuario, 'perfil', None), 'departamento', None)
    if sol_dep != departamento:
        return JsonResponse({'status': 'error', 'message': 'Esta solicitud no pertenece a tu departamento.'}, status=403)

    if solicitud.estado != 'PENDIENTE_AUTORIZACION':
        return JsonResponse({'status': 'error', 'message': f'La solicitud ya no está pendiente ({solicitud.get_estado_display()}).'}, status=400)

    try:
        data = json.loads(request.body or '{}')
    except Exception:
        data = {}
    accion = (data.get('accion') or '').lower()

    if accion == 'aprobar':
        solicitud.estado = 'PENDIENTE'
        solicitud.autorizado_por = user
        solicitud.fecha_autorizacion = timezone.now()
        solicitud.save(update_fields=['estado', 'autorizado_por', 'fecha_autorizacion'])
        try:
            from .utils_ntfy import notificar_nueva_solicitud
            notificar_nueva_solicitud(solicitud)
        except Exception:
            pass
        try:
            from .utils_n8n import notify_powerautomate_almacen
            notify_powerautomate_almacen(solicitud)
        except Exception:
            pass
        try:
            from .utils_push import push_a_almacen
            push_a_almacen(solicitud)
        except Exception:
            pass
        return JsonResponse({'status': 'success', 'message': 'Solicitud autorizada.'})
    elif accion == 'rechazar':
        solicitud.estado = 'RECHAZADO'
        solicitud.rechazado_por = user
        solicitud.fecha_rechazo = timezone.now()
        solicitud.save(update_fields=['estado', 'rechazado_por', 'fecha_rechazo'])
        return JsonResponse({'status': 'success', 'message': 'Solicitud rechazada.'})
    return JsonResponse({'status': 'error', 'message': 'Acción no válida.'}, status=400)


@csrf_exempt
@require_GET
def api_mobile_despachos(request):
    """Solicitudes por despachar (PENDIENTE) o listas para recolección (LISTO_RECOLECCION). Solo grupo Almacenes."""
    user = _get_user_from_token(request)
    if not user:
        return JsonResponse({'error': 'No autorizado'}, status=401)
    if not user.groups.filter(name__iexact='Almacenes').exists():
        return JsonResponse({'solicitudes': []})

    qs = (SolicitudMaterial.objects
          .filter(estado__in=['PENDIENTE', 'LISTO_RECOLECCION'])
          .select_related('usuario', 'orden_trabajo', 'ubicacion_origen')
          .order_by('-fecha_solicitud'))
    return JsonResponse({'solicitudes': [_serialize_solicitud(s) for s in qs]})


@csrf_exempt
@require_POST
def api_mobile_despachar(request, pk):
    """Despacha (pasa a LISTO_RECOLECCION) y notifica al solicitante. Solo grupo Almacenes."""
    user = _get_user_from_token(request)
    if not user:
        return JsonResponse({'error': 'No autorizado'}, status=401)
    if not user.groups.filter(name__iexact='Almacenes').exists():
        return JsonResponse({'status': 'error', 'message': 'Solo Almacenes puede despachar.'}, status=403)

    solicitud = SolicitudMaterial.objects.filter(pk=pk).first()
    if not solicitud:
        return JsonResponse({'status': 'error', 'message': 'Solicitud no encontrada.'}, status=404)
    if solicitud.estado != 'PENDIENTE':
        return JsonResponse({'status': 'error', 'message': f'La solicitud no está lista para despacho ({solicitud.get_estado_display()}).'}, status=400)

    solicitud.estado = 'LISTO_RECOLECCION'
    solicitud.entregado_por = user
    solicitud.save(update_fields=['estado', 'entregado_por'])
    try:
        from .utils_n8n import notify_powerautomate_recoleccion
        notify_powerautomate_recoleccion(solicitud)
    except Exception:
        pass
    try:
        from .utils_push import push_a_solicitante
        push_a_solicitante(solicitud)
    except Exception:
        pass
    return JsonResponse({'status': 'success', 'message': 'Despachada. Se notificó al solicitante.'})


@csrf_exempt
@require_POST
def api_mobile_confirmar_entrega(request, pk):
    """Confirma la entrega con foto de quién recibe. Descuenta stock -> ENTREGADO. Solo grupo Almacenes."""
    import base64
    from django.core.files.base import ContentFile
    from django.db import transaction

    user = _get_user_from_token(request)
    if not user:
        return JsonResponse({'error': 'No autorizado'}, status=401)
    if not user.groups.filter(name__iexact='Almacenes').exists():
        return JsonResponse({'status': 'error', 'message': 'Solo Almacenes puede confirmar la entrega.'}, status=403)

    solicitud = SolicitudMaterial.objects.filter(pk=pk).first()
    if not solicitud:
        return JsonResponse({'status': 'error', 'message': 'Solicitud no encontrada.'}, status=404)
    if solicitud.estado != 'LISTO_RECOLECCION':
        return JsonResponse({'status': 'error', 'message': f'La solicitud no está lista para recolección ({solicitud.get_estado_display()}).'}, status=400)

    try:
        data = json.loads(request.body or '{}')
    except Exception:
        data = {}

    recibe_nombre = (data.get('recibe_nombre') or '').strip()
    foto_base64 = data.get('foto_base64') or ''

    try:
        with transaction.atomic():
            for mov in solicitud.items.all():
                if mov.estado != 'APROBADO':
                    mov.liquidar(user)

            solicitud.estado = 'ENTREGADO'
            solicitud.recibe_nombre = recibe_nombre or None
            if not solicitud.entregado_por:
                solicitud.entregado_por = user
            solicitud.fecha_entrega = timezone.now()

            if foto_base64:
                try:
                    img_data = base64.b64decode(foto_base64)
                    solicitud.foto_entrega.save(f'entrega_{solicitud.id}.jpg', ContentFile(img_data), save=False)
                except Exception:
                    pass

            solicitud.save()

        try:
            from .utils_n8n import notify_powerautomate_despacho
            notify_powerautomate_despacho(solicitud)
        except Exception:
            pass

        return JsonResponse({'status': 'success', 'message': f'Entrega de la solicitud #{solicitud.id} confirmada.'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Error al confirmar: {str(e)}'}, status=500)


@csrf_exempt
@require_GET
def api_mobile_mis_solicitudes(request):
    """Solicitudes del usuario autenticado."""
    user = _get_user_from_token(request)
    if not user:
        return JsonResponse({'error': 'No autorizado'}, status=401)
    qs = (SolicitudMaterial.objects
          .filter(usuario=user)
          .select_related('orden_trabajo', 'ubicacion_origen')
          .order_by('-fecha_solicitud')[:100])
    return JsonResponse({'solicitudes': [_serialize_solicitud(s) for s in qs]})


@csrf_exempt
@require_GET
def api_mobile_solicitud_detalle(request, pk):
    """Detalle completo de una solicitud (dueño, mismo departamento o almacén)."""
    user = _get_user_from_token(request)
    if not user:
        return JsonResponse({'error': 'No autorizado'}, status=401)

    solicitud = SolicitudMaterial.objects.filter(pk=pk).select_related('usuario', 'orden_trabajo', 'ubicacion_origen').first()
    if not solicitud:
        return JsonResponse({'error': 'No encontrada'}, status=404)

    perfil = getattr(user, 'perfil', None)
    mi_dep = getattr(getattr(perfil, 'departamento', None), 'id', None)
    sol_dep = getattr(getattr(getattr(solicitud.usuario, 'perfil', None), 'departamento', None), 'id', None)
    es_almacen = user.groups.filter(name__iexact='Almacenes').exists()
    es_aprobador = bool(perfil and getattr(perfil, 'aprobador_salidas', False))

    if not (solicitud.usuario_id == user.id or (mi_dep and mi_dep == sol_dep) or es_almacen or es_aprobador or user.is_superuser):
        return JsonResponse({'error': 'Sin permiso'}, status=403)

    return JsonResponse({'solicitud': _serialize_solicitud(solicitud, full=True)})


@csrf_exempt
@require_POST
def api_mobile_push_token(request):
    """Registra el token de notificaciones push (Expo) del usuario."""
    user = _get_user_from_token(request)
    if not user:
        return JsonResponse({'error': 'No autorizado'}, status=401)
    try:
        data = json.loads(request.body or '{}')
    except Exception:
        data = {}
    token = (data.get('token') or '').strip()
    perfil = getattr(user, 'perfil', None)
    if perfil is not None and token:
        perfil.expo_push_token = token
        perfil.save(update_fields=['expo_push_token'])
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error', 'message': 'Token o perfil no disponible.'}, status=400)
