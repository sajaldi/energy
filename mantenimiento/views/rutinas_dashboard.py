from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse, Http404
from ..models import Tipo, Rutina, Frecuencia, PuestoTrabajo, PasoRutina, Horario, MediaPasoRutina
from activos.models import Categoria, Ubicacion
from django.db.models import Count, Q, Max
from django.template.loader import render_to_string
from django.utils import timezone
from django.conf import settings
from types import SimpleNamespace
import os
import base64
from playwright.sync_api import sync_playwright


def build_in_memory_tree(all_categories, all_rutinas, frecuencia_int, puesto_int, search, tipo_kpis_map=None):
    """
    Construye el árbol jerárquico totalmente en memoria sin consultas adicionales.
    """
    # 1. Agrupar rutinas por categoría
    rutinas_por_tipo = {}
    for r in all_rutinas:
        if r.tipo_id not in rutinas_por_tipo:
            rutinas_por_tipo[r.tipo_id] = []
        rutinas_por_tipo[r.tipo_id].append(r)

    # 2. Mapear categorías por padre
    hijos_por_padre = {}
    for cat in all_categories:
        padre_id = cat.padre_id
        if padre_id not in hijos_por_padre:
            hijos_por_padre[padre_id] = []
        hijos_por_padre[padre_id].append(cat)

    # 3. Función recursiva interna para construir nodos
    def construct_node(cat):
        sub_categories = hijos_por_padre.get(cat.id, [])
        rutinas_list = rutinas_por_tipo.get(cat.id, [])
        
        sub_tree = []
        for sub_cat in sub_categories:
            node = construct_node(sub_cat)
            if node:
                sub_tree.append(node)

        # Recopilar KPIs heredados (de esta categoría + ancestros)
        cat_kpis = []
        kpi_names = set()
        tip_curr = cat
        while tip_curr:
            if tipo_kpis_map and tip_curr.id in tipo_kpis_map:
                for k_id, k_name in tipo_kpis_map[tip_curr.id]:
                    if k_name not in kpi_names:
                        kpi_names.add(k_name)
                        cat_kpis.append({'id': k_id, 'nombre': k_name})
            tip_curr = tip_curr.padre if hasattr(tip_curr, 'padre') else None

        has_filters = frecuencia_int or puesto_int or search
        if rutinas_list or sub_tree or not has_filters:
            return {
                'categoria': cat,
                'rutinas': rutinas_list,
                'subcategorias': sub_tree,
                'level': cat.level,
                'categoria_kpis': cat_kpis,
            }
        return None

    # 4. Iniciar desde las raíces
    final_tree = []
    raices = hijos_por_padre.get(None, [])
    for root_cat in raices:
        node = construct_node(root_cat)
        if node:
            final_tree.append(node)
            
    return final_tree


@staff_member_required
def rutinas_dashboard(request):
    """Dashboard profesional para visualizar rutinas en formato de árbol jerárquico"""
    
    # Filtros
    frecuencia_id = request.GET.get('frecuencia')
    puesto_id = request.GET.get('puesto')
    search = request.GET.get('search', '').strip()
    
    # Convertir a int para facilitar comparación
    try:
        frecuencia_int = int(frecuencia_id) if frecuencia_id else None
    except ValueError:
        frecuencia_int = None
        
    try:
        puesto_int = int(puesto_id) if puesto_id else None
    except ValueError:
        puesto_int = None

    # --- OPTIMIZACIÓN: Carga masiva en memoria ---
    all_categories_qs = Tipo.objects.all().order_by('nombre')
    all_categories = list(all_categories_qs)
    
    # Pre-calcular rutas para búsqueda jerárquica
    cat_paths = {}
    cat_map = {c.id: c for c in all_categories}
    for c in all_categories:
        path = [c.nombre]
        curr = c.padre_id
        while curr and curr in cat_map:
            p_obj = cat_map[curr]
            path.append(p_obj.nombre)
            curr = p_obj.padre_id
        cat_paths[c.id] = " → ".join(reversed(path)).lower()

    all_rutinas_qs = Rutina.objects.all().select_related('frecuencia', 'puesto_trabajo', 'tipo', 'categoria_activo').prefetch_related('kpis')
    
    if frecuencia_int:
        all_rutinas_qs = all_rutinas_qs.filter(frecuencia_id=frecuencia_int)
    if puesto_int:
        all_rutinas_qs = all_rutinas_qs.filter(puesto_trabajo_id=puesto_int)
    
    # Filtrado manual para búsqueda jerárquica (incluyendo ruta de categoría)
    all_rutinas = []
    search_terms = [t.strip().lower() for t in search.split('+')] if search else []
    search_simple = search.lower() if search and '+' not in search else None
    for r in all_rutinas_qs:
        if search_terms and len(search_terms) > 1:
            # Modo multi-término: todos deben estar en el nombre (excluyente)
            name_lower = r.nombre.lower()
            if not all(term in name_lower for term in search_terms):
                continue
        elif search_simple:
            # Modo término único: busca en nombre, código, descripción y ruta
            path_matches = search_simple in cat_paths.get(r.tipo_id, "")
            name_matches = search_simple in r.nombre.lower()
            code_matches = r.codigo_rutina and search_simple in r.codigo_rutina.lower()
            desc_matches = r.descripcion and search_simple in r.descripcion.lower()
            if not (path_matches or name_matches or code_matches or desc_matches):
                continue
        all_rutinas.append(r)
    
    # Precalcular KPIs heredados por categoría (evitar N+1)
    from servicios.models import KPI
    tipo_kpis_map = {}
    tipo_ids_con_kpis = set(Tipo.objects.exclude(kpis=None).values_list('id', flat=True))
    for kpi in KPI.objects.filter(categorias_mantenimiento__in=tipo_ids_con_kpis).values('id', 'nombre', 'categorias_mantenimiento'):
        tid = kpi['categorias_mantenimiento']
        if tid not in tipo_kpis_map:
            tipo_kpis_map[tid] = []
        tipo_kpis_map[tid].append((kpi['id'], kpi['nombre']))

    tree = build_in_memory_tree(all_categories, all_rutinas, frecuencia_int, puesto_int, search, tipo_kpis_map)
    
    # Agregar rutinas sin categoría al final del árbol
    uncategorized = [r for r in all_rutinas if r.tipo_id is None]
    if uncategorized:
        sin_cat = SimpleNamespace(
            id=None, nombre="Sin Categoría", codigo=None,
            padre_id=None, level=0
        )
        tree.append({
            'categoria': sin_cat,
            'rutinas': uncategorized,
            'subcategorias': [],
            'level': 0
        })
    
    # Estadísticas y Datos para Formularios
    frecuencias = Frecuencia.objects.all().order_by('nombre')
    puestos = PuestoTrabajo.objects.all().order_by('nombre')
    total_rutinas = Rutina.objects.count()
    
    # Todas las categorías para el select de creación/edición (con pre-cálculo de ruta para evitar N+1)
    all_types = {t.id: t for t in Tipo.objects.all()}
    for t in all_types.values():
        path = [t.nombre]
        curr = t.padre_id
        while curr and curr in all_types:
            p_obj = all_types[curr]
            path.append(p_obj.nombre)
            curr = p_obj.padre_id
        t.temp_ruta_completa = " → ".join(reversed(path))
    todas_categorias = sorted(all_types.values(), key=lambda x: x.temp_ruta_completa)
    
    # Ubicaciones con pre-cálculo de ruta
    all_locs = {l.id: l for l in Ubicacion.objects.all()}
    for l in all_locs.values():
        path = [l.nombre]
        curr = l.padre_id
        while curr and curr in all_locs:
            p_obj = all_locs[curr]
            path.append(p_obj.nombre)
            curr = p_obj.padre_id
        l.temp_ruta_completa = " → ".join(reversed(path))
    ubicaciones = sorted(all_locs.values(), key=lambda x: x.temp_ruta_completa)

    categorias_activos = Categoria.objects.all().order_by('nombre')
    horarios = Horario.objects.all().order_by('nombre')
    
    return render(request, 'mantenimiento/rutinas_dashboard.html', {
        'tree': tree,
        'frecuencias': frecuencias,
        'puestos': puestos,
        'todas_categorias': todas_categorias,
        'ubicaciones': ubicaciones,
        'categorias_activos': categorias_activos,
        'horarios': horarios,
        'total_rutinas': total_rutinas,
        'frecuencia_selected': frecuencia_int,
        'puesto_selected': puesto_int,
        'search': search
    })


@login_required
def rutina_detail_api(request, pk):
    """API que devuelve detalles de una rutina y su historial de ejecución"""
    from django.http import JsonResponse
    from ..models import OrdenTrabajo, CierreOrdenTrabajo, PasoRutina
    
    try:
        rutina = Rutina.objects.select_related(
            'frecuencia', 'puesto_trabajo', 'tipo', 
            'ubicacion_predeterminada', 'categoria_activo', 'horario_predeterminado'
        ).get(pk=pk)
        
        # Obtener historial de OTs realizadas
        # Limitamos a las últimas 10 para rendimiento
        historial_ots = OrdenTrabajo.objects.filter(
            rutina=rutina, 
            estado='REALIZADA'
        ).select_related('tecnico', 'cierre').order_by('-inicio_programado')[:10]
        
        history_data = []
        for ot in historial_ots:
            cierre = getattr(ot, 'cierre', None)
            history_data.append({
                'id': ot.id,
                'codigo': ot.codigo_de_orden or f"OT-{ot.id}",
                'fecha_programada': ot.inicio_programado.strftime('%d/%m/%Y'),
                'fecha_cierre': cierre.fecha_fin_real.strftime('%d/%m/%Y %H:%M') if cierre else "N/A",
                'tecnico': ot.tecnico.get_full_name() if ot.tecnico else "Sin asignar",
                'comentarios': cierre.comentarios if cierre else "",
                'hh': cierre.horas_hombre if cierre else 0,
            })
            
        data = {
            'status': 'success',
            'rutina': {
                'id': rutina.id,
                'codigo': rutina.codigo_rutina or "S/C",
                'nombre': rutina.nombre,
                'categoria': rutina.tipo.nombre if rutina.tipo else "General",
                'categoria_id': rutina.tipo_id,
                'frecuencia': rutina.frecuencia.nombre if rutina.frecuencia else "S/F",
                'frecuencia_id': rutina.frecuencia_id,
                'tiempo_estimado': str(rutina.tiempo_estimado) if rutina.tiempo_estimado else "N/A",
                'tecnicos': rutina.cantidad_tecnicos,
                'descripcion': rutina.descripcion or "Sin descripción",
                'herramientas': rutina.herramientas or "Ninguna",
                'es_invasiva': rutina.es_invasiva,
                'ubicacion_predeterminada_id': rutina.ubicacion_predeterminada_id,
                'ubicacion_predeterminada_nombre': rutina.ubicacion_predeterminada.nombre if rutina.ubicacion_predeterminada else "No asignada",
                'categoria_activo_id': rutina.categoria_activo_id,
                'categoria_activo_nombre': rutina.categoria_activo.nombre if rutina.categoria_activo else "No asignada",
                'horario_predeterminado_id': rutina.horario_predeterminado_id,
                'horario_predeterminado_nombre': rutina.horario_predeterminado.nombre if rutina.horario_predeterminado else "No asignado",
                'admin_url': f"/admin/mantenimiento/rutina/{rutina.id}/change/",
                'pasos': [
                    {
                        'id': p.id,
                        'orden': p.orden, 
                        'descripcion': p.descripcion, 
                        'verificacion': p.verificacion,
                        'tipo_respuesta': p.tipo_respuesta,
                        'valor_objetivo': p.valor_objetivo,
                        'rango_min': p.rango_min,
                        'rango_max': p.rango_max,
                        'unidad_medida': p.unidad_medida,
                        'media': [
                            {'id': m.id, 'url': m.archivo.url, 'tipo': m.tipo, 'descripcion': m.descripcion}
                            for m in p.media_files.all().order_by('orden')
                        ]
                    }
                    for p in rutina.pasos.prefetch_related('media_files').all().order_by('orden')
                ]
            },
            'historial': history_data
        }
        return JsonResponse(data)
    except Rutina.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Rutina no encontrada'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@staff_member_required
def rutina_save_api(request):
    """API para crear o actualizar una rutina vía AJAX"""
    from django.http import JsonResponse
    import json
    
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
        
    try:
        data = json.loads(request.body)
        pk = data.get('id')
        
        if pk:
            rutina = Rutina.objects.get(pk=pk)
        else:
            rutina = Rutina()
            
        rutina.nombre = data.get('nombre')
        rutina.codigo_rutina = data.get('codigo_rutina')
        rutina.descripcion = data.get('descripcion')
        rutina.herramientas = data.get('herramientas')
        rutina.cantidad_tecnicos = int(data.get('cantidad_tecnicos', 1))
        
        # Checkbox invasiva
        es_invasiva_val = data.get('es_invasiva')
        rutina.es_invasiva = es_invasiva_val in [True, 'true', 'on', '1']
        
        # Foreign Keys
        cat_id = data.get('categoria_id')
        rutina.tipo = Tipo.objects.get(pk=cat_id) if cat_id else None
        
        frec_id = data.get('frecuencia_id')
        rutina.frecuencia = Frecuencia.objects.get(pk=frec_id) if frec_id else None
        
        puesto_id = data.get('puesto_trabajo_id')
        rutina.puesto_trabajo = PuestoTrabajo.objects.get(pk=puesto_id) if puesto_id else None
        
        # Nuevos campos
        ubic_id = data.get('ubicacion_predeterminada_id')
        rutina.ubicacion_predeterminada = Ubicacion.objects.get(pk=ubic_id) if ubic_id else None
        
        cat_activo_id = data.get('categoria_activo_id')
        rutina.categoria_activo = Categoria.objects.get(pk=cat_activo_id) if cat_activo_id else None
        
        horario_id = data.get('horario_predeterminado_id')
        rutina.horario_predeterminado = Horario.objects.get(pk=horario_id) if horario_id else None
        
        # DurationField handling (HH:MM:SS)
        from datetime import timedelta
        tiempo_str = data.get('tiempo_estimado')
        if tiempo_str:
            h, m, s = map(int, tiempo_str.split(':'))
            rutina.tiempo_estimado = timedelta(hours=h, minutes=m, seconds=s)
        
        rutina.save()
        
        return JsonResponse({
            'status': 'success', 
            'message': 'Rutina guardada correctamente',
            'rutina_id': rutina.id
        })
        
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@staff_member_required
def tipo_detail_api(request, pk):
    """API que devuelve detalles de un Tipo (Categoría) para el modal de edición"""
    from django.http import JsonResponse
    from servicios.models import KPI
    try:
        tipo = Tipo.objects.prefetch_related('kpis').get(pk=pk)
        data = {
            'status': 'success',
            'tipo': {
                'id': tipo.id,
                'nombre': tipo.nombre,
                'codigo': tipo.codigo or "",
                'descripcion': tipo.descripcion or "",
                'padre_id': tipo.padre_id or "",
                'kpi_ids': list(tipo.kpis.values_list('id', flat=True)),
            }
        }
        return JsonResponse(data)
    except Tipo.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Categoría no encontrada'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@staff_member_required
def tipo_save_api(request):
    """API para crear o actualizar un Tipo (Categoría) vía AJAX"""
    from django.http import JsonResponse
    import json
    
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
        
    try:
        data = json.loads(request.body)
        pk = data.get('id')
        nombre = data.get('nombre')
        
        if not nombre:
            return JsonResponse({'status': 'error', 'message': 'El nombre es obligatorio'}, status=400)
        
        if pk:
            tipo = Tipo.objects.get(pk=pk)
        else:
            tipo = Tipo()
            
        tipo.nombre = nombre
        tipo.codigo = data.get('codigo') or None
        tipo.descripcion = data.get('descripcion') or ""
        
        padre_id = data.get('padre_id')
        if padre_id:
            # Prevención de ciclos básicos
            if str(padre_id) == str(pk):
                return JsonResponse({'status': 'error', 'message': 'Una categoría no puede ser padre de sí misma'}, status=400)
            tipo.padre = Tipo.objects.get(pk=padre_id)
        else:
            tipo.padre = None
            
        tipo.save()
        
        return JsonResponse({
            'status': 'success', 
            'message': 'Categoría guardada correctamente',
            'tipo_id': tipo.id
        })
        
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@staff_member_required
def tipo_delete_api(request, pk):
    """API para eliminar un Tipo (Categoría)"""
    from django.http import JsonResponse
    from django.db.models import ProtectedError
    
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
        
    try:
        tipo = Tipo.objects.get(pk=pk)
        
        # Validar si tiene rutinas o subtipos (dependiendo de on_delete, pero mejor ser explícito para el usuario)
        if tipo.subtipos.count() > 0:
            return JsonResponse({'status': 'error', 'message': 'No se puede eliminar una categoría que contiene sub-categorías. Elimínalas o muévelas primero.'}, status=400)
            
        if Rutina.objects.filter(tipo=tipo).count() > 0:
            return JsonResponse({'status': 'error', 'message': 'No se puede eliminar una categoría que contiene rutinas estructuradas. Reasigna las rutinas primero.'}, status=400)
            
        tipo.delete()
        return JsonResponse({'status': 'success', 'message': 'Categoría eliminada'})
        
    except Tipo.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Categoría no encontrada'}, status=404)
    except ProtectedError:
        return JsonResponse({'status': 'error', 'message': 'No se puede eliminar porque está en uso en otros registros (Ej: Activos).'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@staff_member_required
def rutina_pasos_save_api(request):
    """API para guardar los pasos de una rutina de forma atómica"""
    from django.http import JsonResponse
    from django.db import transaction
    import json
    
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
            
            # 1. Obtener IDs de pasos actuales para controlar borrados
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
            PasoRutina.objects.filter(rutina=rutina).exclude(id__in=new_paso_ids).delete()
            
        return JsonResponse({'status': 'success', 'message': 'Pasos actualizados correctamente'})
        
    except Rutina.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Rutina no encontrada'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@staff_member_required
def rutina_delete_api(request, pk):
    """API para eliminar una rutina"""
    from django.http import JsonResponse
    
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
        
    try:
        rutina = Rutina.objects.get(pk=pk)
        rutina.delete()
        return JsonResponse({'status': 'success', 'message': 'Rutina eliminada correctamente'})
    except Rutina.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'La rutina no existe'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@staff_member_required
def rutina_delete_secure_api(request, pk):
    """Elimina una rutina con verificación de contraseña del usuario actual"""
    from django.http import JsonResponse
    from django.contrib.auth import authenticate
    from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
    import json
    
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
    
    try:
        data = json.loads(request.body)
        password = data.get('password')
        token = data.get('verification_token')
        remember = data.get('remember', False)
        
        verified = False
        
        if token:
            try:
                signer = TimestampSigner(salt='rutina-delete')
                username = signer.unsign(token, max_age=86400)
                if username == request.user.username:
                    verified = True
            except (BadSignature, SignatureExpired):
                pass
        
        if password:
            user = authenticate(username=request.user.username, password=password)
            if user is not None:
                verified = True
        
        if not verified:
            return JsonResponse({'status': 'error', 'message': 'Contraseña incorrecta'}, status=403)
        
        rutina = Rutina.objects.get(pk=pk)
        rutina.delete()
        
        response_data = {'status': 'success', 'message': 'Rutina eliminada correctamente'}
        
        if remember:
            signer = TimestampSigner(salt='rutina-delete')
            response_data['verification_token'] = signer.sign(request.user.username)
        
        return JsonResponse(response_data)
    
    except Rutina.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Rutina no encontrada'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
def rutina_qr_pdf(request, pk):
    """Genera la etiqueta QR PDF 3x2 descargas de la rutina."""
    import io
    import qrcode
    import base64
    from django.http import HttpResponse
    from django.shortcuts import get_object_or_404
    from django.template.loader import get_template
    from xhtml2pdf import pisa
    
    rutina = get_object_or_404(Rutina, pk=pk)
    
    qr_data = rutina.codigo_rutina if rutina.codigo_rutina else f"RUTINA-{rutina.id}"
    
    qr = qrcode.QRCode(version=1, box_size=5, border=1)
    qr.add_data(qr_data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    qr_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    context = {
        'rutina': rutina,
        'qr_code': qr_b64
    }
    
    template = get_template('mantenimiento/rutina_etiqueta_pdf.html')
    html = template.render(context)
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="etiqueta_rutina_{rutina.codigo_rutina or rutina.id}.pdf"'
    
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse(f'Error al generar PDF: {pisa_status.err}', status=500)
        
    return response


@staff_member_required
def api_rutina_kpis(request, pk):
    """API que devuelve los KPIs vinculados a una rutina y los disponibles para su servicio"""
    from django.http import JsonResponse
    from servicios.models import KPI
    
    try:
        rutina = Rutina.objects.select_related('tipo', 'tipo__padre', 'tipo__padre__padre').get(pk=pk)
        
        # 1. KPIs actualmente vinculados
        kpis_vinculados = rutina.kpis.select_related('servicio').all()
        vinculados_data = [{
            'id': kpi.id,
            'nombre': kpi.nombre or "KPI sin nombre",
            'servicio': kpi.servicio.nombre if kpi.servicio else "General",
            'categoria': kpi.categoria,
            'estado': kpi.estado
        } for kpi in kpis_vinculados]
        
        # 2. KPIs disponibles (filtrados por el servicio heredado de la categoría)
        servicio_heredado = rutina.tipo.get_servicio() if rutina.tipo else None
        
        disponibles_qs = KPI.objects.exclude(id__in=[k.id for k in kpis_vinculados]).select_related('servicio')
        
        if servicio_heredado:
            disponibles_qs = disponibles_qs.filter(servicio=servicio_heredado)
            
        disponibles_data = [{
            'id': kpi.id,
            'nombre': kpi.nombre or "KPI sin nombre",
            'servicio': kpi.servicio.nombre if kpi.servicio else "General",
            'categoria': kpi.categoria
        } for kpi in disponibles_qs]
        
        return JsonResponse({
            'status': 'success',
            'servicio_filtro': servicio_heredado.nombre if servicio_heredado else None,
            'vinculados': vinculados_data,
            'disponibles': disponibles_data
        })
        
    except Rutina.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Rutina no encontrada'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@staff_member_required
def api_rutina_kpis_save(request, pk):
    """API para guardar (añadir/quitar) los KPIs vinculados a una rutina"""
    from django.http import JsonResponse
    from servicios.models import KPI
    import json
    
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
        
    try:
        rutina = Rutina.objects.get(pk=pk)
        data = json.loads(request.body)
        
        kpi_ids = data.get('kpi_ids', [])
        
        # Como es ManyToMany, podemos simplemente asignar la nueva lista completa
        # Esto eliminará los que no estén en la lista y añadirá los nuevos
        kpis_to_set = KPI.objects.filter(id__in=kpi_ids)
        rutina.kpis.set(kpis_to_set)
        
        return JsonResponse({'status': 'success', 'message': 'KPIs actualizados correctamente'})
        
    except Rutina.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Rutina no encontrada'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@staff_member_required
def api_tipo_kpis(request, pk):
    """API que devuelve los KPIs vinculados a una categoría (Tipo) y los disponibles"""
    from django.http import JsonResponse
    from servicios.models import KPI

    try:
        tipo = Tipo.objects.get(pk=pk)
        kpis_vinculados = tipo.kpis.select_related('servicio').all()
        vinculados_data = [{
            'id': kpi.id,
            'nombre': kpi.nombre or "KPI sin nombre",
            'servicio': kpi.servicio.nombre if kpi.servicio else "General",
            'categoria': kpi.categoria,
            'estado': kpi.estado,
        } for kpi in kpis_vinculados]

        servicio_heredado = tipo.get_servicio()
        disponibles_qs = KPI.objects.exclude(
            id__in=[k.id for k in kpis_vinculados]
        ).select_related('servicio')
        if servicio_heredado:
            disponibles_qs = disponibles_qs.filter(servicio=servicio_heredado)
        disponibles_data = [{
            'id': kpi.id,
            'nombre': kpi.nombre or "KPI sin nombre",
            'servicio': kpi.servicio.nombre if kpi.servicio else "General",
            'categoria': kpi.categoria,
        } for kpi in disponibles_qs]

        return JsonResponse({
            'status': 'success',
            'servicio_filtro': servicio_heredado.nombre if servicio_heredado else None,
            'vinculados': vinculados_data,
            'disponibles': disponibles_data,
        })
    except Tipo.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Categoría no encontrada'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@staff_member_required
def api_tipo_kpis_save(request, pk):
    """API para guardar los KPIs vinculados a una categoría (Tipo)"""
    from django.http import JsonResponse
    from servicios.models import KPI
    import json

    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
    try:
        tipo = Tipo.objects.get(pk=pk)
        data = json.loads(request.body)
        kpi_ids = data.get('kpi_ids', [])
        kpis_to_set = KPI.objects.filter(id__in=kpi_ids)
        tipo.kpis.set(kpis_to_set)
        return JsonResponse({'status': 'success', 'message': 'KPIs de categoría actualizados correctamente'})
    except Tipo.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Categoría no encontrada'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@staff_member_required
def paso_media_upload_api(request, paso_id):
    """API para subir archivos multimedia a un paso de rutina"""
    from django.http import JsonResponse
    import os
    
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
    
    try:
        paso = PasoRutina.objects.get(pk=paso_id)
        archivo = request.FILES.get('file')
        
        if not archivo:
            return JsonResponse({'status': 'error', 'message': 'No se recibió ningún archivo'}, status=400)
        
        # Validar tamaño (50MB máx)
        if archivo.size > 50 * 1024 * 1024:
            return JsonResponse({'status': 'error', 'message': 'El archivo excede el límite de 50MB'}, status=400)
        
        # Auto-detectar tipo por extensión
        ext = os.path.splitext(archivo.name)[1].lower()
        IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg'}
        VIDEO_EXTS = {'.mp4', '.webm', '.mov', '.avi', '.mkv', '.m4v'}
        
        if ext in IMAGE_EXTS:
            tipo = 'IMAGEN'
        elif ext in VIDEO_EXTS:
            tipo = 'VIDEO'
        else:
            return JsonResponse({'status': 'error', 'message': f'Extensión no soportada: {ext}. Use imágenes (jpg, png, webp) o videos (mp4, webm, mov).'}, status=400)
        
        # Determinar orden
        max_orden = paso.media_files.aggregate(Max('orden'))['orden__max'] or 0
        
        descripcion = request.POST.get('descripcion', '')
        
        media = MediaPasoRutina.objects.create(
            paso=paso,
            archivo=archivo,
            tipo=tipo,
            descripcion=descripcion,
            orden=max_orden + 1
        )
        
        return JsonResponse({
            'status': 'success',
            'media': {
                'id': media.id,
                'url': media.archivo.url,
                'tipo': media.tipo,
                'descripcion': media.descripcion
            }
        })
        
    except PasoRutina.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Paso no encontrado'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@staff_member_required
def paso_media_delete_api(request, media_id):
    """API para eliminar un archivo multimedia de un paso"""
    from django.http import JsonResponse
    
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
    
    try:
        media = MediaPasoRutina.objects.get(pk=media_id)
        # Eliminar archivo físico
        if media.archivo:
            media.archivo.delete(save=False)
        media.delete()
        return JsonResponse({'status': 'success', 'message': 'Archivo eliminado correctamente'})
    except MediaPasoRutina.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Archivo no encontrado'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@staff_member_required
def rutina_print_pdf(request, pk):
    """Genera un PDF visual del procedimiento de la rutina con imágenes."""
    try:
        rutina = Rutina.objects.select_related('tipo', 'frecuencia').get(pk=pk)
        pasos_qs = rutina.pasos.prefetch_related('media_files').all().order_by('orden')
        
        # Procesar pasos para incluir imágenes base64
        pasos_data = []
        for p in pasos_qs:
            fotos = []
            for m in p.media_files.filter(tipo='IMAGEN').order_by('orden'):
                try:
                    if m.archivo:
                        # Leer archivo y convertir a base64
                        ext = os.path.splitext(m.archivo.name)[1].lower().replace('.', '')
                        mime = {'jpg': 'jpeg', 'jpeg': 'jpeg', 'png': 'png', 'gif': 'gif', 'webp': 'webp'}.get(ext, 'jpeg')
                        b64 = base64.b64encode(m.archivo.read()).decode('utf-8')
                        fotos.append({
                            'data_uri': f'data:image/{mime};base64,{b64}'
                        })
                except Exception as e:
                    print(f"Error procesando imagen para PDF: {e}")
            
            pasos_data.append({
                'descripcion': p.descripcion,
                'tipo_respuesta': p.tipo_respuesta,
                'get_tipo_respuesta_display': p.get_tipo_respuesta_display(),
                'verificacion': p.verificacion,
                'fotos': fotos
            })

        # Logo opcional
        logo_b64 = ""
        logo_path = os.path.join(settings.BASE_DIR, 'activos', 'static', 'activos', 'img', 'logo_operadora_cc.png')
        if os.path.exists(logo_path):
            with open(logo_path, "rb") as f:
                logo_b64 = base64.b64encode(f.read()).decode('utf-8')

        context = {
            'rutina': rutina,
            'pasos': pasos_data,
            'ahora': timezone.now(),
            'logo_b64': logo_b64
        }
        
        html_content = render_to_string('mantenimiento/rutina_procedimiento_pdf.html', context, request=request)
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
            page = browser.new_page()
            page.set_content(html_content, wait_until='networkidle')
            pdf_bytes = page.pdf(format="A4", print_background=True, margin={'top': '0', 'bottom': '0', 'left': '0', 'right': '0'})
            browser.close()
            
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        filename = f"Guia_Procedimiento_{rutina.codigo_rutina or rutina.id}.pdf"
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response

    except Rutina.DoesNotExist:
        raise Http404("Rutina no encontrada")
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error generando PDF de rutina: {e}", exc_info=True)
        return HttpResponse(f"Error interno: {str(e)}", status=500)

@staff_member_required
def rutina_move_api(request, pk):
    """API para mover una rutina de una categoría a otra"""
    from django.http import JsonResponse
    import json
    
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
        
    try:
        data = json.loads(request.body)
        tipo_id = data.get('tipo_id')
        
        rutina = Rutina.objects.get(pk=pk)
        if tipo_id:
            rutina.tipo = Tipo.objects.get(pk=tipo_id)
        else:
            rutina.tipo = None
            
        rutina.save(update_fields=['tipo'])
        
        return JsonResponse({'status': 'success', 'message': 'Rutina movida correctamente'})
    except Rutina.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Rutina no encontrada'}, status=404)
    except Tipo.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'La categoría destino no existe'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@staff_member_required
def tipo_move_api(request, pk):
    """API para mover una categoría (Tipo) debajo de otra (padre)"""
    from django.http import JsonResponse
    import json
    
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
        
    try:
        data = json.loads(request.body)
        padre_id = data.get('padre_id')
        
        tipo = Tipo.objects.get(pk=pk)
        
        if padre_id:
            if int(padre_id) == tipo.id:
                return JsonResponse({'status': 'error', 'message': 'Una categoría no puede ser padre de sí misma'}, status=400)
            tipo.padre = Tipo.objects.get(pk=padre_id)
        else:
            tipo.padre = None
            
        tipo.save(update_fields=['padre'])
        
        return JsonResponse({'status': 'success', 'message': 'Categoría movida correctamente'})
    except Tipo.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'La categoría no existe'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@staff_member_required
def export_rutinas_excel(request):
    """Exporta todas las rutinas a un archivo Excel (.xlsx) usando el RutinaResource existente."""
    from ..admin import RutinaResource

    resource = RutinaResource()

    # Aplicar los mismos filtros que el dashboard si vienen en GET
    qs = Rutina.objects.all().select_related('frecuencia', 'tipo', 'puesto_trabajo',
                                             'ubicacion_predeterminada', 'categoria_activo',
                                             'horario_predeterminado')

    frecuencia_id = request.GET.get('frecuencia')
    puesto_id = request.GET.get('puesto')
    search = request.GET.get('search', '').strip()

    if frecuencia_id:
        try:
            qs = qs.filter(frecuencia_id=int(frecuencia_id))
        except (ValueError, TypeError):
            pass

    if puesto_id:
        try:
            qs = qs.filter(puesto_trabajo_id=int(puesto_id))
        except (ValueError, TypeError):
            pass

    if search:
        terms = [t.strip() for t in search.split('+')]
        for term in terms:
            qs = qs.filter(
                Q(nombre__icontains=term) |
                Q(codigo_rutina__icontains=term) |
                Q(descripcion__icontains=term) |
                Q(tipo__nombre__icontains=term)
            )

    dataset = resource.export(queryset=qs)

    response = HttpResponse(
        dataset.xlsx,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="rutinas_mantenimiento.xlsx"'
    return response

