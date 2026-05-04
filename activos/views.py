from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.db.models import Q
from .forms import ActivoAdminForm
from .models import VisorPlano, PinPlano, Activo
import json
from django.views.decorators.csrf import csrf_exempt
from celery.result import AsyncResult
from django.contrib.admin.views.decorators import staff_member_required
from core.decorators import mobile_permission_required
from django.contrib import messages
from django.contrib.auth.decorators import login_required

def visor_plano(request, visor_id=None, plano_id=None):
    from .models.plano import VisorPlano, Plano
    
    visor = None
    if visor_id:
        visor = get_object_or_404(
            VisorPlano.objects.select_related('plano__ubicacion').prefetch_related(
                'pines__activo__modelo__categoria',
                'pines__aviso',
                'pines__actividad',
                'pines__fotos',
                'proyectos'
            ), 
            pk=visor_id
        )
    elif plano_id:
        plano = get_object_or_404(Plano, pk=plano_id)
        # Buscar si este plano ya tiene un visor asignado
        visor = VisorPlano.objects.filter(plano=plano).select_related('plano__ubicacion').prefetch_related(
            'pines__activo__modelo__categoria',
            'pines__aviso',
            'pines__actividad',
            'pines__fotos',
            'proyectos'
        ).first()
        
        if not visor:
            # 1. Prioridad: Documento ID pasado por el explorador
            doc_id = request.GET.get('documento_id')
            if doc_id:
                from documentos.models import Documento
                doc = Documento.objects.filter(id=doc_id).select_related('ultima_revision').first()
                if doc:
                    plano.documento = doc
                    # Guardar permanentemente si no tenía vínculo
                    if not plano.documento_id:
                        plano.save(update_fields=['documento'])

            # 2. Fallback: Buscar coincidencia por nombre (Si no se pasó doc_id o no se cargó archivo)
            if not plano.archivo_actual:
                from documentos.models import Documento
                # Búsqueda más permisiva: el código o título contiene el nombre del plano
                clean_name = plano.nombre.strip('-').strip()
                doc = Documento.objects.filter(
                    Q(codigo__icontains=clean_name) | 
                    Q(titulo__icontains=clean_name)
                ).select_related('ultima_revision').order_by('-id').first()
                if doc:
                    plano.documento = doc
                    if not plano.documento_id:
                        plano.save(update_fields=['documento'])

            # Crear un objeto temporal en memoria (NO GUARDADO) para que el template funcione
            visor = VisorPlano(
                nombre=f"Visor: {plano.nombre}",
                plano=plano
            )
            # Marcar como temporal para que el frontend sepa que no se pueden guardar pines inicialmente
            visor.is_ephemeral = True
            visor.pines_data = [] # Mock para prefetch_related
        else:
            visor.is_ephemeral = False
    
    if not visor:
        raise Http404("No se especificó visor ni plano")
    
    from .models import Categoria, Ubicacion
    from mantenimiento.models import Aviso
    from proyectos.models import Actividad
    
    # Optimización para móvil: Solo traer los datos necesarios o limitar
    categorias = Categoria.objects.all().order_by('nombre')
    ubicaciones = Ubicacion.objects.all().order_by('nombre')
    # Solo avisos abiertos o en proceso
    avisos = Aviso.objects.filter(estado__in=['ABIERTO', 'PROCESO']).order_by('-creado_en')[:100]
    # Actividades de proyectos pendientes o en progreso
    actividades = Actividad.objects.filter(
        estado__in=['PENDIENTE', 'EN_PROGRESO']
    ).select_related('proyecto').order_by('proyecto__codigo', 'orden')[:100]
    visor_pins = visor.pines.all() if not getattr(visor, 'is_ephemeral', False) else []
    proyectos_visor = visor.proyectos.all() if not getattr(visor, 'is_ephemeral', False) else []
    
    context = {
        'visor': visor,
        'visor_pins': visor_pins,
        'ubicaciones': ubicaciones,
        'categorias': categorias,
        'avisos': avisos,
        'actividades': actividades,
        'proyectos': proyectos_visor,
    }
    
    return render(request, 'activos/visor_plano.html', context)

@staff_member_required
def api_buscar_activos_json(request):
    """API para búsqueda dinámica de activos en el visor"""
    from django.db import models
    query = request.GET.get('q', '').strip()
    cat_id = request.GET.get('cat_id')
    loc_id = request.GET.get('loc_id')
    
    qs = Activo.objects.all().select_related('modelo__categoria', 'ubicacion').order_by('nombre')
    
    if query:
        qs = qs.filter(
            models.Q(nombre__icontains=query) | 
            models.Q(codigo_interno__icontains=query) |
            models.Q(descripcion__icontains=query) |
            models.Q(serie__icontains=query)
        )
    
    if cat_id:
        qs = qs.filter(modelo__categoria_id=cat_id)
        
    if loc_id:
        qs = qs.filter(ubicacion_id=loc_id)
        
    # Limitar resultados para evitar sobrecarga
    qs = qs[:50]
    
    data = []
    for a in qs:
        data.append({
            'id': a.id,
            'nombre': a.nombre,
            'codigo': a.codigo_interno or '',
            'categoria_id': a.modelo.categoria.id if a.modelo and a.modelo.categoria else '',
            'ubicacion_id': a.ubicacion.id if a.ubicacion else '',
            # Metadata extra para el select
            'data_nombre': a.nombre.lower(),
            'data_codigo': (a.codigo_interno or '').lower()
        })
        
    return JsonResponse({'results': data})

@staff_member_required
def api_buscar_modelos_json(request):
    """API para búsqueda dinámica de modelos de activos para Select2"""
    from django.db import models
    from .models import Modelo
    query = request.GET.get('q', '').strip()
    
    qs = Modelo.objects.all().select_related('marca', 'categoria', 'unidad_medida').order_by('marca__nombre', 'nombre')
    
    if query:
        qs = qs.filter(
            models.Q(nombre__icontains=query) | 
            models.Q(marca__nombre__icontains=query)
        )
        
    # Limitar resultados para evitar sobrecarga
    qs = qs[:50]
    
    data = []
    for m in qs:
        cat_nombre = m.categoria.nombre if m.categoria else ''
        cat_icono = m.categoria.icono if m.categoria else 'cube'
        
        unidad_nombre = m.unidad_medida.nombre if hasattr(m, 'unidad_medida') and m.unidad_medida else ''
        
        marca_str = m.marca.nombre if m.marca else ''
        # El nombre que se mostrará
        texto = f"{marca_str} {m.nombre}".strip()
        
        data.append({
            'id': m.id,
            'text': texto,
            'categoria': cat_nombre,
            'unidad': unidad_nombre,
            'icono': cat_icono,
        })
        
    return JsonResponse({'results': data})

@csrf_exempt
@staff_member_required
def guardar_pin(request):
    if request.method == 'POST':
        try:
            # Soportar tanto JSON como FormData (para archivos)
            if request.content_type == 'application/json':
                data = json.loads(request.body)
            else:
                data = request.POST

            pin_id = data.get('id')
            visor_id = data.get('visor_id')
            activo_id = data.get('activo_id')
            aviso_id = data.get('aviso_id')
            x = float(data.get('x'))
            y = float(data.get('y'))
            color = data.get('color', '#FF0000')
            nota = data.get('nota', '')

            if pin_id and pin_id != 'null':
                pin = get_object_or_404(PinPlano, id=pin_id)
            else:
                pin = PinPlano(visor_id=visor_id)

            if activo_id:
                # Verificar duplicados en el mismo visor
                dup = PinPlano.objects.filter(visor_id=visor_id, activo_id=activo_id).exclude(id=pin.id).first()
                if dup:
                    return JsonResponse({
                        'status': 'error',
                        'message': f'El activo "{dup.activo.nombre}" ya está ubicado en este plano.'
                    }, status=400)
                pin.activo_id = activo_id
            else:
                pin.activo = None
            
            if aviso_id:
                pin.aviso_id = aviso_id
            else:
                pin.aviso = None
            
            # Actividad de proyecto
            actividad_id = data.get('actividad_id')
            if actividad_id:
                pin.actividad_id = actividad_id
            else:
                pin.actividad = None
                
            # Ubicación (Zonas/Áreas)
            ubicacion_id = data.get('ubicacion_id')
            if ubicacion_id:
                pin.ubicacion_id = ubicacion_id
            else:
                pin.ubicacion = None

            # Dimensiones (para áreas)
            ancho = float(data.get('ancho') or 0)
            alto = float(data.get('alto') or 0)
            pin.ancho = ancho
            pin.alto = alto
                
            pin.x = x
            pin.y = y
            pin.color = color
            pin.nota = nota
            pin.save()

            # Devolver los nuevos campos en la respuesta
            aviso_meta = {}
            if pin.aviso:
                aviso_meta = {
                    "prioridad": pin.aviso.get_prioridad_display(),
                    "estado": pin.aviso.get_estado_display(),
                    "solicitante": pin.aviso.solicitante.username if pin.aviso.solicitante else "Anónimo",
                    "descripcion": pin.aviso.descripcion
                }

            fotos_urls = [foto.imagen.url for foto in pin.fotos.all()]

            # Guardar fotos si vienen en la petición
            if 'fotos' in request.FILES:
                from .models import PinFoto
                for f in request.FILES.getlist('fotos'):
                    PinFoto.objects.create(pin=pin, imagen=f)

            # Obtener URLs de las fotos
            fotos_urls = [f.imagen.url for f in pin.fotos.all()]

            nombre_label = "Sin asignar"
            icono_label = "location"
            aviso_meta = {}
            
            if pin.actividad:
                nombre_label = pin.actividad.nombre
                icono_label = "construct"
            elif pin.activo:
                nombre_label = pin.activo.nombre
                cat = pin.activo.modelo.categoria if pin.activo.modelo else None
                icono_label = cat.icono if cat else 'cube'
            elif pin.aviso:
                nombre_label = f"AV-{pin.aviso.id}"
                icono_label = "warning"
                aviso_meta = {
                    'prioridad': pin.aviso.get_prioridad_display(),
                    'estado': pin.aviso.get_estado_display(),
                    'solicitante': pin.aviso.solicitante.username if pin.aviso.solicitante else 'Anónimo',
                    'descripcion': pin.aviso.descripcion
                }

            return JsonResponse({
                'status': 'success',
                'pin_id': pin.id,
                'activo_id': pin.activo.id if pin.activo else None,
                'aviso_id': pin.aviso.id if pin.aviso else None,
                'actividad_id': pin.actividad.id if pin.actividad else None,
                'ubicacion_id': pin.ubicacion_id,
                'nombre_activo': nombre_label,
                'nombre_actividad': pin.actividad.nombre if pin.actividad else None,
                'nombre_ubicacion': pin.ubicacion.nombre if pin.ubicacion else None,
                'codigo_externo': pin.activo.codigo_interno if pin.activo else '',
                'nota': pin.nota,
                'fotos': fotos_urls,
                'icono': icono_label,
                'aviso_meta': aviso_meta,
                'ancho': pin.ancho,
                'alto': pin.alto
            })
        except Exception as e:
            return HttpResponse(f"Error fatal: {str(e)}", status=500)

@csrf_exempt
@staff_member_required
def api_upload_foto_ubicacion(request):
    """
    API para subir una o varias fotos a una ubicación.
    Optimización activa en el modelo.
    """
    if request.method == 'POST':
        from .models.foto_ubicacion import FotoUbicacion
        from .models.ubicacion import Ubicacion
        
        ubicacion_id = request.POST.get('ubicacion_id')
        if not ubicacion_id:
            return JsonResponse({'success': False, 'error': 'Falta ID de ubicación'}, status=400)
            
        ubicacion = get_object_or_404(Ubicacion, pk=ubicacion_id)
        files = request.FILES.getlist('fotos')
        
        if not files:
            return JsonResponse({'success': False, 'error': 'No hay archivos seleccionados'}, status=400)
            
        saved_count = 0
        for f in files:
            try:
                # El modelo FotoUbicacion ya tiene la lógica de optimización en su save()
                foto_obj = FotoUbicacion.objects.create(
                    ubicacion=ubicacion,
                    foto=f,
                    subido_por=request.user
                )
                saved_count += 1
            except Exception as e:
                print(f"Error subiendo foto: {e}")
                
        return JsonResponse({
            'success': True, 
            'message': f'Se subieron {saved_count} fotos con éxito.',
            'count': saved_count
        })
        
    return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)

@csrf_exempt
def eliminar_pin(request, pin_id):
    if request.method == 'POST':
        pin = get_object_or_404(PinPlano, id=pin_id)
        pin.delete()
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=405)

def import_progress(request, task_id):
    """
    API endpoint para obtener el progreso de una tarea de importación Celery.
    """
    task = AsyncResult(task_id)
    
    if task.state == 'PENDING':
        response = {
            'state': task.state,
            'current': 0,
            'total': 1,
            'status': 'Esperando inicio...',
            'percent': 0
        }
    elif task.state == 'PROGRESS':
        response = {
            'state': task.state,
            'current': task.info.get('current', 0),
            'total': task.info.get('total', 1),
            'status': task.info.get('status', ''),
            'current_row': task.info.get('current_row', ''),
            'percent': task.info.get('percent', 0)
        }
    elif task.state == 'SUCCESS':
        response = {
            'state': task.state,
            'current': 100,
            'total': 100,
            'status': 'Completado',
            'percent': 100,
            'result': task.info
        }
    else:  # FAILURE, etc.
        response = {
            'state': task.state,
            'current': 1,
            'total': 1,
            'status': str(task.info),  # Exception info
            'percent': 0
        }
    
    return JsonResponse(response)

@staff_member_required
def get_import_progress(request):
    """
    Retorna información detallada del progreso de importación para el usuario actual.
    Incluye: porcentaje, item actual, conteo procesado, estadísticas y velocidad.
    """
    from django.core.cache import cache
    uid = request.user.id
    
    progress = cache.get(f"import_progress_{uid}", 0)
    current_item = cache.get(f"import_progress_{uid}_current", '')
    processed = cache.get(f"import_progress_{uid}_count", 0)
    stats = cache.get(f"import_progress_{uid}_stats", {'new': 0, 'update': 0, 'skip': 0, 'error': 0})
    start_time = cache.get(f"import_progress_{uid}_start", 0)
    
    # Calcular velocidad (items por segundo)
    import time
    elapsed = time.time() - start_time if start_time else 0
    speed = round(processed / elapsed, 1) if elapsed > 0 else 0
    
    return JsonResponse({
        'progress': progress,
        'current_item': current_item,
        'processed': processed,
        'stats': stats,
        'speed': speed,  # items/segundo
        'elapsed': round(elapsed, 1)
    })

# --- Vistas para Arbol Interactivo ---

@staff_member_required
def arbol_activos_view(request):
    """Vista principal que renderiza el template del árbol"""
    return render(request, 'activos/arbol_activos.html', {
        'title': 'Explorador de Activos por Ubicación'
    })

@staff_member_required
def explorer_jerarquia_admin(request):
    """Vista de jerarquía completa para el admin"""
    from .models import Ubicacion, Activo, Categoria
    
    roots = Ubicacion.objects.filter(padre__isnull=True).order_by('orden', 'nombre')
    cat_roots = Categoria.objects.filter(padre__isnull=True).order_by('nombre')
    
    context = {
        'title': 'Explorador Jerárquico de Activos',
        'roots': roots,
        'cat_roots': cat_roots,
        'app_label': 'activos',
    }
    return render(request, 'admin/activos/jerarquia_completa.html', context)

@staff_member_required
def api_get_explorer_level(request):
    """Retorna un fragmento HTML con los hijos de una ubicación o activo optimizado para rendimiento"""
    from .models import Ubicacion, Activo, Categoria
    from collections import defaultdict
    from django.db.models import Count, Q, Exists, OuterRef
    
    parent_id = request.GET.get('id')
    parent_type = request.GET.get('type') # 'ubicacion' o 'activo' o 'categoria'
    cat_id = request.GET.get('cat_id') # Contexto de categoría si existe
    
    sub_ubicaciones = []
    sub_categorias = []
    activos_directos = []
    categorias_activos = defaultdict(list)

    # Definimos sub-query de existencia de hijos para anotar y evitar N+1 en plantilla
    hijos_ubi_exists = Ubicacion.objects.filter(padre=OuterRef('pk'))
    activos_ubi_exists = Activo.objects.filter(ubicacion=OuterRef('pk'))
    hijos_activo_exists = Activo.objects.filter(padre=OuterRef('pk'))
    
    
    import time
    start_time = time.time()
    
    if parent_type == 'ubicacion':
        ubicacion = get_object_or_404(Ubicacion, id=parent_id)
        
        if cat_id:
            categoria = get_object_or_404(Categoria, id=cat_id)
            descendant_cats = categoria.get_descendants(include_self=True)
            
            # Filtramos todos los activos de esta categoría que están bajo esta ubicación (en cualquier nivel)
            # Esto nos servirá para identificar qué sub-ubicaciones tienen contenido válido de forma masiva
            all_valid_assets = Activo.objects.filter(
                ubicacion__in=ubicacion.get_descendants(include_self=True),
                modelo__categoria__in=descendant_cats
            ).values_list('ubicacion_id', flat=True).distinct()
            
            # Sub-ubicaciones directas: Solo las que tienen descendientes con activos válidos.
            # En lugar de un loop con recursión, usamos la lista all_valid_assets.
            valid_subs = []
            for sub in ubicacion.sub_ubicaciones.all():
                # Una sub-ubicación es válida si ella misma o alguno de sus descendientes está en la lista de activos
                if sub.id in all_valid_assets or any(d_id in all_valid_assets for d_id in sub.get_descendants().values_list('id', flat=True)):
                    valid_subs.append(sub.id)
            
            sub_ubicaciones = Ubicacion.objects.filter(id__in=valid_subs).annotate(
                has_sub_ubicaciones=Exists(hijos_ubi_exists),
                has_activos=Exists(activos_ubi_exists)
            ).order_by('orden', 'nombre')
            
            # 2. Mostrar activos directos de esta categoría en esta ubicación
            activos_directos = Activo.objects.filter(
                ubicacion=ubicacion, 
                modelo__categoria__in=descendant_cats, 
                padre__isnull=True
            ).annotate(num_hijos=Count('componentes')).select_related('modelo__categoria', 'ubicacion').order_by('nombre')
            
        else:
            # Vista normal por ubicación
            sub_ubicaciones = ubicacion.sub_ubicaciones.annotate(
                has_sub_ubicaciones=Exists(hijos_ubi_exists),
                has_activos=Exists(activos_ubi_exists)
            ).order_by('orden', 'nombre')
            
            activos = ubicacion.activos.filter(padre__isnull=True).annotate(
                num_hijos=Count('componentes')
            ).select_related('modelo__categoria', 'ubicacion').order_by('nombre')
            
            for a in activos:
                cat_nombre = a.modelo.categoria.nombre if (a.modelo and a.modelo.categoria) else "Sin Categoría"
                categorias_activos[cat_nombre].append(a)
            
    elif parent_type == 'activo':
        print(f"DEBUG EXPLORER: Loading components for asset {parent_id}")
        t0 = time.time()
        activo_padre = get_object_or_404(Activo, id=parent_id)
        print(f"DEBUG EXPLORER: get_object took {time.time() - t0:.4f}s")
        
        t1 = time.time()
        hijos = activo_padre.componentes.annotate(
            num_hijos=Count('componentes')
        ).select_related('modelo__categoria', 'ubicacion').order_by('nombre')
        
        hijos_list = list(hijos)
        print(f"DEBUG EXPLORER: Query took {time.time() - t1:.4f}s. Count: {len(hijos_list)}")
        
        categoria_filt = None
        descendant_cats = []
        if cat_id:
            categoria_filt = get_object_or_404(Categoria, id=cat_id)
            descendant_cats = list(categoria_filt.get_descendants(include_self=True).values_list('id', flat=True))
            
        t2 = time.time()
        for a in hijos_list:
            show = True
            if cat_id:
                show = a.modelo and a.modelo.categoria_id in descendant_cats
            
            if show:
                cat_nombre = a.modelo.categoria.nombre if (a.modelo and a.modelo.categoria) else "Sin Categoría"
                categorias_activos[cat_nombre].append(a)
        print(f"DEBUG EXPLORER: Grouping took {time.time() - t2:.4f}s")

    elif parent_type == 'categoria':
        categoria = get_object_or_404(Categoria, id=parent_id)
        sub_categorias = categoria.subcategorias.all().order_by('nombre')
        
        # En lugar de listar activos directo, listamos las ubicaciones raíz que tienen activos de esta categoría (o subcategorías)
        descendant_cats = categoria.get_descendants(include_self=True)
        
        # Identificamos TODAS las ubicaciones que tienen activos de esta categoría de forma global
        ubicaciones_con_activos = set(Activo.objects.filter(
            modelo__categoria__in=descendant_cats
        ).values_list('ubicacion_id', flat=True).distinct())
        
        # Obtenemos las ubicaciones raíz
        roots = Ubicacion.objects.filter(padre__isnull=True)
        valid_roots = []
        
        for r in roots:
            # Una raíz es válida si ella o cualquiera de sus descendientes tiene activos
            r_all_ids = set(r.get_descendants(include_self=True).values_list('id', flat=True))
            if not r_all_ids.isdisjoint(ubicaciones_con_activos):
                valid_roots.append(r.id)
        
        sub_ubicaciones = Ubicacion.objects.filter(id__in=valid_roots).annotate(
            has_sub_ubicaciones=Exists(hijos_ubi_exists),
            has_activos=Exists(activos_ubi_exists)
        ).order_by('orden', 'nombre')
        
        # También listamos activos que pertenezcan a esta categoría pero NO tengan ubicación asignada
        activos_directos = Activo.objects.filter(
            modelo__categoria__in=descendant_cats, 
            ubicacion__isnull=True,
            padre__isnull=True
        ).select_related('modelo__categoria', 'ubicacion').order_by('nombre')

    context = {
        'sub_ubicaciones': sub_ubicaciones,
        'sub_categorias': sub_categorias,
        'activos_directos': activos_directos,
        'categorias_activos': dict(sorted(categorias_activos.items())),
        'cat_id': cat_id or (parent_id if parent_type == 'categoria' else None),
    }
    
    print(f"DEBUG EXPLORER: Total view time {time.time() - start_time:.4f}s")
    return render(request, 'admin/activos/includes/tree_level_fragment.html', context)

@staff_member_required
def api_explorer_search(request):
    """Buscador global para el explorador jerárquico"""
    from django.db import models
    from .models import Activo, Ubicacion, Categoria
    query = request.GET.get('q', '').strip()
    
    if not query or len(query) < 2:
        return HttpResponse("")
        
    # Buscar Activos
    activos = Activo.objects.filter(
        models.Q(nombre__icontains=query) | 
        models.Q(codigo_interno__icontains=query) |
        models.Q(serie__icontains=query) |
        models.Q(descripcion__icontains=query)
    ).select_related('ubicacion')[:15]
    
    # Buscar Ubicaciones
    ubicaciones = Ubicacion.objects.filter(nombre__icontains=query)[:10]
    
    # Buscar Categorías
    categorias = Categoria.objects.filter(nombre__icontains=query)[:10]
    
    from django.template.loader import render_to_string
    html = ""
    
    if categorias.exists():
        html += '<div class="category-header-mini" style="margin-left:0; background:#f1f5f9;">Categorías</div>'
        for c in categorias:
            html += render_to_string('admin/activos/includes/tree_item.html', {'node': c, 'type': 'categoria'}, request=request)
            
    if ubicaciones.exists():
        html += '<div class="category-header-mini" style="margin-left:0; background:#f1f5f9;">Ubicaciones</div>'
        for u in ubicaciones:
            html += render_to_string('admin/activos/includes/tree_item.html', {'node': u, 'type': 'ubicacion'}, request=request)
            
    if activos.exists():
        html += '<div class="category-header-mini" style="margin-left:0; background:#f1f5f9;">Activos</div>'
        for a in activos:
            html += render_to_string('admin/activos/includes/tree_item.html', {'node': a, 'type': 'activo'}, request=request)
            
    if not html:
        html = '<div style="padding: 20px; text-align: center; color: #94a3b8;">No se encontraron resultados</div>'
        
    from django.http import HttpResponse
    return HttpResponse(html)

@staff_member_required
def api_item_form(request, item_type, item_id):
    """Retorna un formulario HTML personalizado para editar un elemento y procesa su guardado"""
    from .models import Activo, Ubicacion, Categoria
    from django import forms
    
    if item_type == 'activo':
        instance = get_object_or_404(Activo, id=item_id)
        class CustomForm(forms.ModelForm):
            class Meta:
                model = Activo
                fields = ['nombre', 'codigo_interno', 'serie', 'descripcion', 'estado', 'ubicacion', 'padre', 'modelo']
                widgets = {
                    'nombre': forms.TextInput(attrs={'class': 'form-control'}),
                    'codigo_interno': forms.TextInput(attrs={'class': 'form-control'}),
                    'serie': forms.TextInput(attrs={'class': 'form-control'}),
                    'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
                    'estado': forms.Select(attrs={'class': 'form-control'}),
                    'ubicacion': forms.Select(attrs={'class': 'form-control'}),
                    'padre': forms.Select(attrs={'class': 'form-control'}),
                    'modelo': forms.Select(attrs={'class': 'form-control'}),
                }
    elif item_type == 'categoria':
        instance = get_object_or_404(Categoria, id=item_id)
        class CustomForm(forms.ModelForm):
            class Meta:
                model = Categoria
                fields = ['nombre', 'padre', 'icono', 'descripcion']
                widgets = {
                    'nombre': forms.TextInput(attrs={'class': 'form-control'}),
                    'padre': forms.Select(attrs={'class': 'form-control'}),
                    'icono': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ej: flash, water...'}),
                    'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
                }
    else:
        instance = get_object_or_404(Ubicacion, id=item_id)
        class CustomForm(forms.ModelForm):
            class Meta:
                model = Ubicacion
                fields = ['nombre', 'tipo', 'padre', 'orden', 'descripcion']
                widgets = {
                    'nombre': forms.TextInput(attrs={'class': 'form-control'}),
                    'tipo': forms.Select(attrs={'class': 'form-control'}),
                    'padre': forms.Select(attrs={'class': 'form-control'}),
                    'orden': forms.NumberInput(attrs={'class': 'form-control'}),
                    'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
                }

    if request.method == 'POST':
        form = CustomForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            return JsonResponse({'status': 'success', 'message': 'Cambios guardados correctamente.'})
        return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)
    
    form = CustomForm(instance=instance)
    
    # Optimización: No cargar miles de opciones en los select si no es necesario.
    # Para el formulario rápido, limitamos a la opción actual o vacía para evitar bloqueos por volumen.
    activos = []
    historial = []
    
    if item_type == 'activo':
        # Optimización de campos del formulario
        if hasattr(form.fields.get('modelo'), 'queryset'):
            from .models import Modelo
            form.fields['modelo'].queryset = Modelo.objects.all().select_related('marca').order_by('marca__nombre', 'nombre')
            form.fields['modelo'].required = False
        if hasattr(form.fields.get('ubicacion'), 'queryset'):
            form.fields['ubicacion'].queryset = instance.ubicacion._meta.model.objects.filter(id=instance.ubicacion.id) if instance.ubicacion else instance._meta.model.objects.none()
        if hasattr(form.fields.get('padre'), 'queryset'):
            form.fields['padre'].queryset = instance.__class__.objects.filter(id=instance.padre.id) if instance.padre else instance.__class__.objects.none()

        from mantenimiento.models import OrdenTrabajo, Aviso
        # OTs relacionadas directamente o por el campo ManyToMany
        ots = OrdenTrabajo.objects.filter(activos=instance).select_related('rutina', 'ubicacion').order_by('-inicio_programado')
        avisos = Aviso.objects.filter(activo=instance).select_related('ubicacion').order_by('-creado_en')
        
        # Combinar y convertir a lista para unificar cronología si fuera necesario, 
        # pero por ahora los pasamos por separado para mejor control en el template.
        historial_items = []
        for ot in ots:
            historial_items.append({
                'tipo': 'OT',
                'id': ot.id,
                'titulo': ot.rutina.nombre if ot.rutina else "Correctiva",
                'fecha': ot.inicio_programado,
                'estado': ot.get_estado_display(),
                'estado_slug': ot.estado.lower(),
                'color': 'blue' if ot.tipo == 'PREVENTIVA' else 'orange'
            })
        for av in avisos:
            historial_items.append({
                'tipo': 'AVISO',
                'id': av.id,
                'titulo': av.descripcion[:50],
                'fecha': av.creado_en,
                'estado': av.get_estado_display(),
                'estado_slug': av.estado.lower(),
                'color': 'red'
            })
        
        historial = sorted(historial_items, key=lambda x: x['fecha'], reverse=True)

    elif item_type == 'ubicacion':
        if hasattr(form.fields.get('padre'), 'queryset'):
            form.fields['padre'].queryset = instance.__class__.objects.filter(id=instance.padre.id) if instance.padre else instance.__class__.objects.none()
    elif item_type == 'categoria':
        if hasattr(form.fields.get('padre'), 'queryset'):
            form.fields['padre'].queryset = instance.__class__.objects.filter(id=instance.padre.id) if instance.padre else instance.__class__.objects.none()

    if item_type == 'ubicacion':
        # Obtener activos de esta ubicación y todas sus descendientes para la cuadrícula
        descendants = instance.get_descendants(include_self=True)
        queryset = Activo.objects.filter(ubicacion__in=descendants)
        
        cat_id = request.GET.get('cat_id')
        if cat_id:
            categoria = get_object_or_404(Categoria, id=cat_id)
            queryset = queryset.filter(modelo__categoria__in=categoria.get_descendants(include_self=True))

        activos = queryset.select_related(
            'modelo__marca', 'modelo__categoria', 'ubicacion'
        ).order_by('nombre')
    elif item_type == 'categoria':
        # Listamos todos los activos de esta categoría (y descendientes)
        descendants = instance.get_descendants(include_self=True)
        activos = Activo.objects.filter(modelo__categoria__in=descendants).select_related(
            'modelo__marca', 'modelo__categoria', 'ubicacion'
        ).order_by('nombre')

    context = {
        'form': form,
        'instance': instance,
        'type': item_type,
        'activos': activos,
        'historial': historial,
    }
    return render(request, 'admin/activos/includes/item_form_custom.html', context)

@staff_member_required
def api_ubicaciones_root(request):
    from .models import Ubicacion
    roots = Ubicacion.objects.filter(padre__isnull=True).order_by('orden', 'nombre')
    data = []
    for u in roots:
        data.append({
            'id': u.id,
            'nombre': u.nombre,
            'tipo': u.tipo,
            'has_children': u.sub_ubicaciones.exists()
        })
    return JsonResponse(data, safe=False)

@staff_member_required
def api_ubicaciones_children(request, parent_id):
    from .models import Ubicacion, Activo, Categoria
    
    # 1. Obtener sub-ubicaciones físicas
    children = Ubicacion.objects.filter(padre_id=parent_id).order_by('orden', 'nombre')
    data = []
    for u in children:
        data.append({
            'id': u.id,
            'nombre': u.nombre,
            'tipo': u.tipo,
            'has_children': u.sub_ubicaciones.exists() or Activo.objects.filter(ubicacion=u).exists()
        })
    
    # 2. Obtener categorías de activos en esta ubicación (Categorías virtuales)
    # Solo buscamos si NO hay más sub-ubicaciones o si queremos dar el nivel de sistema
    descendants = Ubicacion.objects.get(id=parent_id).get_descendants(include_self=True)
    cat_ids = Activo.objects.filter(ubicacion__in=descendants).values_list('modelo__categoria_id', flat=True).distinct()
    
    if cat_ids:
        categorias = Categoria.objects.filter(id__in=cat_ids).order_by('nombre')
        for c in categorias:
            data.append({
                'id': f"cat_{c.id}_{parent_id}", # Formato especial para identificarlo
                'nombre': c.nombre,
                'tipo': 'CATEGORIA',
                'has_children': False,
                'icono': c.icono or 'cube'
            })
            
    return JsonResponse(data, safe=False)

@staff_member_required
def api_ubicacion_detalle(request, ubicacion_id):
    from .models import Ubicacion, Activo
    from django.db.models import Count, Q
    
    try:
        ubicacion = Ubicacion.objects.get(id=ubicacion_id)
    except Ubicacion.DoesNotExist:
        return JsonResponse({'error': 'Ubicación no encontrada'}, status=404)
        
    # Obtener activos de esta ubicación y todas sus descendientes
    descendants = ubicacion.get_descendants(include_self=True)
    activos_qs = Activo.objects.filter(ubicacion__in=descendants).select_related('modelo__categoria__padre', 'modelo__categoria', 'modelo', 'ubicacion')
    
    # Filtro opcional por categoría
    cat_id = request.GET.get('cat_id')
    if cat_id:
        activos_qs = activos_qs.filter(modelo__categoria_id=cat_id)
        
    activos = activos_qs
    
    # Estructura de árbol: Root Name -> { data, subcats: { Sub Name -> [assets] } }
    groups = {}
    total_operativos = 0
    
    for activo in activos:
        # Estado
        if activo.estado == 'OPERATIVO':
            total_operativos += 1

        # Categorización
        cat_directa = activo.modelo.categoria if (activo.modelo and activo.modelo.categoria) else None
        
        # Agrupador Principal (Padre o Directa si no tiene padre)
        # Nota: Asumimos jerarquía de 2 niveles para visualización simple. 
        # Si tiene abuelo, este lógica tomará al padre inmediato como raíz de visualización.
        # Para ser más robustos en "Sistemas", idealmente buscaríamos la raíz, pero esto funciona para "Tipo -> Subtipo".
        cat_root = cat_directa.padre if (cat_directa and cat_directa.padre) else cat_directa
        
        root_name = cat_root.nombre if cat_root else "Otros"
        root_icon = cat_root.icono if cat_root else "cube"
        
        # Subcategoría (Solo si es diferente a la raíz)
        sub_name = cat_directa.nombre if (cat_directa and cat_directa != cat_root) else "_general_"
        
        if root_name not in groups:
            groups[root_name] = {
                'nombre': root_name,
                'icono': root_icon,
                'total_assets': 0,
                'subcats': {} 
            }
            
        groups[root_name]['total_assets'] += 1
        
        if sub_name not in groups[root_name]['subcats']:
            groups[root_name]['subcats'][sub_name] = []
            
        # Serializar activo
        groups[root_name]['subcats'][sub_name].append({
            'id': activo.id,
            'nombre': activo.nombre,
            'codigo': activo.codigo_interno or 'S/C',
            'serie': activo.serie,
            'modelo': activo.modelo.nombre if activo.modelo else None,
            'estado': activo.estado,
            'estado_display': activo.get_estado_display(),
            'descripcion': (activo.descripcion[:50] + '...') if (activo.descripcion and len(activo.descripcion) > 50) else (activo.descripcion or ''),
            'modelo_descripcion': (activo.modelo.descripcion[:50] + '...') if (activo.modelo and activo.modelo.descripcion and len(activo.modelo.descripcion) > 50) else (activo.modelo.descripcion if (activo.modelo and activo.modelo.descripcion) else ''),
            'ubicacion_nombre': activo.ubicacion.nombre if activo.ubicacion else 'Sin Ubicación',
            'is_child': activo.ubicacion_id != ubicacion.id,
        })

    # Procesar para JSON (Listas ordenadas)
    final_list = []
    for root_key in sorted(groups.keys()):
        g_data = groups[root_key]
        
        # Procesar subcategorías
        subs_list = []
        # Ponemos "_general_" al principio si existe
        if "_general_" in g_data['subcats']:
            subs_list.append({
                'nombre': 'General',
                'is_general': True,
                'activos': g_data['subcats'].pop("_general_")
            })
            
        # El resto ordenado alfabéticamente
        for sub_key in sorted(g_data['subcats'].keys()):
            subs_list.append({
                'nombre': sub_key,
                'is_general': False,
                'activos': g_data['subcats'][sub_key]
            })
            
        final_list.append({
            'nombre': g_data['nombre'],
            'icono': g_data['icono'],
            'total_items': g_data['total_assets'],
            'subcategorias': subs_list
        })
    
    return JsonResponse({
        'ubicacion': {
            'id': ubicacion.id,
            'nombre': ubicacion.nombre,
            'tipo': ubicacion.get_tipo_display(),
            'ruta': ubicacion.get_ruta_completa(),
            'descripcion': ubicacion.descripcion
        },
        'total_activos': activos.count(),
        'activos_operativos': total_operativos,
        'categorias': final_list
    })

@staff_member_required
def api_activo_detalle(request, activo_id):
    from .models import Activo
    
    try:
        activo = Activo.objects.select_related(
            'modelo__marca', 'modelo__categoria', 'ubicacion', 'responsable'
        ).get(id=activo_id)
    except Activo.DoesNotExist:
        return JsonResponse({'error': 'Activo no encontrado'}, status=404)
        
    data = {
        'id': activo.id,
        'nombre': activo.nombre,
        'codigo_interno': activo.codigo_interno,
        'serie': activo.serie,
        'estado': activo.estado,
        'estado_display': activo.get_estado_display(),
        'marca': activo.modelo.marca.nombre if (activo.modelo and activo.modelo.marca) else None,
        'modelo': activo.modelo.nombre if activo.modelo else None,
        'categoria': activo.modelo.categoria.nombre if (activo.modelo and activo.modelo.categoria) else None,
        'ubicacion': activo.ubicacion.ruta_completa if activo.ubicacion else 'Sin Ubicación',
        'responsable': activo.responsable.get_full_name() or activo.responsable.username if activo.responsable else 'Sin Asignar',
        'fecha_compra': activo.fecha_compra.strftime('%d/%m/%Y') if activo.fecha_compra else None,
        'costo': str(activo.costo) if activo.costo else None,
        'descripcion': activo.descripcion,
        'foto_url': activo.foto.url if activo.foto else None,
        'creado_en': activo.creado_en.strftime('%d/%m/%Y'),
        'legacy_ubicacion': activo.ubicacion_legacy
    }
    
    return JsonResponse(data)


@staff_member_required
@mobile_permission_required('mi_planta')
def mobile_activo_detalle(request, pk):
    """
    Vista detallada de un Activo optimizada para móviles.
    Permite a superusuarios subir una foto real directamente.
    """
    from django.contrib import messages
    activo = get_object_or_404(Activo.objects.select_related('modelo__marca', 'ubicacion', 'responsable'), pk=pk)
    
    # Procesar subida de foto solo para superusuarios
    if request.method == 'POST' and request.user.is_superuser and 'foto' in request.FILES:
        try:
            foto = request.FILES['foto']
            activo.foto = foto
            activo.save(update_fields=['foto'])
            messages.success(request, "Foto del activo actualizada correctamente.")
        except Exception as e:
            messages.error(request, f"Error al subir la foto: {str(e)}")
        return redirect('activos:mobile_activo_detalle', pk=pk)

    # Obtener OTs relacionadas recientes
    ots_recientes = activo.ordenes_trabajo.all().order_by('-inicio_programado')[:5]
    
    # Obtener avisos recientes
    from mantenimiento.models import Aviso
    avisos_recientes = Aviso.objects.filter(activo=activo).order_by('-creado_en')[:5]
    
    # Obtener puntos de medición con técnicos pre-cargados
    from django.db.models import Prefetch
    from .models.medicion import DocumentoMedicion
    
    puntos = activo.puntos_medicion.all().prefetch_related(
        Prefetch('lecturas', queryset=DocumentoMedicion.objects.select_related('tecnico'))
    )
    
    context = {
        'activo': activo,
        'ots_recientes': ots_recientes,
        'avisos_recientes': avisos_recientes,
        'puntos_medicion': puntos,
    }
    return render(request, 'activos/mobile_activo_detalle.html', context)


@staff_member_required
def mobile_busqueda_activos(request):
    """
    Buscador de activos y órdenes de trabajo optimizado para móviles.
    """
    from mantenimiento.models import OrdenTrabajo
    from callcenter.models import TiempoAcordado, SolicitudTicket
    query = request.GET.get('q', '').strip()
    activos = []
    ordenes = []
    tiempos_acordados = []
    tickets = []
    
    from core.models import ElementoApp
    secciones = ElementoApp.get_secciones_usuario(request.user)

    if query:
        # Buscar activos - Solo si tiene acceso a Mi Planta
        if 'mi_planta' in secciones:
            activos = Activo.objects.filter(
                Q(nombre__icontains=query) | 
                Q(codigo_interno__icontains=query) |
                Q(serie__icontains=query)
            ).select_related('ubicacion')[:20]
        
        # Buscar órdenes de trabajo (Cualquier estado) - Solo si tiene acceso a Tareas de Hoy
        if 'tareas_hoy' in secciones:
            ordenes = OrdenTrabajo.objects.filter(
                Q(id__icontains=query) |
                Q(codigo_de_orden__icontains=query) |
                Q(descripcion_corta__icontains=query) |
                Q(activos__nombre__icontains=query) |
                Q(activos__codigo_interno__icontains=query) |
                Q(activos__serie__icontains=query)
            ).select_related('ubicacion').distinct().order_by('-id')[:10]
        
        # Buscar Tiempos Acordados
        if 'tiempo_acordado' in secciones:
            tiempos_acordados = TiempoAcordado.objects.filter(
                Q(ticket__folio__icontains=query) |
                Q(motivo_extension__icontains=query) |
                Q(institucion__nombre__icontains=query)
            ).select_related('ticket', 'institucion', 'enlace')[:10]

        # Buscar Tickets de Call Center (NUEVO) - Solo si tiene acceso a Mis Avisos
        if 'mis_avisos' in secciones:
            tickets = SolicitudTicket.objects.filter(
                Q(folio__icontains=query) |
                Q(id_solicitud__icontains=query) |
                Q(solicitante__icontains=query) |
                Q(solicitud_descripcion__icontains=query)
            ).order_by('-fecha_solicitud')[:20]

        
        # Si solo hay un activo y ninguna orden/acuerdo/ticket, redirigir directo
        if activos.count() == 1 and not ordenes and not tiempos_acordados and not tickets:
            return redirect('activos:mobile_activo_detalle', pk=activos[0].id)
            
    return render(request, 'activos/mobile_busqueda.html', {
        'activos': activos,
        'ordenes': ordenes,
        'tiempos_acordados': tiempos_acordados,
        'tickets': tickets,
        'query': query
    })
@staff_member_required
@mobile_permission_required('mi_planta')
def mobile_ubicaciones(request, parent_id=None):
    """
    Explorador jerárquico de ubicaciones para la App (OPTIMIZADO).
    """
    from .models.ubicacion import Ubicacion
    from .models.plano import VisorPlano
    from mantenimiento.models import Rutina, Tipo as M_Tipo, Aviso
    from django.db.models import Count
    
    # Fotos y activos de la ubicación
    parent = None
    unique_categories = []
    categorias_agrupadas = []
    avisos_historial = []
    ubicacion_fotos = []
    activos_ubicacion = []
    breadcrumb_path = []
    
    if parent_id:
        parent = get_object_or_404(Ubicacion, pk=parent_id)
        ubicaciones_qs = Ubicacion.objects.filter(padre=parent)
        # Historial de avisos de esta ubicación específica
        from mantenimiento.models import Aviso
        from .models.foto_ubicacion import FotoUbicacion
        from .models.activo import Activo
        avisos_historial = Aviso.objects.filter(ubicacion=parent).select_related('solicitante', 'falla').order_by('-creado_en')[:10]
        descendants = parent.get_descendants(include_self=True)
        activos_qs = Activo.objects.filter(ubicacion__in=descendants).select_related(
            'modelo', 'modelo__marca', 'modelo__categoria', 'modelo__categoria__padre', 'ubicacion'
        )
        
        # New Hierarchical Grouping: Location -> Category -> Assets
        children = parent.sub_ubicaciones.all()
        branch_map = {child.id: child for child in children}
        
        ubicaciones_agrupadas = {}
        # Entry for direct assets
        ubicaciones_agrupadas['direct'] = {
            'id': 'direct',
            'nombre': 'Asignados Directamente', 
            'icono': 'pin',
            'is_direct': True, 
            'categorias': {}
        }
        
        # Initialize branches
        for child_id, child in branch_map.items():
            ubicaciones_agrupadas[child_id] = {
                'id': child_id,
                'nombre': child.nombre,
                'icono': child.categoria.icono if (child.categoria and child.categoria.icono) else 'location',
                'categorias': {}
            }

        def group_asset_in_category(cat_dict, asset):
            cat = None
            if asset.modelo and asset.modelo.categoria:
                cat = asset.modelo.categoria.padre or asset.modelo.categoria
            
            cat_key = str(cat.id) if cat else 'None'
            if cat_key not in cat_dict:
                cat_dict[cat_key] = {
                    'nombre': cat.nombre if cat else 'Otros',
                    'icono': cat.icono if cat else 'cube',
                    'activos': []
                }
            cat_dict[cat_key]['activos'].append(asset)

        # Optimization: Map every descendant ID to its immediate branch root ID under parent
        descendant_to_branch = {}
        for child_id, child in branch_map.items():
            child_descendants = child.get_descendants(include_self=True).values_list('id', flat=True)
            for d_id in child_descendants:
                descendant_to_branch[d_id] = child_id

        # Distribute assets
        for a in activos_qs:
            group_id = descendant_to_branch.get(a.ubicacion_id, 'direct')
            group_asset_in_category(ubicaciones_agrupadas[group_id]['categorias'], a)

        # Final list filtering out empty branches
        final_ubicaciones_agrupadas = []
        if ubicaciones_agrupadas['direct']['categorias']:
            # Sort categories for direct assets as well
            cats_list = sorted(ubicaciones_agrupadas['direct']['categorias'].values(), key=lambda x: x['nombre'])
            ubicaciones_agrupadas['direct']['categorias_sorted'] = cats_list
            final_ubicaciones_agrupadas.append(ubicaciones_agrupadas['direct'])
        
        for cid, group in ubicaciones_agrupadas.items():
            if cid != 'direct' and group['categorias']:
                # Sort categories within each location
                cats_list = sorted(group['categorias'].values(), key=lambda x: x['nombre'])
                group['categorias_sorted'] = cats_list
                final_ubicaciones_agrupadas.append(group)
        
        # Collect unique global categories for the grid to avoid repeats
        global_categories = {}
        for group in final_ubicaciones_agrupadas:
            for cat_key, cat_data in group['categorias'].items():
                if cat_key not in global_categories:
                    global_categories[cat_key] = {
                        'nombre': cat_data['nombre'],
                        'icono': cat_data['icono']
                    }
        unique_categories = sorted(global_categories.values(), key=lambda x: x['nombre'])
        
        # Replace the old context variable with the new one
        categorias_agrupadas = final_ubicaciones_agrupadas 
        
        ubicacion_fotos = FotoUbicacion.objects.filter(ubicacion=parent).order_by('-creado_en')
        activos_ubicacion = activos_qs # Flat list for the (11,424) count
        
        # Build breadcrumb path (ancestors)
        breadcrumb_path = []
        curr = parent.padre
        while curr:
            breadcrumb_path.insert(0, {'id': curr.id, 'nombre': curr.nombre})
            curr = curr.padre
    else:
        ubicaciones_qs = Ubicacion.objects.filter(padre__isnull=True)
    
    # Anotar conteos en una sola query para evitar crash por N+1
    ubicaciones = ubicaciones_qs.annotate(
        num_sub=Count('sub_ubicaciones', distinct=True),
        num_activos=Count('activos', distinct=True)
    ).select_related('categoria__mantenimiento_tipo').order_by('orden', 'nombre')
    
    # Mapear visores de forma masiva
    visores = {v.plano.ubicacion_id: v for v in VisorPlano.objects.select_related('plano').filter(plano__ubicacion__in=ubicaciones)}
    
    # Optimización para rutinas: Obtener todas las categorías de mantenimiento que tienen rutinas
    # y construir un set de IDs que incluyen sus descendientes (porque una rutina en padre aplica a hijos)
    # En realidad es al revés: para una ubicación (hijo), buscamos rutinas en sus padres.
    m_cats_with_rutinas = set(Rutina.objects.values_list('tipo_id', flat=True))
    
    for u in ubicaciones:
        u.has_sub = u.num_sub > 0
        u.has_activos = u.num_activos > 0
        u.visor = visores.get(u.id)
        
        # Verificar si tiene rutinas asociadas vía categoría
        u.has_rutinas = False
        if u.categoria and hasattr(u.categoria, 'mantenimiento_tipo'):
            m_cat = u.categoria.mantenimiento_tipo
            # Verificar si m_cat o algún ancestro tiene rutinas
            curr = m_cat
            while curr:
                if curr.id in m_cats_with_rutinas:
                    u.has_rutinas = True
                    break
                curr = curr.padre
        
    return render(request, 'activos/mobile_ubicaciones.html', {
        'ubicaciones': ubicaciones,
        'parent': parent,
        'avisos_historial': avisos_historial,
        'ubicacion_fotos': ubicacion_fotos,
        'activos_ubicacion': activos_ubicacion,
        'categorias_agrupadas': categorias_agrupadas,
        'breadcrumb_path': breadcrumb_path,
        'unique_categories': unique_categories,
    })

@staff_member_required
def activo_edit_view(request, pk):
    """
    Vista premium para editar un activo.
    """
    activo = get_object_or_404(
        Activo.objects.select_related(
            'modelo__marca', 'modelo__categoria', 'ubicacion', 'responsable', 'familia', 'plano', 'padre'
        ).prefetch_related('puntos_medicion', 'componentes'), 
        pk=pk
    )
    
    if request.method == 'POST':
        form = ActivoAdminForm(request.POST, request.FILES, instance=activo)
        if form.is_valid():
            form.save()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'status': 'success', 'message': 'Activo actualizado correctamente.'})
            messages.success(request, f'Activo "{activo.nombre}" actualizado correctamente.')
            return redirect('activos:activo_edit', pk=pk)
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)
    else:
        form = ActivoAdminForm(instance=activo)
        
    context = {
        'activo': activo,
        'form': form,
        'title': f'Editar Activo: {activo.nombre}',
    }
    return render(request, 'activos/activo_edit.html', context)


@staff_member_required
def print_altabaja(request, pk):
    """Vista de impresión para documentos de Alta/Baja."""
    from .models import DocumentoAltaBaja
    documento = get_object_or_404(DocumentoAltaBaja, pk=pk)
    items = documento.items.select_related(
        'activo', 'activo__modelo__marca', 'activo__ubicacion'
    ).all()
    
    # Archivos adjuntos que son imágenes
    archivos_img = [a for a in documento.archivos.all() if a.es_imagen]
    
    # Determinar si hay alguna foto (ya sea de los activos o adjunta al documento)
    photos_exist = any(item.activo.foto for item in items) or bool(archivos_img)
    
    return render(request, 'activos/print_altabaja.html', {
        'documento': documento,
        'items': items,
        'archivos_img': archivos_img,
        'photos_exist': photos_exist,
    })

@staff_member_required
def plano_documento_proxy(request, plano_id):
    from .models import Plano
    from django.http import FileResponse, Http404
    import mimetypes
    
    plano = get_object_or_404(Plano, id=plano_id)
    archivo = plano.archivo_actual
    if not archivo:
        raise Http404("Plano no tiene archivo")
        
    try:
        file_handle = archivo.open("rb")
        content_type, _ = mimetypes.guess_type(archivo.name)
        response = FileResponse(file_handle, content_type=content_type)
        response["Content-Disposition"] = f"inline; filename=\"{archivo.name.split('/')[-1]}\""
        # Cabeceras de seguridad
        response["X-Frame-Options"] = "SAMEORIGIN"
        response["Content-Security-Policy"] = "frame-ancestors 'self'"
        return response
    except Exception as e:
        raise Http404(f"Error al acceder al archivo: {str(e)}")
@staff_member_required
def activo_fiori_view(request, pk):
    """Vista de detalle de activo estilo SAP Fiori con gráficas y rutinas"""
    from mantenimiento.models import OrdenTrabajo, Aviso, Rutina, Programacion
    from auditorias.models import ResultadoAuditoria
    import json
    
    activo = get_object_or_404(
        Activo.objects.select_related(
            'modelo__marca', 'modelo__categoria', 'ubicacion', 'responsable', 'familia', 'plano'
        ), 
        pk=pk
    )
    
    # --- Navegación y Jerarquía de Ubicación ---
    breadcrumb_path = []
    if activo.ubicacion:
        curr = activo.ubicacion
        while curr:
            breadcrumb_path.insert(0, {'id': curr.id, 'nombre': curr.nombre})
            curr = curr.padre
            
    # --- Activos Cercanos / Similares ---
    activos_cercanos = []
    if activo.ubicacion:
        # 1. Buscar activos en la misma ubicación exacta (hermanos)
        # Priorizamos los que tienen la misma categoría para que sean "similares"
        cat_id = activo.modelo.categoria_id if activo.modelo else None
        
        siblings_qs = Activo.objects.filter(ubicacion=activo.ubicacion).exclude(id=activo.id).select_related('modelo__marca', 'modelo__categoria')
        
        # Primero los de la misma categoría
        similares = []
        if cat_id:
            similares = list(siblings_qs.filter(modelo__categoria_id=cat_id)[:6])
            
        # Si faltan para completar 6, tomamos cualquiera de la misma ubicación
        otros = []
        if len(similares) < 6:
            exclude_ids = [s.id for s in similares]
            otros = list(siblings_qs.exclude(id__in=exclude_ids)[:6-len(similares)])
            
        activos_cercanos = similares + otros
    
    # OTs relacionadas
    ots = OrdenTrabajo.objects.filter(activos=activo).select_related('rutina', 'tecnico').order_by('-inicio_programado')
    
    # Avisos/Tickets
    avisos = Aviso.objects.filter(activo=activo).order_by('-creado_en')
    
    # Auditorías
    auditorias = ResultadoAuditoria.objects.filter(activo=activo).select_related('auditoria').order_by('-fecha_escaneo')
    
    # Puntos de medición + Datos para gráficas
    puntos_raw = activo.puntos_medicion.all()
    puntos_data = []
    
    for p in puntos_raw:
        # Últimas 50 lecturas para el gráfico detallado (ordenadas cronológicamente)
        # Optimizamos trayendo técnico para la tabla
        lecturas_qs = p.lecturas.select_related('tecnico').order_by('fecha_lectura')
        all_lecturas = list(lecturas_qs)
        recent_lecturas = all_lecturas[-50:]
        
        puntos_data.append({
            'obj': p,
            'chart_labels': [l.fecha_lectura.strftime('%d/%m/%Y %H:%M') for l in recent_lecturas],
            'chart_data': [l.valor for l in recent_lecturas],
            'is_cumulative': p.es_acumulativo,
            'history': [{
                'date': l.fecha_lectura.strftime('%d/%m/%Y %H:%M'),
                'val': l.valor,
                'tech': l.tecnico.get_full_name() if l.tecnico else "---",
                'obs': l.observaciones or ""
            } for l in reversed(recent_lecturas)]
        })
    
    # Rutinas Aplicables
    # 1. Rutinas en las que el activo está explícitamente programado
    programaciones = Programacion.objects.filter(activos=activo).select_related('rutina__frecuencia', 'rutina__tipo')
    rutinas_ids = [prog.rutina_id for prog in programaciones]
    
    # 2. Rutinas sugeridas por el tipo/categoría del activo
    rutinas_sugeridas = []
    if activo.modelo and activo.modelo.categoria:
        # Buscar rutinas cuyo tipo esté vinculado a la categoría de este activo
        rutinas_sugeridas = Rutina.objects.filter(
            tipo__categoria_activo=activo.modelo.categoria
        ).exclude(id__in=rutinas_ids).select_related('frecuencia', 'tipo')

    context = {
        'activo': activo,
        'ots': ots,
        'avisos': avisos,
        'auditorias': auditorias,
        'puntos_data': puntos_data,
        'programaciones': programaciones,
        'rutinas_sugeridas': rutinas_sugeridas,
        'breadcrumb_path': breadcrumb_path,
        'activos_cercanos': activos_cercanos,
        'title': f"{activo.nombre} - SAP Fiori",
    }
    
    return render(request, 'activos/activo_fiori.html', context)


@staff_member_required
def fiori_explorer_view(request, ubicacion_id=None):
    """
    Nuevo explorador de activos con estética SAP Fiori.
    Permite navegar por ubicaciones y ver activos en un diseño master-detail.
    """
    from .models import Ubicacion
    
    # Si viene con un ID, intentamos cargar esa ubicación como punto focal
    initial_ubicacion = None
    if ubicacion_id:
        initial_ubicacion = get_object_or_404(Ubicacion, id=ubicacion_id)
    
    context = {
        'initial_id': ubicacion_id,
        'initial_name': initial_ubicacion.nombre if initial_ubicacion else None,
        'title': 'Explorador de Activos - SAP Fiori',
    }
    return render(request, 'activos/explorador_fiori.html', context)


# ==============================================================================
# MOBILE ADMIN - UBICACIONES QR
# ==============================================================================

from django.contrib.auth.decorators import user_passes_test

@user_passes_test(lambda u: u.is_superuser)
def mobile_admin_dashboard(request):
    return render(request, 'activos/mobile_admin_dashboard.html')

@user_passes_test(lambda u: u.is_superuser)
def mobile_admin_ubicaciones_scanner(request):
    return render(request, 'activos/mobile_admin_ubicaciones_scanner.html')

@user_passes_test(lambda u: u.is_superuser)
def mobile_admin_ubicaciones_handler(request):
    qr_code = request.GET.get('qr', '').strip()
    if not qr_code.startswith('UBC'):
        return JsonResponse({'status': 'error', 'message': 'Código no válido para ubicación.'})
        
    from activos.models import Ubicacion
    ubi = Ubicacion.objects.filter(codigo_qr=qr_code).first()
    
    if ubi:
        # Redirigir al detalle de ubicaciones abriendo el árbol en el ID? 
        # Ya que mobile_ubicaciones carga el árbol
        return JsonResponse({'status': 'success', 'found': True, 'url': f'/activos/app/ubicaciones/{ubi.id}/'})
    else:
        return JsonResponse({'status': 'success', 'found': False, 'url': f'/activos/app/admin/ubicacion/asignar/?qr={qr_code}'})

@user_passes_test(lambda u: u.is_superuser)
def mobile_admin_ubicacion_asignar(request):
    from activos.models import Ubicacion
    qr_code = request.GET.get('qr', '')
    
    if request.method == 'POST':
        final_parent_id = request.POST.get('final_parent_id')
        nueva_area = request.POST.get('nueva_area', '').strip()
        qr_asignar = request.POST.get('qr', '')
        
        target_ubi = None
        
        if final_parent_id:
            padre_final = Ubicacion.objects.get(id=final_parent_id)
            
            if nueva_area:
                target_ubi = Ubicacion.objects.create(
                    nombre=nueva_area,
                    padre=padre_final,
                    tipo='ESPACIO',
                    codigo_qr=qr_asignar
                )
            else:
                target_ubi = padre_final
                target_ubi.codigo_qr = qr_asignar
                target_ubi.save()
                
        if target_ubi:
            return redirect('activos:mobile_ubicaciones_child', parent_id=target_ubi.id)
            
    ubicaciones = Ubicacion.objects.filter(padre__isnull=True).order_by('nombre')
    return render(request, 'activos/mobile_admin_ubicacion_asignar.html', {
        'qr': qr_code,
        'ubicaciones': ubicaciones
    })

# =========================================================
# GENERADOR Y WYSIWYG PARA ETIQUETAS QR (LOTES)
# =========================================================
@user_passes_test(lambda u: u.is_superuser)
def qr_designer_view(request, plantilla_id):
    from django.shortcuts import get_object_or_404
    from .models import PlantillaEtiquetaQR
    from django.contrib import admin
    
    plantilla = get_object_or_404(PlantillaEtiquetaQR, id=plantilla_id)
    
    context = {
        **admin.site.each_context(request),
        'title': f'Diseñador Visual: {plantilla.nombre}',
        'plantilla': plantilla
    }
    return render(request, 'activos/qr_designer.html', context)

from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
@user_passes_test(lambda u: u.is_superuser)
def qr_designer_save(request, plantilla_id):
    import json
    from django.shortcuts import get_object_or_404
    from django.http import JsonResponse
    from .models import PlantillaEtiquetaQR
    
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Solo POST'}, status=405)
        
    try:
        data = json.loads(request.body)
        plantilla = get_object_or_404(PlantillaEtiquetaQR, id=plantilla_id)
        
        plantilla.ancho_cm = data.get('ancho_cm', plantilla.ancho_cm)
        plantilla.alto_cm = data.get('alto_cm', plantilla.alto_cm)
        plantilla.header_text = data.get('header_text', '')
        plantilla.footer_mode = data.get('footer_mode', 'secuencial')
        plantilla.font_size = data.get('font_size', 10)
        plantilla.qr_scale = data.get('qr_scale', 80)
        plantilla.border_thickness = data.get('border_thickness', 1)
        plantilla.margin_top = data.get('margin_top', 0)
        plantilla.compiled_html = data.get('compiled_html', '')
        
        plantilla.save()
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})

@user_passes_test(lambda u: u.is_superuser)
def qr_generator_dashboard(request):
    from django.contrib import admin
    from .models import PlantillaEtiquetaQR
    
    plantillas = PlantillaEtiquetaQR.objects.filter(activo=True)
    
    context = {
        **admin.site.each_context(request),
        'title': 'Impresión Masiva de Códigos QR',
        'plantillas': plantillas
    }
    return render(request, 'activos/qr_generator_dashboard.html', context)

@user_passes_test(lambda u: u.is_superuser)
def qr_generator_pdf(request):
    import base64
    import io
    import json
    import qrcode
    from django.http import HttpResponse
    from xhtml2pdf import pisa
    from .models import PlantillaEtiquetaQR
    
    if request.method != 'POST':
        return HttpResponse('Method not allowed', status=405)
        
    try:
        lotes_str = request.POST.get('lotes_json', '[]')
        try:
            lotes = json.loads(lotes_str)
        except Exception:
            lotes = []
        
        if not lotes:
            return HttpResponse('No hay lotes en la cola de impresión.', status=400)
            
        renderized_blocks = []
        first_plantilla = None
        
        for lote in lotes:
            plantilla_id = lote.get('plantilla_id')
            prefix = lote.get('prefix', '')
            digits = int(lote.get('digits', 5))
            start_num = int(lote.get('start', 1))
            qty = int(lote.get('qty', 10))
            
            try:
                plantilla = PlantillaEtiquetaQR.objects.get(id=plantilla_id)
                if not first_plantilla:
                    first_plantilla = plantilla
            except PlantillaEtiquetaQR.DoesNotExist:
                continue
                
            base_html = plantilla.compiled_html or ''
            
            for i in range(start_num, start_num + qty):
                formatted_num = str(i).zfill(digits)
                codigo = f"{prefix}{formatted_num}"
                
                qr = qrcode.QRCode(version=1, box_size=10, border=0)
                qr.add_data(codigo)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                
                buffer = io.BytesIO()
                img.save(buffer, format='PNG')
                qr_b64 = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode('utf-8')
                
                block = base_html.replace("{{ l.qr_code }}", qr_b64)
                block = block.replace("{{ l.secuencial }}", codigo)
                
                renderized_blocks.append(block)
        
        if not renderized_blocks:
            return HttpResponse('Ningún bloque generado válido.', status=400)
        
        page_w = first_plantilla.ancho_cm if first_plantilla else 5
        page_h = first_plantilla.alto_cm if first_plantilla else 5
        final_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                .label-page {{
                    page-break-after: always;
                    overflow: hidden;
                    margin: 0;
                    padding: 0;
                    border: none;
                }}
                @page {{
                    size: {page_w}cm {page_h}cm;
                    margin: 0cm;
                }}
                body {{
                    font-family: Arial, sans-serif;
                }}
            </style>
        </head>
        <body style="margin: 0; padding: 0;">
            <div class="label-page">
                {'</div><div class="label-page">'.join(renderized_blocks)}
            </div>
        </body>
        </html>
        """
        
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'inline; filename="lote_qr.pdf"'
        
        pisa_status = pisa.CreatePDF(final_html, dest=response)
        if pisa_status.err:
            return HttpResponse('Error generando PDF', status=500)
            
        return response
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return HttpResponse(f'Error Processing Lotes: {str(e)}', status=500)


# ─── Visor / Gestor de Ubicaciones ──────────────────────────────────────────

@staff_member_required
def ubicacion_manager_view(request):
    """Renders the mobile-style location manager/viewer."""
    from .models import Ubicacion
    total = Ubicacion.objects.count()
    raices = Ubicacion.objects.filter(padre__isnull=True).order_by('orden', 'nombre').count()
    return render(request, 'activos/ubicacion_manager.html', {
        'total': total,
        'raices': raices,
    })


@staff_member_required
def api_ubicacion_list(request):
    """Returns a JSON tree of ubicaciones, optionally filtered by parent."""
    from .models import Ubicacion
    from django.db.models import Count

    parent_id = request.GET.get('parent_id')
    q = request.GET.get('q', '').strip()

    if q:
        qs = Ubicacion.objects.filter(nombre__icontains=q).select_related('padre').order_by('nombre')[:50]
    elif parent_id:
        qs = Ubicacion.objects.filter(padre_id=parent_id).order_by('orden', 'nombre')
    else:
        qs = Ubicacion.objects.filter(padre__isnull=True).order_by('orden', 'nombre')

    TIPO_ICONS = {
        'EDIFICIO': 'business',
        'NIVEL': 'layers',
        'ESPACIO': 'grid',
        'BODEGA': 'archive',
        'OTRO': 'location',
    }

    data = []
    for u in qs:
        children_count = u.sub_ubicaciones.count()
        activos_count = u.activos.count() if hasattr(u, 'activos') else 0
        data.append({
            'id': u.id,
            'nombre': u.nombre,
            'tipo': u.tipo,
            'tipo_display': u.get_tipo_display(),
            'icon': TIPO_ICONS.get(u.tipo, 'location'),
            'codigo_qr': u.codigo_qr or '',
            'descripcion': u.descripcion or '',
            'orden': u.orden,
            'es_almacen': u.es_almacen,
            'padre_id': u.padre_id,
            'padre_nombre': u.padre.nombre if u.padre else None,
            'children_count': children_count,
            'activos_count': activos_count,
            'has_children': children_count > 0,
        })
    return JsonResponse({'results': data, 'parent_id': parent_id})


@staff_member_required
def api_ubicacion_save(request):
    """Creates or updates a Ubicacion via AJAX POST."""
    import json as _json
    from .models import Ubicacion

    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    try:
        data = _json.loads(request.body)
    except Exception:
        data = request.POST

    ubi_id = data.get('id')
    nombre = (data.get('nombre') or '').strip()
    tipo = data.get('tipo', 'OTRO')
    padre_id = data.get('padre_id') or None
    descripcion = data.get('descripcion', '')
    orden = int(data.get('orden') or 0)
    es_almacen = bool(data.get('es_almacen', False))
    codigo_qr = (data.get('codigo_qr') or '').strip() or None

    if not nombre:
        return JsonResponse({'error': 'El nombre es requerido.'}, status=400)

    try:
        if ubi_id:
            ubi = get_object_or_404(Ubicacion, id=ubi_id)
        else:
            ubi = Ubicacion()

        ubi.nombre = nombre
        ubi.tipo = tipo
        ubi.padre_id = padre_id if padre_id else None
        ubi.descripcion = descripcion
        ubi.orden = orden
        ubi.es_almacen = es_almacen
        ubi.codigo_qr = codigo_qr
        ubi.save()

        return JsonResponse({
            'status': 'success',
            'id': ubi.id,
            'nombre': ubi.nombre,
            'message': 'Ubicación guardada correctamente.',
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@staff_member_required
def api_ubicacion_delete(request, ubicacion_id):
    """Deletes a Ubicacion if it has no children or assets."""
    from .models import Ubicacion
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    ubi = get_object_or_404(Ubicacion, id=ubicacion_id)
    if ubi.sub_ubicaciones.exists():
        return JsonResponse({'error': 'No se puede eliminar: tiene sub-ubicaciones.'}, status=400)
    if ubi.activos.exists():
        return JsonResponse({'error': 'No se puede eliminar: tiene activos asignados.'}, status=400)

    ubi.delete()
    return JsonResponse({'status': 'success', 'message': 'Ubicación eliminada.'})

@login_required
def api_modelo_detalle(request, modelo_id):
    """Returns JSON data for a specific asset model."""
    from .models.activo import Modelo
    modelo = get_object_or_404(Modelo, id=modelo_id)
    data = {
        'id': modelo.id,
        'nombre': modelo.nombre,
        'marca': str(modelo.marca),
        'categoria': str(modelo.categoria) if modelo.categoria else "Sin Categoría",
        'descripcion': modelo.descripcion or "Sin descripción técnica adicional.",
        'imagen': modelo.imagen if modelo.imagen else None,
        'precio': str(modelo.precio_promedio) if modelo.precio_promedio else "0.00",
        'unidad': str(modelo.unidad_medida) if modelo.unidad_medida else "N/A"
    }
    return JsonResponse(data)
