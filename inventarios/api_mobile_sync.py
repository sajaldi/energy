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
        stock_total = sum(sr.cantidad for sr in m.stock_records.all())
        materials_data.append({
            'id': m.id,
            'nombre': m.nombre,
            'sku': m.sku or '',
            'descripcion': m.descripcion or '',
            'unidad': m.unidad_medida.nombre if m.unidad_medida else 'Unidad',
            'categoria': m.categoria.nombre if m.categoria else '',
            'imagen_url': m.imagen.url if m.imagen else '',
            'stock_total': float(stock_total),
            'updated_at': m.actualizado_en.isoformat() if hasattr(m, 'actualizado_en') and m.actualizado_en else '',
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
                
                if tipo == 'SALIDA':
                    MovimientoInventario.objects.create(
                        material=material,
                        tipo='SALIDA',
                        cantidad=Decimal(str(payload.get('cantidad', 0))),
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
                    
                    # Salida del origen
                    MovimientoInventario.objects.create(
                        material=material,
                        tipo='SALIDA',
                        cantidad=cantidad,
                        ubicacion_origen=origen,
                        usuario=user,
                        estado='APROBADO',
                        comentarios=f"Transferencia a {payload.get('destino_nombre', '')} (app móvil)",
                    )
                    # Entrada al destino
                    MovimientoInventario.objects.create(
                        material=material,
                        tipo='ENTRADA',
                        cantidad=cantidad,
                        ubicacion_destino=destino,
                        usuario=user,
                        estado='APROBADO',
                        comentarios=f"Transferencia desde {payload.get('origen_nombre', '')} (app móvil)",
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
            
            diferencia = Decimal(str(cantidad_contada)) - Decimal(str(cantidad_sistema or 0))
            
            if diferencia != 0:
                tipo = 'AJUSTE'
                MovimientoInventario.objects.create(
                    material=material,
                    tipo=tipo,
                    cantidad=abs(diferencia),
                    usuario=user,
                    estado='APROBADO',
                    comentarios=f"Ajuste por inventario físico (app móvil). Sistema: {cantidad_sistema}, Contado: {cantidad_contada}",
                    es_inconsistente=True,
                )
            
            processed += 1
        
        return JsonResponse({'status': 'success', 'processed': processed})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
