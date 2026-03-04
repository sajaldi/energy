import sys, re

# 1. Update rutinas_dashboard.py
with open('d:/Apps/energia/energy/mantenimiento/views/rutinas_dashboard.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Replace endpoint name and logic
# We rename procedimiento_save_api to rutina_pasos_save_api
old_proc_save_api = '''@staff_member_required
def procedimiento_save_api(request):
    \"\"\"API para guardar los pasos de un procedimiento estándar de forma atómica\"\"\"
    from django.http import JsonResponse
    from django.db import transaction
    import json
    
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
        
    try:
        data = json.loads(request.body)
        proc_id = data.get('procedimiento_id')
        pasos_data = data.get('pasos', [])
        
        if not proc_id:
            return JsonResponse({'status': 'error', 'message': 'ID de procedimiento requerido'}, status=400)
            
        with transaction.atomic():
            procedimiento = Procedimiento.objects.get(pk=proc_id)
            
            # 1. Obtener IDs de pasos actuales para controlar borrados
            existing_pasos = {p.id: p for p in procedimiento.pasos.all()}
            new_paso_ids = []
            
            for i, p_data in enumerate(pasos_data):
                p_id = p_data.get('id')
                if p_id and int(p_id) in existing_pasos:
                    paso = existing_pasos[int(p_id)]
                else:
                    paso = PasoProcedimiento(procedimiento=procedimiento)
                
                paso.orden = i + 1
                paso.descripcion = p_data.get('descripcion', '')
                paso.verificacion = p_data.get('verificacion', '')
                paso.tipo_respuesta = p_data.get('tipo_respuesta', 'INSTRUCCION')
                paso.unidad_medida = p_data.get('unidad_medida', '')
                
                # Campos numéricos
                try:
                    v_obj = p_data.get('valor_objetivo')
                    paso.valor_objetivo = float(v_obj) if v_obj and str(v_obj).strip() else None
                    r_min = p_data.get('rango_min')
                    paso.rango_min = float(r_min) if r_min and str(r_min).strip() else None
                    r_max = p_data.get('rango_max')
                    paso.rango_max = float(r_max) if r_max and str(r_max).strip() else None
                except (ValueError, TypeError):
                    pass
                
                paso.save()
                new_paso_ids.append(paso.id)
            
            # 2. Borrar pasos que no vinieron en el nuevo set
            PasoProcedimiento.objects.filter(procedimiento=procedimiento).exclude(id__in=new_paso_ids).delete()
            
        return JsonResponse({'status': 'success', 'message': 'Procedimiento actualizado correctamente'})
        
    except Procedimiento.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Procedimiento no encontrado'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)'''

new_proc_save_api = '''@staff_member_required
def rutina_pasos_save_api(request):
    \"\"\"API para guardar los pasos de una rutina de forma atómica\"\"\"
    from django.http import JsonResponse
    from django.db import transaction
    import json
    from ..models import Rutina, PasoRutina
    
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
        
    try:
        data = json.loads(request.body)
        rutina_id = data.get('rutina_id')
        pasos_data = data.get('pasos', [])
        
        if not rutina_id:
            return JsonResponse({'status': 'error', 'message': 'ID de rutina requerido'}, status=400)
            
        with transaction.atomic():
            rutina = Rutina.objects.get(pk=rutina_id)
            
            existing_pasos = {p.id: p for p in rutina.pasos.all()}
            new_paso_ids = []
            
            for i, p_data in enumerate(pasos_data):
                p_id = p_data.get('id')
                if p_id and int(p_id) in existing_pasos:
                    paso = existing_pasos[int(p_id)]
                else:
                    paso = PasoRutina(rutina=rutina)
                
                paso.orden = i + 1
                paso.descripcion = p_data.get('descripcion', '')
                paso.verificacion = p_data.get('verificacion', '')
                paso.tipo_respuesta = p_data.get('tipo_respuesta', 'INSTRUCCION')
                paso.unidad_medida = p_data.get('unidad_medida', '')
                
                try:
                    v_obj = p_data.get('valor_objetivo')
                    paso.valor_objetivo = float(v_obj) if v_obj and str(v_obj).strip() else None
                    r_min = p_data.get('rango_min')
                    paso.rango_min = float(r_min) if r_min and str(r_min).strip() else None
                    r_max = p_data.get('rango_max')
                    paso.rango_max = float(r_max) if r_max and str(r_max).strip() else None
                except (ValueError, TypeError):
                    pass
                
                paso.save()
                new_paso_ids.append(paso.id)
            
            PasoRutina.objects.filter(rutina=rutina).exclude(id__in=new_paso_ids).delete()
            
        return JsonResponse({'status': 'success', 'message': 'Pasos actualizados correctamente'})
        
    except Rutina.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Rutina no encontrada'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)'''

text = text.replace(old_proc_save_api, new_proc_save_api)

# And remove the procedimiento_detail_api entirely, or just replace it with utina_pasos_api if needed.
# Since routine passes pasos at generic get, we don't need a separate endpoint for this if it's already in detail.
text = re.sub(r'@login_required\ndef procedimiento_detail_api[\s\S]*?status=500\)\n\n', '', text)

with open('d:/Apps/energia/energy/mantenimiento/views/rutinas_dashboard.py', 'w', encoding='utf-8') as f:
    f.write(text)

# 2. Update urls.py to point to the new save function instead of old one
with open('d:/Apps/energia/energy/mantenimiento/urls.py', 'r', encoding='utf-8') as f:
    urls_text = f.read()
urls_text = urls_text.replace(\"path('rutinas/dashboard/procedimiento/save/', rutinas_dashboard.procedimiento_save_api, name='procedimiento_save_api'),\", \"path('rutinas/dashboard/rutina/pasos/save/', rutinas_dashboard.rutina_pasos_save_api, name='rutina_pasos_save_api'),\")
urls_text = urls_text.replace(\"path('rutinas/dashboard/procedimiento/detail/<int:pk>/', rutinas_dashboard.procedimiento_detail_api, name='procedimiento_detail_api'),\", \"\")
with open('d:/Apps/energia/energy/mantenimiento/urls.py', 'w', encoding='utf-8') as f:
    f.write(urls_text)

print("Views and URLs updated.")
