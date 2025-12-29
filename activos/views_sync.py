from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json

@csrf_exempt
def submit_all_activos(request):
    """
    Sincronización masiva de activos desde la app móvil.
    Recibe una lista de activos y realiza upsert (crear o actualizar).
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
    
    try:
        data = json.loads(request.body)
        if not isinstance(data, list):
            return JsonResponse({'status': 'error', 'message': 'Se esperaba una lista de activos'}, status=400)
        
        resultados = {
            'creados': 0,
            'actualizados': 0,
            'errores': 0,
            'detalles': []
        }
        
        from django.db import transaction
        from .models import Activo, Modelo, Ubicacion
        
        with transaction.atomic():
            for item in data:
                try:
                    activo = None
                    # Intentar buscar por ID si viene
                    if item.get('id'):
                        activo = Activo.objects.filter(pk=item.get('id')).first()
                    
                    # Si no, buscar por código interno si viene
                    if not activo and item.get('codigo_interno'):
                        activo = Activo.objects.filter(codigo_interno=item.get('codigo_interno')).first()
                    
                    # Datos a guardar
                    defaults = {
                        'nombre': item.get('nombre', 'Sin Nombre'),
                        'serie': item.get('serie', ''),
                        'descripcion': item.get('descripcion', ''),
                        'estado': item.get('estado', 'OPERATIVO'),
                        'fecha_compra': item.get('fecha_compra') or None, # Manejar string vacía
                        'costo': item.get('costo') or 0,
                    }
                    
                    # Manejo de Relaciones (Foreign Keys)
                    # Modelo
                    if item.get('modelo_id'):
                        defaults['modelo_id'] = item.get('modelo_id')
                    
                    # Ubicación
                    if item.get('ubicacion_id'):
                        defaults['ubicacion_id'] = item.get('ubicacion_id')
                    
                    if activo:
                        # Actualizar
                        for key, value in defaults.items():
                            setattr(activo, key, value)
                        
                        # El código interno solo se actualiza si viene y es diferente
                        if item.get('codigo_interno'):
                            activo.codigo_interno = item.get('codigo_interno')
                            
                        activo.save()
                        results = 'actualizado'
                        resultados['actualizados'] += 1
                    else:
                        # Crear uno nuevo
                        defaults['codigo_interno'] = item.get('codigo_interno')
                        activo = Activo.objects.create(**defaults)
                        results = 'creado'
                        resultados['creados'] += 1
                        
                    resultados['detalles'].append({
                        'codigo': item.get('codigo_interno'),
                        'status': results,
                        'id': activo.id
                    })
                    
                except Exception as e:
                    resultados['errores'] += 1
                    resultados['detalles'].append({
                        'codigo': item.get('codigo_interno', 'S/C'),
                        'status': 'error',
                        'error': str(e)
                    })
        
        return JsonResponse({
            'status': 'success',
            'summary': {
                'total_recibidos': len(data),
                'creados': resultados['creados'],
                'actualizados': resultados['actualizados'],
                'errores': resultados['errores']
            },
            'detalles': resultados['detalles']
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'JSON inválido'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
