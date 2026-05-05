from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db import IntegrityError, transaction
from django.db.models import Q, Count
from django.http import JsonResponse, HttpResponse
from django.urls import reverse
import json

from ..models import (
    PermisoTrabajo, TipoPermiso, VerificacionRequisito, RequisitoPermiso,
    ObjetoCatalogo, LevantamientoConfiscacion, ObjetoConfiscado, 
    FotoObjetoConfiscado, EntregaConfiscacion
)
from activos.models.ubicacion import Ubicacion
from mantenimiento.models import OrdenTrabajo, TecnicoPuesto

@staff_member_required
def mobile_mis_permisos(request):
    """
    Lista los permisos del usuario y de su equipo.
    """
    query = Q(solicitante=request.user)
    
    # Extensión: Permisos del mismo equipo/puesto
    puesto_tecnico = getattr(request.user, 'perfil_tecnico', None)
    if puesto_tecnico:
        puesto = puesto_tecnico.puesto
        query |= Q(solicitante__perfil_tecnico__puesto=puesto)
    
    permisos = PermisoTrabajo.objects.filter(query).select_related(
        'tipo', 'ubicacion', 'orden_trabajo', 'solicitante', 'autorizado_por'
    ).order_by('-id')
    
    return render(request, 'seguridad/mobile/mis_permisos.html', {
        'permisos': permisos,
        'puesto': puesto_tecnico.puesto if puesto_tecnico else None
    })

@staff_member_required
def mobile_permiso_detalle(request, pk):
    """
    Muestra el detalle expandido de un permiso con checklist interactivo.
    """
    permiso = get_object_or_404(PermisoTrabajo.objects.select_related(
        'tipo', 'ubicacion', 'orden_trabajo', 'solicitante', 'autorizado_por'
    ), pk=pk)
    
    # Verificar acceso
    puesto_tecnico = getattr(request.user, 'perfil_tecnico', None)
    puede_ver = (
        permiso.solicitante == request.user or 
        request.user.is_superuser or
        (puesto_tecnico and hasattr(permiso.solicitante, 'perfil_tecnico') and 
         permiso.solicitante.perfil_tecnico.puesto == puesto_tecnico.puesto)
    )
    
    if not puede_ver:
        return redirect('seguridad:mobile_mis_permisos')
    
    if request.method == 'POST':
        if permiso.estado == 'BORRADOR':
            # Reset checkboxes and NA to False because unchecked inputs don't send POST data
            VerificacionRequisito.objects.filter(permiso=permiso, requisito__tipo_respuesta='CHECK').update(valor_bool=False)
            VerificacionRequisito.objects.filter(permiso=permiso).update(no_aplica=False)

            for verif in permiso.verificaciones.all():
                if verif.requisito.tipo_respuesta == 'CHECK':
                    val = request.POST.get(f'verif_{verif.id}_bool')
                    verif.valor_bool = (val == 'on')
                elif verif.requisito.tipo_respuesta == 'NUMERICO':
                    val = request.POST.get(f'verif_{verif.id}_num')
                    verif.valor_numerico = float(val) if val else None
                elif verif.requisito.tipo_respuesta in ['TEXTO', 'FECHAHORA', 'TABLA']:
                    val = request.POST.get(f'verif_{verif.id}_text')
                    if val is not None:
                        verif.valor_texto = val
                
                if verif.requisito.tipo_respuesta == 'FOTO':
                    foto_file = request.FILES.get(f'verif_{verif.id}_foto')
                    if foto_file:
                        verif.foto = foto_file

                if verif.requisito.tipo_respuesta not in ['INSTRUCCION', 'HEADER']:
                    na_val = request.POST.get(f'verif_{verif.id}_na')
                    verif.no_aplica = (na_val == 'on')

                    com_val = request.POST.get(f'verif_{verif.id}_com')
                    if com_val is not None:
                        verif.comentarios = com_val

                verif.save()
        
        # Acciones de estado
        accion = request.POST.get('accion')
        if accion == 'solicitar' and permiso.estado == 'BORRADOR':
            permiso.estado = 'SOLICITADO'
            permiso.save()
        elif accion == 'aprobar' and permiso.estado == 'SOLICITADO':
            if request.user.has_perm('seguridad.change_permisotrabajo'):
                permiso.estado = 'APROBADO'
                permiso.autorizado_por = request.user
                permiso.fecha_autorizacion = timezone.now()
                permiso.save()
        
        return redirect('seguridad:mobile_permiso_detalle', pk=permiso.id)
    
    verificaciones = list(permiso.verificaciones.select_related('requisito').order_by('requisito__orden'))
    
    counter = 1
    for verif in verificaciones:
        if verif.requisito.tipo_respuesta != 'HEADER':
            verif.display_number = counter
            counter += 1
        else:
            verif.display_number = None
    
    return render(request, 'seguridad/mobile/permiso_detalle.html', {
        'permiso': permiso,
        'verificaciones': verificaciones
    })

@login_required
def api_buscar_tabla(request):
    """API genérica para autocompletado de tablas relacionadas (Typeahead).
    Resuelve dinámicamente cualquier modelo Django registrado en apps."""
    from django.apps import apps
    
    tabla = request.GET.get('tabla', '')
    q = request.GET.get('q', '')
    # mode=list returns all available models for the editor dropdown
    mode = request.GET.get('mode', '')
    
    if mode == 'list':
        # Return all registered models for the editor select
        modelos = []
        exclude_apps = {'contenttypes', 'sessions', 'admin', 'auth_permission',
                        'django_celery_beat', 'django_celery_results'}
        for model in apps.get_models():
            app = model._meta.app_label
            if app in exclude_apps:
                continue
            label = f"{app}.{model.__name__}"
            verbose = f"{model._meta.verbose_name_plural.title()} ({app})"
            modelos.append({'value': label, 'label': verbose})
        modelos.sort(key=lambda x: x['label'])
        return JsonResponse({'models': modelos})
    
    if not tabla:
        return JsonResponse({'results': []})
    
    resultados = []
    
    try:
        app_label, model_name = tabla.split('.')
        Model = apps.get_model(app_label, model_name)
    except (ValueError, LookupError):
        return JsonResponse({'results': [], 'error': f'Modelo {tabla} no encontrado'})
    
    qs = Model.objects.all()
    
    if q:
        # Build a dynamic Q filter across all char/text fields
        from django.db.models import CharField, TextField
        text_fields = [
            f.name for f in Model._meta.get_fields()
            if isinstance(f, (CharField, TextField)) and not f.primary_key
        ]
        if text_fields:
            q_filter = Q()
            for field_name in text_fields[:5]:  # limit to first 5 text fields
                q_filter |= Q(**{f'{field_name}__icontains': q})
            qs = qs.filter(q_filter)
    
    for obj in qs[:20]:
        resultados.append({'id': obj.pk, 'text': str(obj)})
        
    return JsonResponse({'results': resultados})

@staff_member_required
def mobile_generar_permiso(request, ot_id):
    """
    Genera un permiso desde una OT en la interfaz móvil.
    """
    ot = get_object_or_404(OrdenTrabajo, pk=ot_id)
    
    if request.method == 'POST':
        tipo_id = request.POST.get('tipo_permiso')
        if not tipo_id:
            return redirect('seguridad:mobile_generar_permiso', ot_id=ot.id)
        
        tipo = get_object_or_404(TipoPermiso, pk=tipo_id)
        
        # Crear Permiso
        permiso = PermisoTrabajo.objects.create(
            tipo=tipo,
            orden_trabajo=ot,
            ubicacion=ot.ubicacion,
            descripcion_trabajo=f"OT-{ot.id}: {ot.rutina.nombre if ot.rutina else ot.aviso.descripcion if ot.aviso else 'Mantenimiento'}",
            fecha_inicio=ot.inicio_programado,
            fecha_fin=ot.fin_programado or (ot.inicio_programado + timezone.timedelta(hours=4)),
            solicitante=request.user,
            estado='BORRADOR'
        )
        
        # Generar Checklist
        for req in tipo.requisitos.all():
            VerificacionRequisito.objects.create(
                permiso=permiso,
                requisito=req
            )
        
        return redirect('seguridad:mobile_permiso_detalle', pk=permiso.id)
    
    tipos_permiso = TipoPermiso.objects.all()
    
    return render(request, 'seguridad/mobile/generar_permiso.html', {
        'ot': ot,
        'tipos_permiso': tipos_permiso
    })

# --- Confiscaciones ---

@staff_member_required
def mobile_confiscaciones_lista(request):
    """
    Lista los levantamientos de objetos realizados.
    Separa los activos de los finalizados.
    """
    # Levantamientos activos (en curso)
    activos = LevantamientoConfiscacion.objects.filter(finalizado=False).select_related(
        'ubicacion', 'inspector'
    ).annotate(num_objetos=Count('objetos')).order_by('-fecha')
    
    # Historial de levantamientos
    historial = LevantamientoConfiscacion.objects.filter(finalizado=True).select_related(
        'ubicacion', 'inspector'
    ).annotate(num_objetos=Count('objetos')).order_by('-fecha')[:20]
    
    return render(request, 'seguridad/mobile/confiscaciones_list.html', {
        'activos': activos,
        'historial': historial
    })

@staff_member_required
def mobile_confiscacion_nueva(request):
    """
    Inicia un nuevo levantamiento (walkthrough).
    Permite navegación jerárquica y selección por QR.
    """
    parent_id = request.GET.get('parent_id')
    qr_code = request.GET.get('code')
    selected_id = request.GET.get('selected_id')
    ubicacion_seleccionada = None

    # Soporte para QR o selección manual de ID
    if qr_code:
        ubicacion_seleccionada = Ubicacion.objects.filter(codigo_qr=qr_code).first()
    elif selected_id:
        ubicacion_seleccionada = Ubicacion.objects.filter(pk=selected_id).first()

    if request.method == 'POST':
        ubicacion_id = request.POST.get('ubicacion')
        ubicacion = get_object_or_404(Ubicacion, pk=ubicacion_id)
        
        levantamiento = LevantamientoConfiscacion.objects.create(
            ubicacion=ubicacion,
            inspector=request.user,
            comentarios=request.POST.get('comentarios', '')
        )
        return redirect('seguridad:mobile_confiscacion_ejecutar', pk=levantamiento.id)
    
    # Navegación jerárquica
    parent = None
    if parent_id:
        parent = get_object_or_404(Ubicacion, pk=parent_id)
        ubicaciones = parent.sub_ubicaciones.all().order_by('orden', 'nombre')
    else:
        # Raíces
        ubicaciones = Ubicacion.objects.filter(padre__isnull=True).order_by('orden', 'nombre')
    
    return render(request, 'seguridad/mobile/confiscacion_nueva.html', {
        'ubicaciones': ubicaciones,
        'parent': parent,
        'ubicacion_seleccionada': ubicacion_seleccionada
    })

@staff_member_required
def mobile_confiscacion_ejecutar(request, pk):
    """
    Pantalla principal de ejecución de un levantamiento.
    Permite ver objetos ya registrados y acceso al escáner.
    """
    levantamiento = get_object_or_404(LevantamientoConfiscacion.objects.select_related('ubicacion'), pk=pk)
    objetos = levantamiento.objetos.select_related('catalogo_objeto').prefetch_related('fotos').all().order_by('-id')
    
    # Manejar finalización del recorrido
    if request.method == 'POST' and request.POST.get('action') == 'finalizar':
        levantamiento.finalizado = True
        levantamiento.fecha_fin = timezone.now()
        levantamiento.save()
        from django.contrib import messages
        messages.success(request, f"Recorrido {levantamiento.folio} finalizado exitosamente.")
        return redirect('seguridad:mobile_confiscaciones_lista')

    return render(request, 'seguridad/mobile/confiscacion_ejecutar.html', {
        'levantamiento': levantamiento,
        'objetos': objetos
    })

@staff_member_required
def mobile_almacen_recepcion(request):
    """
    Dashboard de inicio para Almacenes.
    Muestra lotes pendientes de recibir (en tránsito).
    """
    # Levantamientos que tienen al menos un objeto en tránsito
    lotes_transito = LevantamientoConfiscacion.objects.filter(
        objetos__status='TRANSITO'
    ).annotate(num_objetos=Count('objetos')).distinct().order_by('-id')
    
    # Manejar descubrimiento de lote vía GET (desde el escáner)
    codigo_escaneado = request.GET.get('code')
    if codigo_escaneado:
        objeto = ObjetoConfiscado.objects.filter(codigo_barras=codigo_escaneado).first()
        if objeto:
            return redirect('seguridad:mobile_almacen_validar_lote', pk=objeto.levantamiento_id)
        else:
            from django.contrib import messages
            messages.error(request, f"Código '{codigo_escaneado}' no encontrado.")

    return render(request, 'seguridad/mobile/almacen_recepcion.html', {
        'lotes': lotes_transito
    })

@staff_member_required
def mobile_almacen_validar_lote(request, pk):
    """
    Grid de validación para Almacenes.
    Muestra todo el lote y permite marcar recepción ítem por ítem.
    """
    levantamiento = get_object_or_404(LevantamientoConfiscacion, pk=pk)
    objetos = levantamiento.objetos.select_related('catalogo_objeto').prefetch_related('fotos').all().order_by('id')
    
    if request.method == 'POST' and request.POST.get('action') == 'finalizar_recepcion':
        # Marcar todo el lote como procesado (Opcional: solo si todos están almacenados)
        # Aquí podrías cerrar la sesión definitivamente para almacén
        from django.contrib import messages
        messages.success(request, f"Recepción de {levantamiento.folio} finalizada.")
        return redirect('seguridad:mobile_almacen_recepcion')

    return render(request, 'seguridad/mobile/almacen_validar_lote.html', {
        'levantamiento': levantamiento,
        'objetos': objetos
    })

@staff_member_required
def api_almacen_almacenar_objeto(request):
    """
    API AJAX para recibir y guardar un objeto en bodega.
    """
    from django.http import JsonResponse
    import json
    
    if request.method == 'POST':
        try:
            # Soportar Multipart (fotos) o JSON
            if request.content_type.startswith('multipart/form-data'):
                codigo = request.POST.get('codigo')
                levantamiento_id = request.POST.get('levantamiento_id')
                comentario = request.POST.get('comentario', '')
                ubicacion = request.POST.get('ubicacion', '')
                fotos = request.FILES.getlist('fotos')
            else:
                data = json.loads(request.body)
                codigo = data.get('codigo')
                levantamiento_id = data.get('levantamiento_id')
                comentario = data.get('comentario', '')
                ubicacion = data.get('ubicacion', '')
                fotos = []

            objeto = ObjetoConfiscado.objects.filter(
                codigo_barras=codigo, 
                levantamiento_id=levantamiento_id
            ).first()
            
            if objeto:
                objeto.status = 'ALMACENADO'
                if comentario:
                    objeto.comentario_almacen = comentario
                if ubicacion:
                    objeto.ubicacion_almacen = ubicacion
                objeto.save()

                # Guardar fotos de evidencia de almacén
                for f in fotos:
                    FotoObjetoConfiscado.objects.create(
                        objeto=objeto,
                        foto=f,
                        etapa='ALMACEN'
                    )

                return JsonResponse({
                    'status': 'success', 
                    'objeto_id': objeto.id,
                    'nombre': objeto.catalogo_objeto.nombre,
                    'tiene_novedad': bool(comentario) or len(fotos) > 0
                })
            else:
                return JsonResponse({'status': 'error', 'message': 'Código no encontrado en este lote.'}, status=404)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

@staff_member_required
def mobile_confiscacion_confirmar_carga(request, pk):
    """
    Etapa 2: Grid visual para confirmar que los objetos se están movilizando.
    Muestra fotos y permite escaneo rápido.
    """
    levantamiento = get_object_or_404(LevantamientoConfiscacion, pk=pk)
    # Todos los objetos del levantamiento
    objetos = levantamiento.objetos.select_related('catalogo_objeto').prefetch_related('fotos').all().order_by('id')
    
    if request.method == 'POST' and request.POST.get('action') == 'finalizar_carga':
        levantamiento.finalizado = True
        levantamiento.fecha_fin = timezone.now()
        levantamiento.save()
        from django.contrib import messages
        messages.success(request, f"Carga de {levantamiento.folio} finalizada. En camino a bodega.")
        return redirect('seguridad:mobile_confiscaciones_lista')

    return render(request, 'seguridad/mobile/confiscacion_confirmar_carga.html', {
        'levantamiento': levantamiento,
        'objetos': objetos
    })

@staff_member_required
def api_confirmar_carga_objeto(request):
    """
    Endpoint AJAX para confirmar carga de un objeto individual.
    """
    from django.http import JsonResponse
    import json
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            codigo = data.get('codigo')
            levantamiento_id = data.get('levantamiento_id')
            
            objeto = ObjetoConfiscado.objects.filter(
                codigo_barras=codigo, 
                levantamiento_id=levantamiento_id
            ).first()
            
            if objeto:
                objeto.status = 'TRANSITO'
                objeto.save()
                return JsonResponse({
                    'status': 'success', 
                    'objeto_id': objeto.id,
                    'nombre': objeto.catalogo_objeto.nombre
                })
            else:
                return JsonResponse({'status': 'error', 'message': 'Código no encontrado en este levantamiento.'}, status=404)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

@staff_member_required
def mobile_confiscacion_agregar_objeto(request, pk):
    """
    Formulario para registrar un objeto confiscado.
    Recibe el código escaneado inicialmente por GET o vacío.
    """
    levantamiento = get_object_or_404(LevantamientoConfiscacion, pk=pk)
    codigo = request.GET.get('codigo', '')
    generar = request.GET.get('generar') == '1'
    
    # NUEVO: Generación automática de código si se solicita
    if generar and not codigo:
        import random, string
        today = timezone.now().strftime('%Y%m%d')
        # Intentar hasta encontrar uno que no exista
        while True:
            rand = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
            codigo_gen = f"CONF-{today}-{rand}"
            if not ObjetoConfiscado.objects.filter(codigo_barras=codigo_gen).exists():
                codigo = codigo_gen
                break

    # NUEVO: Verificación inmediata al llegar del escáner
    if codigo and not generar:
        objeto_existente = ObjetoConfiscado.objects.filter(codigo_barras=codigo).first()
        if objeto_existente:
            from django.contrib import messages
            messages.info(request, f"El código '{codigo}' ya está registrado. Redirigiendo a edición...")
            return redirect('seguridad:mobile_confiscacion_editar_objeto', pk=objeto_existente.id)
    
    if request.method == 'POST':
        catalogo_id = request.POST.get('catalogo_objeto')
        catalogo = get_object_or_404(ObjetoCatalogo, pk=catalogo_id)
        codigo_barras = request.POST.get('codigo_barras')
        
        try:
            objeto = ObjetoConfiscado.objects.create(
                levantamiento=levantamiento,
                catalogo_objeto=catalogo,
                codigo_barras=codigo_barras,
                descripcion=request.POST.get('descripcion', ''),
                ubicacion_especifica=request.POST.get('ubicacion_especifica', ''),
                status='IDENTIFICADO'
            )
            
            # Procesar fotos (múltiples)
            files = request.FILES.getlist('fotos')
            for f in files:
                FotoObjetoConfiscado.objects.create(
                    objeto=objeto,
                    foto=f
                )
                
            # Si fue generado, redirigir a impresión automáticamente
            generar = request.POST.get('was_generated') == 'True'
            if generar:
                return redirect('seguridad:mobile_confiscacion_imprimir_etiqueta', pk=objeto.id)
                
            return redirect('seguridad:mobile_confiscacion_ejecutar', pk=levantamiento.id)
            
        except IntegrityError:
            from django.contrib import messages
            objeto_existente = ObjetoConfiscado.objects.filter(codigo_barras=codigo_barras).first()
            messages.error(request, f"Error: El código '{codigo_barras}' ya está registrado. ¿Desea editar el registro existente?")
            
            catalogo = ObjetoCatalogo.objects.all()
            return render(request, 'seguridad/mobile/confiscacion_formulario_objeto.html', {
                'levantamiento': levantamiento,
                'codigo_inicial': codigo_barras,
                'catalogo_objetos': catalogo,
                'objeto_existente': objeto_existente
            })
    
    catalogo = ObjetoCatalogo.objects.all()
    
    return render(request, 'seguridad/mobile/confiscacion_formulario_objeto.html', {
        'levantamiento': levantamiento,
        'codigo_inicial': codigo,
        'catalogo_objetos': catalogo,
        'fue_generado': generar
    })

@staff_member_required
def mobile_confiscacion_editar_objeto(request, pk):
    """
    Vista para editar un objeto confiscado existente.
    """
    objeto = get_object_or_404(ObjetoConfiscado, pk=pk)
    
    if request.method == 'POST':
        catalogo_id = request.POST.get('catalogo_objeto')
        objeto.catalogo_objeto = get_object_or_404(ObjetoCatalogo, pk=catalogo_id)
        objeto.descripcion = request.POST.get('descripcion', '')
        objeto.ubicacion_especifica = request.POST.get('ubicacion_especifica', '')
        objeto.save()
        
        # Añadir fotos nuevas si hay
        files = request.FILES.getlist('fotos')
        for f in files:
            FotoObjetoConfiscado.objects.create(
                objeto=objeto,
                foto=f
            )
            
        from django.contrib import messages
        messages.success(request, f"Objeto {objeto.codigo_barras} actualizado correctamente.")
        return redirect('seguridad:mobile_confiscacion_ejecutar', pk=objeto.levantamiento.id)
        
    catalogo = ObjetoCatalogo.objects.all()
    return render(request, 'seguridad/mobile/confiscacion_formulario_editar.html', {
        'objeto': objeto,
        'catalogo_objetos': catalogo
    })

@staff_member_required
@require_POST
def mobile_confiscacion_eliminar_objeto(request, pk):
    objeto = get_object_or_404(ObjetoConfiscado, pk=pk)
    levantamiento_id = objeto.levantamiento.id
    objeto.delete()
    messages.success(request, "Objeto eliminado correctamente.")
    return redirect('seguridad:mobile_confiscacion_ejecutar', pk=levantamiento_id)

@staff_member_required
def mobile_confiscacion_objeto_actualizar(request, pk):
    """
    Actualiza el estado de un objeto confiscado (ej. a RETIRADO).
    """
    objeto = get_object_or_404(ObjetoConfiscado, pk=pk)
    nuevo_status = request.POST.get('status')
    
    if nuevo_status in dict(ObjetoConfiscado.STATUS_CHOICES):
        objeto.status = nuevo_status
        if nuevo_status == 'RETIRADO':
            objeto.fecha_retiro = timezone.now()
        objeto.save()
        
    return redirect('seguridad:mobile_confiscacion_ejecutar', pk=objeto.levantamiento.id)

@staff_member_required
def mobile_almacen_entrega_validar(request):
    """
    Vista para gestionar el 'Carrito de Entrega'.
    El almacenista escanea objetos y aquí llena los datos del retirante.
    """
    codigos_raw = request.GET.get('codigos', '')
    codigos = [c.strip() for c in codigos_raw.split(',') if c.strip()]
    
    objetos = ObjetoConfiscado.objects.filter(
        codigo_barras__in=codigos,
        status='ALMACENADO'
    ).select_related('catalogo_objeto', 'levantamiento')
    
    return render(request, 'seguridad/mobile/almacen_entrega_validar.html', {
        'objetos': objetos,
        'codigos_vivos': ','.join([o.codigo_barras for o in objetos])
    })

@csrf_exempt
@login_required
def api_almacen_confirmar_entrega(request):
    """
    API Multipart para procesar la entrega final de materiales.
    Crea el registro de Entrega y marca objetos como RETIRADO.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

    try:
        nombre_retirante = request.POST.get('nombre_retirante')
        dni_retirante = request.POST.get('dni_retirante')
        comentarios = request.POST.get('comentarios', '')
        objeto_ids = [idx for idx in request.POST.get('objeto_ids', '').split(',') if idx]
        
        foto_id = request.FILES.get('foto_identidad')
        foto_entrega = request.FILES.get('foto_entrega')

        if not nombre_retirante or not objeto_ids:
            return JsonResponse({'status': 'error', 'message': 'Faltan datos obligatorios (Nombre o Objetos)'}, status=400)

        with transaction.atomic():
            # Crear cabecera de entrega
            entrega = EntregaConfiscacion.objects.create(
                nombre_retirante=nombre_retirante,
                dni_retirante=dni_retirante,
                foto_identidad=foto_id,
                foto_entrega=foto_entrega,
                entregado_por=request.user,
                comentarios=comentarios
            )

            # Actualizar objetos
            objetos = ObjetoConfiscado.objects.filter(id__in=objeto_ids)
            for obj in objetos:
                obj.status = 'RETIRADO'
                obj.entrega = entrega
                obj.fecha_retiro = timezone.now()
                obj.save()

        return JsonResponse({
            'status': 'success', 
            'entrega_id': entrega.id,
            'pdf_url': reverse('seguridad:mobile_confiscacion_entrega_pdf', args=[entrega.id])
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@staff_member_required
def mobile_confiscacion_entrega_pdf_view(request, pk):
    """ Genera el PDF del acta de entrega de material confiscado """
    entrega = get_object_or_404(EntregaConfiscacion, pk=pk)
    objetos = entrega.objetos_entregados.all()
    
    # Convertir fotos a Base64 para el PDF
    import base64
    foto_id_b64 = ""
    if entrega.foto_identidad:
        try:
            with entrega.foto_identidad.open('rb') as f:
                foto_id_b64 = base64.b64encode(f.read()).decode('utf-8')
        except Exception as e:
            print(f"Error encode ID photo: {e}")

    foto_entrega_b64 = ""
    if entrega.foto_entrega:
        try:
            with entrega.foto_entrega.open('rb') as f:
                foto_entrega_b64 = base64.b64encode(f.read()).decode('utf-8')
        except Exception as e:
            print(f"Error encode Delivery photo: {e}")

    # Logo oficial en Base64
    import os
    from django.conf import settings
    logo_path = os.path.join(settings.BASE_DIR, 'activos', 'static', 'activos', 'img', 'logo_operadora_cc.png')
    logo_dcc_b64 = ""
    if os.path.exists(logo_path):
        try:
            with open(logo_path, "rb") as image_file:
                logo_dcc_b64 = base64.b64encode(image_file.read()).decode('utf-8')
        except Exception:
            pass

    context = {
        'entrega': entrega,
        'objetos': objetos,
        'fecha': timezone.now(),
        'foto_id_b64': foto_id_b64,
        'foto_entrega_b64': foto_entrega_b64,
        'logo_dcc_b64': logo_dcc_b64,
    }
    
    from .pdf_views import render_to_pdf
    pdf = render_to_pdf('seguridad/pdf/recibo_entrega.html', context)
    
    if pdf:
        response = HttpResponse(pdf, content_type='application/pdf')
        filename = f"Recibo_Entrega_{entrega.id}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    return HttpResponse("Error generando PDF", status=500)

@staff_member_required
def mobile_confiscacion_imprimir_etiqueta(request, pk):
    """
    Genera una etiqueta de 58mm con QR para un objeto confiscado.
    """
    import qrcode
    import io
    import base64
    from django.http import HttpResponse

    objeto = get_object_or_404(ObjetoConfiscado, pk=pk)
    
    # Generar QR
    qr = qrcode.QRCode(version=1, box_size=10, border=1)
    qr.add_data(objeto.codigo_barras)
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')
    
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    qr_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

    # Ubicación jerárquica del levantamiento
    ubicacion = objeto.levantamiento.ubicacion
    ubicacion_jerarquica = ubicacion.get_ruta_completa() if ubicacion else 'Sin ubicación'
    if objeto.ubicacion_especifica:
        ubicacion_jerarquica += f" ({objeto.ubicacion_especifica})"

    # Nombre del usuario que genera la etiqueta (logueado)
    usuario_actual = request.user
    nombre_usuario = usuario_actual.get_full_name() or usuario_actual.username if usuario_actual.is_authenticated else 'Desconocido'

    return render(request, 'seguridad/mobile/confiscacion_imprimir.html', {
        'objeto': objeto,
        'qr_b64': qr_b64,
        'ahora': timezone.now(),
        'ubicacion_jerarquica': ubicacion_jerarquica,
        'nombre_usuario': nombre_usuario,
    })
@login_required
def mobile_perfil(request):
    """
    Muestra la interfaz de perfil del usuario logueado.
    """
    perfil = getattr(request.user, 'perfil_tecnico', None)
    
    return render(request, 'seguridad/mobile/perfil.html', {
        'perfil': perfil,
        'usuario': request.user
    })
@csrf_exempt
@login_required
def api_crear_objeto_catalogo(request):
    """
    API para crear un nuevo tipo de objeto en el catálogo desde el móvil.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
    
    try:
        data = json.loads(request.body)
        nombre = data.get('nombre', '').strip()
        
        if not nombre:
            return JsonResponse({'status': 'error', 'message': 'El nombre es obligatorio'}, status=400)
        
        # Crear o obtener si ya existe
        objeto_tipo, created = ObjetoCatalogo.objects.get_or_create(nombre=nombre)
        
        return JsonResponse({
            'status': 'success',
            'id': objeto_tipo.id,
            'nombre': objeto_tipo.nombre,
            'created': created
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
