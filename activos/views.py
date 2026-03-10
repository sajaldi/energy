from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from .forms import ActivoAdminForm
from .models import VisorPlano, PinPlano, Activo
import json
from django.views.decorators.csrf import csrf_exempt
from celery.result import AsyncResult
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages

def visor_plano(request, visor_id):
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
    proyectos_visor = visor.proyectos.all()
    
    context = {
        'visor': visor,
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
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

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
    from .models import Ubicacion
    children = Ubicacion.objects.filter(padre_id=parent_id).order_by('orden', 'nombre')
    data = []
    for u in children:
        data.append({
            'id': u.id,
            'nombre': u.nombre,
            'tipo': u.tipo,
            'has_children': u.sub_ubicaciones.exists()
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
    activos = Activo.objects.filter(ubicacion__in=descendants).select_related('modelo__categoria__padre', 'modelo__categoria', 'modelo', 'ubicacion')
    
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
def mobile_activo_detalle(request, pk):
    """
    Vista detallada de un Activo optimizada para móviles.
    """
    activo = get_object_or_404(Activo.objects.select_related('modelo__marca', 'ubicacion', 'responsable'), pk=pk)
    
    # Obtener OTs relacionadas recientes
    ots_recientes = activo.ordenes_trabajo.all().order_by('-inicio_programado')[:5]
    
    # Obtener puntos de medición
    puntos = activo.puntos_medicion.all().prefetch_related('lecturas')
    
    context = {
        'activo': activo,
        'ots_recientes': ots_recientes,
        'puntos_medicion': puntos,
    }
    return render(request, 'activos/mobile_activo_detalle.html', context)


@staff_member_required
def mobile_busqueda_activos(request):
    """
    Buscador de activos optimizado para móviles.
    """
    query = request.GET.get('q', '').strip()
    activos = []
    
    if query:
        activos = Activo.objects.filter(
            models.Q(nombre__icontains=query) | 
            models.Q(codigo_interno__icontains=query) |
            models.Q(serie__icontains=query)
        ).select_related('ubicacion')[:20]
        
        # Si solo hay uno, redirigir directo
        if activos.count() == 1:
            return redirect('activos:mobile_activo_detalle', pk=activos[0].id)
            
    return render(request, 'activos/mobile_busqueda.html', {
        'activos': activos,
        'query': query
    })
@staff_member_required
def mobile_ubicaciones(request, parent_id=None):
    """
    Explorador jerárquico de ubicaciones para la App (OPTIMIZADO).
    """
    from .models.ubicacion import Ubicacion
    from .models.plano import VisorPlano
    from mantenimiento.models import Rutina, Tipo as M_Tipo
    from django.db.models import Count
    
    parent = None
    if parent_id:
        parent = get_object_or_404(Ubicacion, pk=parent_id)
        ubicaciones_qs = Ubicacion.objects.filter(padre=parent)
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
