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
        data = json.loads(request.body)
        raw_ids = data.get('ot_ids', [])
        
        # Limpiar IDs de cualquier formato de miles/decimales (comas o puntos)
        ids = []
        for rid in raw_ids:
            if isinstance(rid, str):
                cleaned = rid.replace(',', '').replace('.', '')
                if cleaned.isdigit(): ids.append(int(cleaned))
            elif isinstance(rid, (int, float)):
                ids.append(int(rid))

        ots = OrdenTrabajo.objects.filter(id__in=ids, estado__in=['ESPERA', 'PROGRAMADA', 'EJECUCION'])
        c = ots.count()
        ots.delete()
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
            if rutina.tipo:
                # Get all asset categories linked to this routine tipo or its subtypes
                r_cats = rutina.tipo.get_descendants(include_self=True)
                asset_cats_ids = [rc.categoria_activo_id for rc in r_cats if rc.categoria_activo_id]
                for acid in asset_cats_ids:
                    try:
                        all_cats.update(CA.objects.get(id=acid).get_descendants(include_self=True).values_list('id', flat=True))
                    except:
                        continue
        except Rutina.DoesNotExist:
            pass
            
    if not all_cats:
        return JsonResponse({'status': 'success', 'activos': []})
        
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
@staff_member_required
def api_search_ordenes(request):
    """
    Busca órdenes de trabajo activas (PROGRAMADA, EJECUCION) por ID, código o descripción.
    Optimizado para evitar cargar miles de opciones en un select estático.
    """
    query = request.GET.get('q', '').strip()
    if not query:
        return JsonResponse({'results': []})
    
    from django.db.models import Q
    ots = OrdenTrabajo.objects.filter(
        Q(id__icontains=query) | 
        Q(codigo_de_orden__icontains=query) |
        Q(descripcion_corta__icontains=query) |
        Q(ubicacion__nombre__icontains=query) |
        Q(activos__nombre__icontains=query) |
        Q(activos__codigo_interno__icontains=query)
    ).filter(
        estado__in=['PROGRAMADA', 'EJECUCION']
    ).select_related('ubicacion').distinct().only(
        'id', 'codigo_de_orden', 'descripcion_corta', 'ubicacion__nombre'
    )[:30]
    
    results = []
    for ot in ots:
        lugar = ot.ubicacion.nombre if ot.ubicacion else "Sin Ubicación"
        desc = ot.descripcion_corta or ("Sin descripción" if not ot.id else f"OT #{ot.id}")
        text = f"OT #{ot.id if not ot.codigo_de_orden else ot.codigo_de_orden} - {lugar} - {desc}"
        results.append({
            'id': ot.id,
            'text': text
        })
    
    return JsonResponse({'results': results})

@staff_member_required
def api_get_ot_detail(request, pk):
    """
    Retorna detalles de una OT para mostrar en modal (Dashboard/Cronograma).
    """
    ot = get_object_or_404(OrdenTrabajo.objects.select_related('rutina', 'ubicacion', 'tecnico', 'programacion', 'aviso').prefetch_related('activos', 'archivos'), pk=pk)

    activos = [{"id": a.id, "nombre": a.nombre, "codigo": a.codigo_interno} for a in ot.activos.all()]
    archivos = [{
        "id": a.id,
        "nombre": a.nombre,
        "tipo": a.tipo,
        "url": a.archivo.url,
        "momento": a.momento,
    } for a in ot.archivos.all()]
    
    data = {
        'id': ot.id,
        'codigo': ot.codigo_de_orden or f"OT #{ot.id}",
        'tipo': ot.get_tipo_display(),
        'prioridad': ot.get_prioridad_display(),
        'estado': ot.get_estado_display(),
        'rutina': ot.rutina.nombre if ot.rutina else (f"Aviso #{ot.aviso.id}" if ot.aviso else "OT Correctiva"),
        'ubicacion': ot.ubicacion.get_ruta_completa() if (ot.ubicacion and hasattr(ot.ubicacion, 'get_ruta_completa')) else (str(ot.ubicacion) if ot.ubicacion else 'No especificada'),
        'tecnico': ot.tecnico.get_full_name() or ot.tecnico.username if ot.tecnico else 'No asignado',
        'inicio': ot.inicio_programado.strftime('%d/%m/%Y %H:%M') if ot.inicio_programado else 'Sin fecha',
        'fin': ot.fin_programado.strftime('%d/%m/%Y %H:%M') if ot.fin_programado else 'Sin fecha',
        'notas': ot.notas or ot.descripcion_corta or 'Sin observaciones adicionales.',
        'activos': activos,
        'status_color': get_status_color(ot.estado),
        'raw_status': ot.estado,
        'status_list': [{'id': k, 'label': v} for k, v in OrdenTrabajo.ESTADO_CHOICES],
        'archivos': archivos,
    }
    return JsonResponse({'status': 'success', 'ot': data})

@staff_member_required
@require_POST
@csrf_exempt
def api_update_ot_status_notes(request, pk):
    """
    Actualiza el estado y las notas de una OT desde el modal del cronograma.
    """
    try:
        ot = get_object_or_404(OrdenTrabajo, pk=pk)
        data = json.loads(request.body)
        
        nuevo_estado = data.get('estado')
        nuevas_notas = data.get('notas')
        
        if nuevo_estado:
            # Validar que sea un estado permitido
            if nuevo_estado in dict(OrdenTrabajo.ESTADO_CHOICES):
                ot.estado = nuevo_estado
                if nuevo_estado == 'EJECUCION' and not ot.fecha_ejecucion:
                    ot.fecha_ejecucion = timezone.now()
            else:
                return JsonResponse({'status': 'error', 'message': f'Estado {nuevo_estado} no válido'}, status=400)
        
        if nuevas_notas is not None:
            ot.notas = nuevas_notas
            
        ot.save()
        return JsonResponse({'status': 'success', 'message': 'Orden actualizada correctamente'})
        
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'JSON inválido'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

def get_status_color(estado):
    colors = {
        'PROGRAMADA': '#3b82f6',
        'EJECUCION': '#f59e0b',
        'REALIZADA': '#10b981',
        'CANCELADA': '#ef4444',
        'ESPERA': '#64748b'
    }

@staff_member_required
def api_buscar_activos(request):
    """
    Busca activos por nombre, código o serie.
    """
    query = request.GET.get('q', '').strip()
    if not query:
        return JsonResponse({'results': []})
    
    from django.db.models import Q
    activos = Activo.objects.filter(
        Q(nombre__icontains=query) | 
        Q(codigo_interno__icontains=query) |
        Q(serie__icontains=query) |
        Q(epc__icontains=query)
    ).select_related('ubicacion').only(
        'id', 'nombre', 'codigo_interno', 'ubicacion__id', 'ubicacion__nombre'
    )[:30]
    
    results = []
    for a in activos:
        codigo = a.codigo_interno or "S/C"
        lugar = a.ubicacion.nombre if a.ubicacion else "Sin Ubicación"
        lugar_id = a.ubicacion.id if a.ubicacion else None
        
        # Nuevos campos para el detalle
        modelo_nombre = a.modelo.nombre if a.modelo else (a.modelo_legacy or "S/M")
        marca_nombre = a.modelo.marca.nombre if (a.modelo and a.modelo.marca) else (a.marca_legacy or "S/M")
        categoria_nombre = a.modelo.categoria.nombre if (a.modelo and a.modelo.categoria) else "S/C"
        
        results.append({
            'id': a.id,
            'text': f"{a.nombre} [{codigo}]",
            'ubicacion_id': lugar_id,
            'ubicacion_nombre': lugar,
            'marca': marca_nombre,
            'modelo': modelo_nombre,
            'categoria': categoria_nombre,
            'serie': a.serie or "S/S"
        })
    return JsonResponse({'results': results})

@staff_member_required
def api_buscar_activos_filtrados(request):
    """
    Busca activos filtrados por ubicación y categoría.
    Especialmente para el flujo de inicio de rutinas desde QR móvil.
    """
    ubicacion_id = request.GET.get('ubicacion_id')
    rutina_id = request.GET.get('rutina_id')
    query = request.GET.get('q', '').strip()

    if not ubicacion_id or not rutina_id:
        return JsonResponse({'results': []})

    from ..models import Rutina
    try:
        rutina = Rutina.objects.get(id=rutina_id)
        # Determinar la categoría (prioridad: rutina -> tipo)
        categoria = rutina.categoria_activo
        if not categoria and rutina.tipo:
            categoria = rutina.tipo.categoria_activo
        
        if not categoria:
            return JsonResponse({'results': []})

        from django.db.models import Q
        from activos.models import Ubicacion
        
        # Obtener todos los descendientes de la ubicación para el filtro
        try:
            ubi = Ubicacion.objects.get(id=ubicacion_id)
            descendant_ids = ubi.get_descendants(include_self=True).values_list('id', flat=True)
        except Ubicacion.DoesNotExist:
            return JsonResponse({'results': []})

        # Filtrar activos
        qs = Activo.objects.filter(
            ubicacion_id__in=descendant_ids,
            modelo__categoria=categoria
        )

        if query:
            qs = qs.filter(
                Q(nombre__icontains=query) |
                Q(codigo_interno__icontains=query) |
                Q(serie__icontains=query)
            )

        results = []
        for a in qs.select_related('ubicacion', 'modelo__marca', 'modelo__categoria')[:50]:
            results.append({
                'id': a.id,
                'nombre': a.nombre,
                'codigo': a.codigo_interno or a.serie or 'S/C',
                'ubicacion': a.ubicacion.nombre if a.ubicacion else 'S/U',
                'categoria': a.modelo.categoria.nombre if a.modelo and a.modelo.categoria else 'S/C',
                'marca_modelo': f"{a.modelo.marca.nombre if a.modelo and a.modelo.marca else ''} {a.modelo.nombre if a.modelo else ''}".strip()
            })

        return JsonResponse({'results': results})

    except Rutina.DoesNotExist:
        return JsonResponse({'results': []})

@require_POST
def api_update_foto_descripcion(request, pk):
    """
    Actualiza la descripción de una Foto de Aviso vía AJAX.
    """
    from ..models import FotoAviso
    try:
        foto = FotoAviso.objects.get(pk=pk)
        data = json.loads(request.body)
        descripcion = data.get('descripcion', '').strip()
        
        foto.descripcion = descripcion
        foto.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Descripción actualizada correctamente.'
        })
    except FotoAviso.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'La foto no existe.'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
