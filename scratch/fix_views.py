import os

path = r'd:\Apps\energia\energy\inventarios\views.py'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# find def api_autorizar_solicitud(request, pk):
start_idx = 0
for i, l in enumerate(lines):
    if l.startswith('def api_autorizar_solicitud(request, pk):'):
        start_idx = i
        break

# The good code ends around line 2054
good_lines = lines[:2054]
with open(path, 'w', encoding='utf-8') as f:
    f.writelines(good_lines)
    f.write("        # Rechazar todos los movimientos asociados\n")
    f.write("        solicitud.items.update(estado='RECHAZADO')\n")
    f.write("        \n")
    f.write("        return JsonResponse({'status': 'success', 'message': f'Solicitud #{solicitud.id} rechazada.'})\n")
    f.write("        \n")
    f.write("    else:\n")
    f.write("        return JsonResponse({'status': 'error', 'message': 'Acción inválida. Use \"aprobar\" o \"rechazar\".'}, status=400)\n")
    f.write("\n")
    f.write("@csrf_exempt\n")
    f.write("@login_required\n")
    f.write("def api_sync_offline_queue(request):\n")
    f.write("    if request.method != 'POST': return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)\n")
    f.write("    import json\n")
    f.write("    from decimal import Decimal\n")
    f.write("    try:\n")
    f.write("        data = json.loads(request.body)\n")
    f.write("        queue = data.get('queue', [])\n")
    f.write("        if not queue: return JsonResponse({'status': 'success', 'message': 'Cola vacía'})\n")
    f.write("        procesados = 0\n")
    f.write("        errores = []\n")
    f.write("        from django.db import transaction\n")
    f.write("        from .models import Material, MovimientoInventario\n")
    f.write("        from activos.models import Ubicacion\n")
    f.write("        with transaction.atomic():\n")
    f.write("            for mov_data in queue:\n")
    f.write("                try:\n")
    f.write("                    material_id = mov_data.get('material_id')\n")
    f.write("                    tipo = mov_data.get('tipo', 'ENTRADA').upper()\n")
    f.write("                    cantidad = Decimal(str(mov_data.get('cantidad', 0)))\n")
    f.write("                    ubicacion_id = mov_data.get('ubicacion_id')\n")
    f.write("                    comentarios = mov_data.get('comentarios', 'Registro Offline (Sincronizado)')\n")
    f.write("                    if not material_id or not ubicacion_id or cantidad <= 0: raise ValueError('Datos inválidos')\n")
    f.write("                    material = Material.objects.get(id=material_id)\n")
    f.write("                    ubicacion = Ubicacion.objects.get(id=ubicacion_id)\n")
    f.write("                    movimiento = MovimientoInventario(material=material, tipo=tipo, cantidad=cantidad, usuario=request.user, comentarios=comentarios)\n")
    f.write("                    if tipo == 'ENTRADA': movimiento.ubicacion_destino = ubicacion\n")
    f.write("                    elif tipo == 'SALIDA': movimiento.ubicacion_origen = ubicacion\n")
    f.write("                    else: movimiento.ubicacion_destino = ubicacion\n")
    f.write("                    movimiento.save()\n")
    f.write("                    movimiento.liquidar(request.user)\n")
    f.write("                    procesados += 1\n")
    f.write("                except Exception as e: errores.append({'item': mov_data, 'error': str(e)})\n")
    f.write("        return JsonResponse({'status': 'success', 'message': f'{procesados} movimientos sincronizados', 'errores': errores})\n")
    f.write("    except Exception as e: return JsonResponse({'status': 'error', 'message': str(e)}, status=500)\n")
