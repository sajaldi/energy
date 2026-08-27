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
        
        return JsonResponse({
            'token': token,
            'user': {
                'id': user.id,
                'username': user.username,
                'nombre': user.get_full_name() or user.username,
                'email': user.email,
                'is_staff': user.is_staff,
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
        
        for op in operations:
            op_id = op.get('id')
            tipo = op.get('tipo')
            payload = op.get('payload', {})
            
            try:
                material = Material.objects.get(id=payload.get('material_id'))
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
        
        return JsonResponse({'status': 'success', 'synced': synced_ids, 'total': len(synced_ids)})
        
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
        unidad_medida=unidad_obj,
        categoria=categoria_obj,
        precio_estimado=precio,
        descripcion=(data.get('descripcion') or '').strip(),
    )

    return JsonResponse({
        'id': material.id,
        'nombre': material.nombre,
        'sku': material.sku,
        'descripcion': material.descripcion or '',
        'unidad': material.unidad_medida.nombre if material.unidad_medida else 'Unidad',
        'categoria': material.categoria.nombre if material.categoria else '',
        'imagen_url': '',
        'stock_total': 0,
        'updated_at': material.actualizado_en.isoformat() if material.actualizado_en else '',
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
