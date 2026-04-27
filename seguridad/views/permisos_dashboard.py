from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.db import transaction
from ..models import TipoPermiso, RequisitoPermiso
import json

@staff_member_required
def tipo_permiso_dashboard(request):
    """Dashboard para gestionar Tipos de Permiso y sus Requisitos"""
    tipos_permiso = TipoPermiso.objects.all().prefetch_related('requisitos').order_by('nombre')
    
    return render(request, 'seguridad/permisos_dashboard.html', {
        'tipos_permiso': tipos_permiso,
        'title': 'Gestión de Tipos de Permisos'
    })

@staff_member_required
def tipo_permiso_detail_api(request, pk):
    """API que devuelve detalles de un Tipo de Permiso y sus Requisitos"""
    try:
        tipo = TipoPermiso.objects.get(pk=pk)
        
        data = {
            'status': 'success',
            'tipo': {
                'id': tipo.id,
                'nombre': tipo.nombre,
                'descripcion': tipo.descripcion or "",
                'requisitos': [
                    {
                        'id': r.id,
                        'orden': r.orden,
                        'texto': r.texto,
                        'es_critico': r.es_critico,
                        'tipo_respuesta': r.tipo_respuesta,
                        'verificacion': r.verificacion or "",
                        'unidad_medida': r.unidad_medida or "",
                        'valor_objetivo': r.valor_objetivo,
                        'rango_min': r.rango_min,
                        'rango_max': r.rango_max,
                    }
                    for r in tipo.requisitos.all()
                ]
            }
        }
        return JsonResponse(data)
    except TipoPermiso.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Tipo de Permiso no encontrado'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@staff_member_required
def tipo_permiso_save_api(request):
    """API para crear o actualizar un Tipo de Permiso"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
        
    try:
        data = json.loads(request.body)
        pk = data.get('id')
        
        if pk:
            tipo = TipoPermiso.objects.get(pk=pk)
        else:
            tipo = TipoPermiso()
            
        tipo.nombre = data.get('nombre')
        tipo.descripcion = data.get('descripcion')
        tipo.save()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Tipo de Permiso guardado correctamente',
            'tipo_id': tipo.id
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@staff_member_required
def tipo_permiso_requisitos_save_api(request):
    """API para guardar los requisitos de un Tipo de Permiso de forma atómica"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
        
    try:
        data = json.loads(request.body)
        tipo_id = data.get('tipo_id')
        requisitos_data = data.get('requisitos', [])
        
        if not tipo_id:
            return JsonResponse({'status': 'error', 'message': 'ID de tipo de permiso requerido'}, status=400)
            
        with transaction.atomic():
            tipo = TipoPermiso.objects.get(pk=tipo_id)
            
            # 1. Obtener IDs de requisitos actuales
            existing_requisitos = {r.id: r for r in tipo.requisitos.all()}
            new_requisito_ids = []
            
            for i, r_data in enumerate(requisitos_data):
                r_id = r_data.get('id')
                if r_id and int(r_id) in existing_requisitos:
                    requisito = existing_requisitos[int(r_id)]
                else:
                    requisito = RequisitoPermiso(tipo_permiso=tipo)
                
                requisito.orden = i + 1
                requisito.texto = r_data.get('texto', '')
                requisito.es_critico = r_data.get('es_critico', False)
                requisito.tipo_respuesta = r_data.get('tipo_respuesta', 'CHECK')
                requisito.verificacion = r_data.get('verificacion', '')
                requisito.unidad_medida = r_data.get('unidad_medida', '')
                
                # Campos numéricos
                try:
                    v_obj = r_data.get('valor_objetivo')
                    requisito.valor_objetivo = float(v_obj) if v_obj and str(v_obj).strip() else None
                    r_min = r_data.get('rango_min')
                    requisito.rango_min = float(r_min) if r_min and str(r_min).strip() else None
                    r_max = r_data.get('rango_max')
                    requisito.rango_max = float(r_max) if r_max and str(r_max).strip() else None
                except (ValueError, TypeError):
                    pass
                
                requisito.save()
                new_requisito_ids.append(requisito.id)
            
            # 2. Borrar requisitos que no vinieron en el nuevo set
            RequisitoPermiso.objects.filter(tipo_permiso=tipo).exclude(id__in=new_requisito_ids).delete()
            
        return JsonResponse({'status': 'success', 'message': 'Requisitos actualizados correctamente'})
        
    except TipoPermiso.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Tipo de Permiso no encontrado'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
