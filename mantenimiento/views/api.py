import json
from datetime import datetime
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from ..models import OrdenTrabajo, Programacion, NotificacionMantenimiento
from activos.models import Activo, Ubicacion

@staff_member_required
@require_POST
@csrf_exempt
def api_update_ot_date(request):
    try:
        data = json.loads(request.body)
        ot_id = str(data.get('ot_id', ''))
        nueva_fecha_str = data.get('nueva_fecha')
        if not ot_id or not nueva_fecha_str:
            return JsonResponse({'status': 'error', 'message': 'Datos incompletos'}, status=400)
        
        nueva_date = datetime.strptime(nueva_fecha_str, '%Y-%m-%d').date()

        # Caso 1: Es una proyecciÃ³n (Ghost OT)
        if ot_id.startswith('proj_'):
            # Formato: proj_programacionId_fechaOriginal
            parts = ot_id.split('_')
            if len(parts) < 3:
                return JsonResponse({'status': 'error', 'message': 'ID de proyecciÃ³n invÃ¡lido'}, status=400)
            
            prog_id = parts[1]
            fecha_orig_str = parts[2]
            prog = Programacion.objects.get(id=prog_id)
            fecha_orig = datetime.strptime(fecha_orig_str, '%Y-%m-%d').date()
            
            # Generar la orden para esa fecha (esto la convierte en real)
            prog.generar_ordenes(fecha_corte=fecha_orig)
            
            # Buscar las OTs reciÃ©n creadas para moverlas a la nueva fecha
            ots = OrdenTrabajo.objects.filter(programacion=prog, inicio_programado__date=fecha_orig)
            if not ots.exists():
                return JsonResponse({'status': 'error', 'message': 'No se pudo generar la orden para moverla.'}, status=400)
            
            delta = nueva_date - fecha_orig
            for ot in ots:
                ot.inicio_programado += delta
                if ot.fin_programado: ot.fin_programado += delta
                ot.save()
            return JsonResponse({'status': 'success', 'message': f'ProyecciÃ³n generada y movida al {nueva_fecha_str}'})

        # Caso 2: Es una OT real
        ot = OrdenTrabajo.objects.get(id=ot_id)
        delta = nueva_date - ot.inicio_programado.date()
        ot.inicio_programado = ot.inicio_programado + delta
        if ot.fin_programado:
            ot.fin_programado = ot.fin_programado + delta
        ot.save()
        return JsonResponse({'status': 'success', 'message': f'Orden #{ot_id} movida al {nueva_fecha_str}'})
    except OrdenTrabajo.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Orden no encontrada'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@staff_member_required
@require_POST
@csrf_exempt
def api_split_ot_asset(request):
    try:
        data = json.loads(request.body)
        ot_id = data.get('ot_id'); asset_id = data.get('asset_id')
        if not ot_id or not asset_id: return JsonResponse({'status': 'error', 'message': 'Datos incompletos'}, status=400)
        ot = OrdenTrabajo.objects.prefetch_related('activos').get(id=ot_id)
        if ot.activos.count() <= 1: return JsonResponse({'status': 'error', 'message': 'La orden solo tiene un activo.'}, status=400)
        asset = Activo.objects.get(id=asset_id)
        new_ot = OrdenTrabajo.objects.create(tipo=ot.tipo, prioridad=ot.prioridad, rutina=ot.rutina, aviso=ot.aviso, tecnico=ot.tecnico, ubicacion=ot.ubicacion, programacion=ot.programacion, planificacion=ot.planificacion, inicio_programado=ot.inicio_programado, fin_programado=ot.fin_programado, estado=ot.estado, notas=f"Sep. de OT #{ot_id}")
        new_ot.activos.add(asset); ot.activos.remove(asset)
        if ot.rutina and ot.rutina.tiempo_estimado:
            t = ot.rutina.tiempo_estimado
            ot.fin_programado = ot.inicio_programado + (t * ot.activos.count())
            new_ot.fin_programado = new_ot.inicio_programado + t
            ot.save(); new_ot.save()
        return JsonResponse({'status': 'success', 'message': f'Activo separado en OT #{new_ot.id}'})
    except Exception as e: return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@staff_member_required
@require_POST
@csrf_exempt
def api_merge_ots(request):
    try:
        data = json.loads(request.body); ot_ids = data.get('ot_ids', [])
        if not ot_ids or len(ot_ids) < 2: return JsonResponse({'status': 'error', 'message': 'Se requieren 2 órdenes.'}, status=400)
        ots = list(OrdenTrabajo.objects.filter(id__in=ot_ids).prefetch_related('activos'))
        master_ot = ots[0]; other_ots = ots[1:]; notes = [master_ot.notas] if hasattr(master_ot, 'notas') and master_ot.notas else []
        for ot in other_ots:
            for a in ot.activos.all(): master_ot.activos.add(a)
            if hasattr(ot, 'notas') and ot.notas: notes.append(ot.notas)
            ot.delete()
        if hasattr(master_ot, 'notas'): master_ot.notas = "\n".join(notes)
        if master_ot.rutina and master_ot.rutina.tiempo_estimado:
            master_ot.fin_programado = master_ot.inicio_programado + (master_ot.rutina.tiempo_estimado * master_ot.activos.count())
        master_ot.save()
        return JsonResponse({'status': 'success', 'message': f'Fusionadas en OT #{master_ot.id}'})
    except Exception as e: return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@staff_member_required
@require_POST
@csrf_exempt
def api_bulk_update_ot_dates(request):
    try:
        data = json.loads(request.body); ot_ids = data.get('ot_ids', []); nf = data.get('nueva_fecha')
        if not ot_ids or not nf: return JsonResponse({'status': 'error', 'message': 'Incompleto'}, status=400)
        nueva_fecha = datetime.strptime(nf, '%Y-%m-%d').date(); count = 0
        for oid in ot_ids:
            oid = str(oid)
            try:
                if oid.startswith('proj_'):
                    parts = oid.split('_')
                    if len(parts) < 3: continue
                    prog_id = parts[1]; fecha_orig = datetime.strptime(parts[2], '%Y-%m-%d').date()
                    prog = Programacion.objects.get(id=prog_id)
                    prog.generar_ordenes(fecha_corte=fecha_orig)
                    ots = OrdenTrabajo.objects.filter(programacion=prog, inicio_programado__date=fecha_orig)
                    delta = nueva_fecha - fecha_orig
                    for ot in ots:
                        ot.inicio_programado += delta
                        if ot.fin_programado: ot.fin_programado += delta
                        ot.save(); count += 1
                else:
                    ot = OrdenTrabajo.objects.get(id=oid); delta = nueva_fecha - ot.inicio_programado.date()
                    ot.inicio_programado += delta
                    if ot.fin_programado: ot.fin_programado += delta
                    ot.save(); count += 1
            except: continue
        return JsonResponse({'status': 'success', 'message': f'{count} movidas.'})
    except Exception as e: return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@staff_member_required
def api_get_notifications(request):
    notifs = NotificacionMantenimiento.objects.filter(user=request.user, leida=False)
    return JsonResponse({'status': 'success', 'notificaciones': [{'id': n.id, 'mensaje': n.mensaje, 'tipo': n.tipo, 'creado_en': n.creado_en.strftime('%H:%M:%S')} for n in notifs]})

@staff_member_required
def api_delete_ots(request):
    if request.method != 'POST': return JsonResponse({'status': 'error', 'message': 'POST req.'}, status=405)
    try:
        data = json.loads(request.body); ids = data.get('ot_ids', [])
        ots = OrdenTrabajo.objects.filter(id__in=ids, estado__in=['ESPERA', 'PROGRAMADA'])
        c = ots.count(); ots.delete()
        return JsonResponse({'status': 'success', 'message': f'{c} eliminadas.'})
    except Exception as e: return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@staff_member_required
@require_POST
@csrf_exempt
def api_mark_notification_read(request):
    try:
        nid = json.loads(request.body).get('notif_id')
        if nid: NotificacionMantenimiento.objects.filter(id=nid, user=request.user).update(leida=True)
        else: NotificacionMantenimiento.objects.filter(user=request.user, leida=False).update(leida=True)
        return JsonResponse({'status': 'success'})
    except Exception as e: return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@staff_member_required
def api_get_assets_wizard(request):
    a_ids = request.GET.getlist('areas[]')
    c_ids = request.GET.getlist('categorias[]')
    rutina_id = request.GET.get('rutina_id')
    
    all_areas = set()
    for aid in a_ids:
        try:
            all_areas.update(Ubicacion.objects.get(id=aid).get_descendants(include_self=True).values_list('id', flat=True))
        except:
            continue
            
    f = {}
    if all_areas:
        f['ubicacion_id__in'] = all_areas
        
    # Categorize filters
    all_cats = set()
    from activos.models import Categoria as CA
    
    # 1. Manually selected categories
    for cid in c_ids:
        try:
            all_cats.update(CA.objects.get(id=cid).get_descendants(include_self=True).values_list('id', flat=True))
        except:
            continue
            
    # 2. Category from Routine
    if rutina_id:
        from ..models import Rutina
        try:
            rutina = Rutina.objects.get(id=rutina_id)
            if rutina.categoria:
                # Get all asset categories linked to this routine category or its subcategories
                r_cats = rutina.categoria.get_descendants(include_self=True)
                asset_cats_ids = [rc.categoria_activo_id for rc in r_cats if rc.categoria_activo_id]
                for acid in asset_cats_ids:
                    try:
                        all_cats.update(CA.objects.get(id=acid).get_descendants(include_self=True).values_list('id', flat=True))
                    except:
                        continue
        except Rutina.DoesNotExist:
            pass
            
    if all_cats:
        f['modelo__categoria_id__in'] = all_cats
        
    activos = Activo.objects.filter(**f).select_related('ubicacion', 'modelo__categoria')[:200]
    return JsonResponse({
        'status': 'success', 
        'activos': [{
            'id': a.id, 
            'nombre': a.nombre, 
            'codigo': a.codigo_interno or a.serie or 'S/C', 
            'ubicacion': a.ubicacion.nombre if a.ubicacion else 'S/U', 
            'categoria': a.modelo.categoria.nombre if a.modelo and a.modelo.categoria else 'S/C'
        } for a in activos]
    })

@staff_member_required
def generar_ordenes_programacion(request, pk):
    if request.method != 'POST': return JsonResponse({'status': 'error', 'message': 'POST req.'}, status=405)
    prog = get_object_or_404(Programacion, pk=pk)
    try:
        c = prog.generar_ordenes()
        return JsonResponse({'status': 'success', 'count': c, 'message': f'Se generaron {c} órdenes.'})
    except Exception as e: return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@staff_member_required
def api_generar_orden_individual(request):
    if request.method != 'POST': return JsonResponse({'status': 'error', 'message': 'POST req.'}, status=405)
    try:
        data = json.loads(request.body); pid = data.get('prog_id'); dstr = data.get('fecha')
        if not pid or not dstr: return JsonResponse({'status': 'error', 'message': 'Incompleto'}, status=400)
        prog = get_object_or_404(Programacion, pk=pid)
        fc = datetime.strptime(dstr, '%Y-%m-%d').date()
        c = prog.generar_ordenes(fecha_corte=fc)
        return JsonResponse({'status': 'success', 'count': c, 'message': f'Se generaron {c} órdenes.'})
    except Exception as e: return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
