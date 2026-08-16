import json
import re
from datetime import datetime
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from ..models import OrdenTrabajo, Programacion, NotificacionMantenimiento, Aviso, CierreOrdenTrabajo, ArchivoOrdenTrabajo, ValorPasoOrden
from activos.models import Activo, Ubicacion, DocumentoMedicion
from django.utils import timezone

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
    ).select_related('ubicacion').distinct().only(
        'id', 'codigo_de_orden', 'descripcion_corta', 'ubicacion__nombre', 'estado'
    )[:30]
    
    results = []
    for ot in ots:
        lugar = ot.ubicacion.nombre if ot.ubicacion else "Sin Ubicación"
        desc = ot.descripcion_corta or ("Sin descripción" if not ot.id else f"OT #{ot.id}")
        estado = ot.get_estado_display() if hasattr(ot, 'get_estado_display') else ot.estado
        text = f"OT #{ot.id if not ot.codigo_de_orden else ot.codigo_de_orden} - [{estado}] {lugar} - {desc}"
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
    ot = get_object_or_404(OrdenTrabajo.objects.select_related('rutina', 'ubicacion', 'tecnico', 'tecnico_puesto', 'programacion', 'aviso', 'empresa_responsable').prefetch_related('activos', 'archivos'), pk=pk)

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
        'tipo_raw': ot.tipo,
        'prioridad': ot.get_prioridad_display(),
        'prioridad_raw': ot.prioridad,
        'estado': ot.get_estado_display(),
        'rutina': ot.rutina.nombre if ot.rutina else (f"Aviso #{ot.aviso.id}" if ot.aviso else "OT Correctiva"),
        'rutina_id': ot.rutina_id,
        'ubicacion': ot.ubicacion.get_ruta_completa() if (ot.ubicacion and hasattr(ot.ubicacion, 'get_ruta_completa')) else (str(ot.ubicacion) if ot.ubicacion else 'No especificada'),
        'ubicacion_id': ot.ubicacion_id,
        'tecnico': ot.tecnico.get_full_name() or ot.tecnico.username if ot.tecnico else None,
        'tecnico_puesto': str(ot.tecnico_puesto) if ot.tecnico_puesto else None,
        'empresa': str(ot.empresa_responsable) if ot.empresa_responsable else None,
        'inicio': ot.inicio_programado.strftime('%d/%m/%Y %H:%M') if ot.inicio_programado else 'Sin fecha',
        'fin': ot.fin_programado.strftime('%d/%m/%Y %H:%M') if ot.fin_programado else 'Sin fecha',
        'descripcion': ot.descripcion_corta or '',
        'notas': ot.notas or '',
        'activos': activos,
        'status_color': get_status_color(ot.estado),
        'raw_status': ot.estado,
        'status_list': [{'id': k, 'label': v} for k, v in OrdenTrabajo.ESTADO_CHOICES],
        'archivos': archivos,
    }
    return JsonResponse({'status': 'success', 'ot': data})


@staff_member_required
def api_get_ot_related(request, pk):
    """
    Retorna órdenes relacionadas a una OT por rutina, activos o ubicación.
    """
    ot = get_object_or_404(OrdenTrabajo.objects.select_related('rutina', 'ubicacion').prefetch_related('activos'), pk=pk)
    
    related_qs = OrdenTrabajo.objects.exclude(id=ot.id).select_related('rutina', 'ubicacion').order_by('-inicio_programado')
    
    reasons = {}  # ot_id -> list of reasons
    
    # By same rutina
    if ot.rutina_id:
        for r in related_qs.filter(rutina_id=ot.rutina_id)[:50]:
            reasons.setdefault(r.id, []).append('rutina')
    
    # By same activos
    activo_ids = list(ot.activos.values_list('id', flat=True))
    if activo_ids:
        for r in related_qs.filter(activos__id__in=activo_ids).distinct()[:30]:
            reasons.setdefault(r.id, []).append('activo')
    
    # By same ubicacion OR parent edificio
    if ot.ubicacion_id:
        ubi_ids = [ot.ubicacion_id]
        try:
            ubi = ot.ubicacion
            if hasattr(ubi, 'get_ancestors'):
                ancestors = ubi.get_ancestors(include_self=True)
                building = ancestors.filter(tipo='EDIFICIO').first()
                if building and hasattr(building, 'get_descendants'):
                    ubi_ids = list(building.get_descendants(include_self=True).values_list('id', flat=True))
        except Exception:
            pass
        for r in related_qs.filter(ubicacion_id__in=ubi_ids).exclude(id__in=list(reasons.keys()))[:30]:
            reasons.setdefault(r.id, []).append('ubicación')
    
    # Fetch all unique related OTs
    all_related_ids = list(reasons.keys())[:50]
    if not all_related_ids:
        return JsonResponse({'status': 'success', 'related': []})
    
    related_ots = OrdenTrabajo.objects.filter(id__in=all_related_ids).select_related('rutina', 'ubicacion').order_by('-inicio_programado')
    
    result = []
    for r in related_ots:
        result.append({
            'id': r.id,
            'codigo': r.codigo_de_orden or f"OT #{r.id}",
            'estado': r.get_estado_display(),
            'estado_raw': r.estado,
            'rutina': r.rutina.nombre if r.rutina else '-',
            'ubicacion': str(r.ubicacion) if r.ubicacion else '-',
            'inicio': r.inicio_programado.strftime('%d/%m/%Y') if r.inicio_programado else '-',
            'motivos': reasons.get(r.id, []),
            'status_color': get_status_color(r.estado),
        })
    
    return JsonResponse({'status': 'success', 'related': result})

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
        Q(epc__icontains=query) |
        Q(descripcion__icontains=query) |
        Q(modelo__nombre__icontains=query) |
        Q(modelo_legacy__icontains=query)
    ).select_related(
        'ubicacion',
        'modelo',
        'modelo__marca',
        'modelo__categoria',
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

@staff_member_required
def api_busqueda_global(request):
    """
    Búsqueda global en el dashboard de mantenimiento.
    Busca en OTs, Avisos y Activos.
    """
    query = request.GET.get('q', '').strip()
    if not query or len(query) < 2:
        return JsonResponse({'results': []})

    from django.db.models import Q

    # 1. Buscar Órdenes de Trabajo
    ots = OrdenTrabajo.objects.filter(
        Q(id__icontains=query) |
        Q(codigo_de_orden__icontains=query) |
        Q(descripcion_corta__icontains=query) |
        Q(ubicacion__nombre__icontains=query) |
        Q(activos__nombre__icontains=query) |
        Q(activos__codigo_interno__icontains=query)
    ).select_related('ubicacion').distinct()[:8]

    ot_results = []
    for ot in ots:
        lugar = ot.ubicacion.nombre if ot.ubicacion else ""
        ot_results.append({
            'id': ot.id,
            'type': 'ot',
            'type_label': 'OT',
            'title': ot.codigo_de_orden or f"OT #{ot.id}",
            'subtitle': ot.descripcion_corta or "",
            'meta': lugar,
            'url': f"/admin/mantenimiento/ordentrabajo/{ot.id}/change/",
            'estado': ot.get_estado_display(),
            'estado_class': ot.estado.lower(),
        })

    # 2. Buscar Avisos
    avisos = Aviso.objects.filter(
        Q(id__icontains=query) |
        Q(descripcion__icontains=query) |
        Q(ubicacion__nombre__icontains=query) |
        Q(activo__nombre__icontains=query) |
        Q(solicitante__username__icontains=query) |
        Q(solicitante__first_name__icontains=query)
    ).select_related('ubicacion', 'activo').distinct()[:8]

    aviso_results = []
    for aviso in avisos:
        aviso_results.append({
            'id': aviso.id,
            'type': 'aviso',
            'type_label': 'Aviso',
            'title': f"AV-{aviso.id}",
            'subtitle': aviso.descripcion[:100],
            'meta': aviso.ubicacion.nombre if aviso.ubicacion else "",
            'url': f"/admin/mantenimiento/aviso/{aviso.id}/change/",
            'estado': aviso.get_estado_display(),
            'estado_class': aviso.estado.lower(),
        })

    # 3. Buscar Activos (limitado)
    activos = Activo.objects.filter(
        Q(nombre__icontains=query) |
        Q(codigo_interno__icontains=query) |
        Q(serie__icontains=query)
    )[:5]

    activo_results = []
    for a in activos:
        activo_results.append({
            'id': a.id,
            'type': 'activo',
            'type_label': 'Activo',
            'title': a.nombre,
            'subtitle': a.codigo_interno or "",
            'meta': a.serie or "",
            'url': f"/admin/activos/activo/{a.id}/change/",
            'estado': "",
            'estado_class': "",
        })

    return JsonResponse({
        'results': ot_results + aviso_results + activo_results,
        'total_ots': len(ot_results),
        'total_avisos': len(aviso_results),
        'total_activos': len(activo_results),
    })

@staff_member_required
def api_ordenes_hoy(request):
    """
    API que retorna OTs del día filtradas por búsqueda y tipo.
    """
    from django.utils import timezone
    from django.db.models import Q

    today = timezone.now().date()
    q = request.GET.get('q', '').strip()
    tipo = request.GET.get('tipo', '').strip()

    # Base: OTs del día activas + NO_PROGRAMADA (sin filtro de fecha)
    base_qs = OrdenTrabajo.objects.filter(
        Q(inicio_programado__date=today, estado__in=['ESPERA', 'PROGRAMADA', 'EJECUCION']) |
        Q(tipo='NO_PROGRAMADA')
    ).select_related('rutina', 'aviso', 'ubicacion', 'tecnico')

    # Si hay búsqueda numérica (ID) o por código específico,
    # buscar sin filtrar por fecha para encontrar OTs antiguas
    es_busqueda_especifica = bool(re.match(r'^[\d\-]+$', q)) if q else False

    if q and es_busqueda_especifica:
        base_qs = OrdenTrabajo.objects.filter(
            Q(id__icontains=q) |
            Q(codigo_de_orden__icontains=q)
        ).select_related('rutina', 'aviso', 'ubicacion', 'tecnico')
    elif q:
        base_qs = base_qs.filter(
            Q(id__icontains=q) |
            Q(codigo_de_orden__icontains=q) |
            Q(descripcion_corta__icontains=q) |
            Q(ubicacion__nombre__icontains=q) |
            Q(rutina__nombre__icontains=q)
        )

    if tipo and not es_busqueda_especifica:
        base_qs = base_qs.filter(tipo=tipo)

    ots = base_qs.order_by('-inicio_programado')[:20]
    if not es_busqueda_especifica:
        ots = base_qs.order_by('inicio_programado')[:20]

    resultados = []
    for ot in ots:
        resultados.append({
            'id': ot.id,
            'codigo': ot.codigo_de_orden or f"OT #{ot.id}",
            'descripcion': ot.rutina.nombre if ot.rutina else (ot.descripcion_corta or "OT Correctiva"),
            'ubicacion': ot.ubicacion.nombre if ot.ubicacion else "",
            'tecnico': ot.tecnico.get_full_name() or ot.tecnico.username if ot.tecnico else "N/A",
            'estado': ot.get_estado_display(),
            'estado_class': ot.estado.lower(),
            'hora': ot.inicio_programado.strftime('%H:%M') if ot.inicio_programado else "",
            'fecha': ot.inicio_programado.strftime('%d/%m') if ot.inicio_programado and ot.inicio_programado.date() != today else "",
            'tipo': ot.tipo,
        })

    return JsonResponse({'ots': resultados, 'total': len(resultados), 'can_delete': request.user.is_superuser})

@staff_member_required
@require_POST
def api_cerrar_ot(request, pk):
    import json
    ot = get_object_or_404(OrdenTrabajo, pk=pk)
    if hasattr(ot, 'cierre') and ot.cierre:
        return JsonResponse({'status': 'error', 'message': 'Esta orden ya tiene un cierre registrado.'}, status=400)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'JSON inválido.'}, status=400)

    fecha_inicio = data.get('fecha_inicio')
    fecha_fin = data.get('fecha_fin')
    if not fecha_inicio or not fecha_fin:
        return JsonResponse({'status': 'error', 'message': 'Las fechas de inicio y fin son requeridas.'}, status=400)

    CierreOrdenTrabajo.objects.create(
        orden_trabajo=ot,
        fecha_inicio_real=datetime.strptime(fecha_inicio, '%Y-%m-%dT%H:%M'),
        fecha_fin_real=datetime.strptime(fecha_fin, '%Y-%m-%dT%H:%M'),
        horas_hombre=float(data.get('horas_hombre', 0)),
        comentarios=data.get('comentarios', ''),
        tecnico=request.user,
    )

    return JsonResponse({'status': 'success', 'message': 'Orden cerrada correctamente.'})

@staff_member_required
@require_POST
@csrf_exempt
def api_guardar_cierre(request, pk):
    try:
        ot = get_object_or_404(OrdenTrabajo, pk=pk)
        is_gerente = request.user.groups.filter(name='Gerentes').exists() or request.user.is_superuser

        if ot.estado == 'REALIZADA' and not is_gerente:
            return JsonResponse({'status': 'error', 'message': 'No tienes permiso para editar un cierre finalizado.'}, status=403)

        pasos = []
        if ot.rutina:
            pasos = ot.rutina.pasos.all()
        activo_principal = ot.activos.first()
        for paso in pasos:
            if paso.tipo_respuesta == 'MEDICION':
                punto = None
                if paso.punto_medicion_exacto:
                    punto = paso.punto_medicion_exacto
                elif paso.punto_medicion_codigo and activo_principal:
                    punto = activo_principal.puntos_medicion.filter(codigo=paso.punto_medicion_codigo).first()
                paso.punto_vinculado = punto

            valor_text = request.POST.get(f'paso_{paso.id}_text')
            valor_num = request.POST.get(f'paso_{paso.id}_num')
            valor_bool = request.POST.get(f'paso_{paso.id}_bool') == 'on'
            no_aplica = request.POST.get(f'paso_{paso.id}_na') == 'on'
            comentarios = request.POST.get(f'paso_{paso.id}_com')

            if paso.tipo_respuesta == 'FOTO':
                fotos_paso = request.FILES.getlist(f'paso_{paso.id}_fotos')
                for foto in fotos_paso:
                    ArchivoOrdenTrabajo.objects.create(
                        orden_trabajo=ot, paso=paso, archivo=foto,
                        subido_por=request.user, tipo='IMAGEN'
                    )
                if fotos_paso:
                    valor_text = f"{len(fotos_paso)} foto(s) adjuntada(s)"

            if valor_text or valor_num or valor_bool or no_aplica or paso.tipo_respuesta in ('MEDICION', 'FOTO'):
                ValorPasoOrden.objects.update_or_create(
                    orden_trabajo=ot, paso=paso,
                    defaults={
                        'valor_texto': valor_text,
                        'valor_numerico': float(valor_num) if valor_num else None,
                        'valor_bool': valor_bool,
                        'no_aplica': no_aplica,
                        'comentarios': comentarios,
                        'capturado_por': request.user,
                    }
                )
                if paso.tipo_respuesta == 'MEDICION' and valor_num and not no_aplica:
                    punto = getattr(paso, 'punto_vinculado', None)
                    if punto:
                        DocumentoMedicion.objects.create(
                            punto=punto, valor=float(valor_num),
                            tecnico=request.user, orden_trabajo=ot,
                            observaciones=f"Capturado vía checklist OT #{ot.id}"
                        )

        activos = ot.activos.all().prefetch_related('puntos_medicion')
        puntos_ids = [p.punto_vinculado.id for p in pasos if getattr(p, 'tipo_respuesta', None) == 'MEDICION' and getattr(p, 'punto_vinculado', None)]
        for a in activos:
            for punto in a.puntos_medicion.all():
                if punto.id not in puntos_ids:
                    valor_lectura = request.POST.get(f'punto_{punto.id}')
                    if valor_lectura:
                        DocumentoMedicion.objects.create(
                            punto=punto, valor=float(valor_lectura),
                            tecnico=request.user, orden_trabajo=ot,
                            observaciones=f"Capturado durante cierre de OT #{ot.id}"
                        )

        for foto in request.FILES.getlist('fotos_inicio'):
            ArchivoOrdenTrabajo.objects.create(
                orden_trabajo=ot, archivo=foto,
                subido_por=request.user, momento='INICIO'
            )

        for foto in request.FILES.getlist('fotos_cierre'):
            ArchivoOrdenTrabajo.objects.create(
                orden_trabajo=ot, archivo=foto,
                subido_por=request.user, momento='CIERRE'
            )

        comentarios_cierre = request.POST.get('comentarios_cierre', '').strip()
        if comentarios_cierre:
            prefix = '[Edición]' if ot.estado == 'REALIZADA' else '[Cierre]'
            nueva_nota = f"\n{prefix} {comentarios_cierre}"
            ot.notas = (ot.notas or '') + nueva_nota
            ot.save(update_fields=['notas'])

        accion = request.POST.get('action')
        if accion == 'finalize' or (ot.estado == 'REALIZADA' and is_gerente):
            fecha_cierre_str = request.POST.get('fecha_cierre')
            fecha_cierre = timezone.now()
            if fecha_cierre_str:
                try:
                    fecha_cierre = timezone.make_aware(datetime.fromisoformat(fecha_cierre_str))
                except Exception:
                    pass

            if ot.estado != 'REALIZADA':
                ot.estado = 'REALIZADA'
                ot.fecha_ejecucion = fecha_cierre
            ot.save()

            if not hasattr(ot, 'cierre') or not ot.cierre:
                CierreOrdenTrabajo.objects.create(
                    orden_trabajo=ot,
                    tecnico=request.user,
                    fecha_inicio_real=fecha_cierre,
                    fecha_fin_real=fecha_cierre,
                    horas_hombre=0,
                    comentarios=request.POST.get('comentarios_cierre', ''),
                )

            try:
                from .mobile import task_generar_ot_pdf
                task_generar_ot_pdf.delay(ot.id)
            except Exception:
                pass
            return JsonResponse({'status': 'success', 'message': 'Orden finalizada correctamente.'})

        ot.save()
        return JsonResponse({'status': 'success', 'message': 'Borrador guardado correctamente.'})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
