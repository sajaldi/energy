import collections
from datetime import datetime, timedelta
import collections
from datetime import datetime, timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib.auth.models import User, Group
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from django.db.models import Count, Q, Min
from core.decorators import mobile_permission_required
from ..models import Programacion, OrdenTrabajo, Aviso, ValorPasoOrden, PasoRutina, Falla, FotoAviso, ArchivoOrdenTrabajo
from activos.models import Activo, Ubicacion, DocumentoMedicion, PuntoMedicion
from ..tasks import task_generar_ot_pdf

@staff_member_required
@mobile_permission_required('tareas_hoy')
def mobile_cronograma(request):
    query = request.GET.get('q', '').strip()
    user_filter = Q()
    if not request.user.is_superuser:
        user_filter = Q(ordenes__tecnico=request.user) | Q(ordenes__equipo__in=request.user.groups.all())
    
    progs = Programacion.objects.select_related('rutina__frecuencia', 'rutina__tipo', 'rutina__puesto_trabajo')
    
    if query:
        progs = progs.filter(
            Q(rutina__nombre__icontains=query) |
            Q(ordenes__activos__nombre__icontains=query) |
            Q(ordenes__activos__codigo_interno__icontains=query)
        )

    if not request.user.is_superuser: 
        progs = progs.filter(user_filter)
    
    progs = progs.annotate(
        total_ots=Count('ordenes', filter=user_filter if not request.user.is_superuser else None), 
        completas_ots=Count('ordenes', filter=(Q(ordenes__estado='REALIZADA') & user_filter) if not request.user.is_superuser else Q(ordenes__estado='REALIZADA')), 
        proxima_ot=Min('ordenes__inicio_programado', filter=(Q(ordenes__inicio_programado__gte=timezone.now()) & user_filter) if not request.user.is_superuser else Q(ordenes__inicio_programado__gte=timezone.now()))
    ).distinct().order_by('rutina__nombre')
    
    for p in progs: 
        p.progreso_porcentaje = int((p.completas_ots / p.total_ots) * 100) if p.total_ots > 0 else 0
        
    return render(request, 'mantenimiento/mobile_cronograma.html', {
        'programaciones': progs,
        'search_query': query
    })

@staff_member_required
@mobile_permission_required('tareas_hoy')
def mobile_programacion_detalle(request, pk):
    prog = get_object_or_404(Programacion, pk=pk)
    ots_q = prog.ordenes.all()
    if not request.user.is_superuser: ots_q = ots_q.filter(Q(tecnico=request.user) | Q(equipo__in=request.user.groups.all())).distinct()
    ots = ots_q.order_by('inicio_programado'); m_dict = collections.defaultdict(list)
    for ot in ots: m_dict[ot.inicio_programado.strftime('%m-%Y')].append(ot)
    m_data = []
    mn = {'01':'Enero','02':'Febrero','03':'Marzo','04':'Abril','05':'Mayo','06':'Junio','07':'Julio','08':'Agosto','09':'Septiembre','10':'Octubre','11':'Noviembre','12':'Diciembre'}
    for mk in sorted(m_dict.keys(), key=lambda x: datetime.strptime(x, '%m-%Y')):
        m_num, y_num = mk.split('-')
        m_data.append({'nombre': f"{mn[m_num]} {y_num}", 'ots': m_dict[mk]})
    return render(request, 'mantenimiento/mobile_cronograma_detalle.html', {'programacion': prog, 'meses_data': m_data})

@staff_member_required
@mobile_permission_required('tareas_hoy')
def mobile_ot_detalle(request, pk):
    ot = get_object_or_404(OrdenTrabajo.objects.select_related('rutina', 'ubicacion', 'tecnico', 'supervisor', 'aviso', 'programacion').prefetch_related('activos', 'archivos'), pk=pk)
    
    # Listas para asignación
    supervisores = User.objects.filter(
        Q(is_staff=True) |
        Q(groups__name='Supervisor') | 
        Q(perfil_tecnico__puesto__nombre__icontains='Supervisor')
    ).distinct().order_by('first_name')
    tecnicos = User.objects.filter(Q(groups__name='Tecnicos') | Q(perfil_tecnico__isnull=False)).distinct().order_by('first_name')
    
    is_gerente = request.user.groups.filter(name='Gerentes').exists() or request.user.is_superuser
    
    ubicaciones = None
    if not ot.ubicacion:
        ubicaciones = Ubicacion.objects.filter(padre__isnull=True).order_by('nombre')
    
    context = {
        'ot': ot,
        'supervisores': supervisores,
        'tecnicos': tecnicos,
        'is_gerente': is_gerente,
        'ubicaciones': ubicaciones,
        'resultados': ot.resultados_checklist.select_related('paso').order_by('paso__orden'),
    }

    return render(request, 'mantenimiento/mobile_ot_detalle.html', context)

@staff_member_required
def mobile_ot_update_ajax(request, pk):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
    
    ot = get_object_or_404(OrdenTrabajo, pk=pk)
    is_gerente = request.user.groups.filter(name='Gerentes').exists() or request.user.is_superuser
    
    # Solo permitir cambios si la orden no está FINALIZADA (a menos que sea Gerente)
    if ot.estado == 'REALIZADA' and not is_gerente:
        return JsonResponse({'status': 'error', 'message': 'No se puede modificar una orden finalizada'}, status=400)

    tecnico_id = request.POST.get('tecnico')
    supervisor_id = request.POST.get('supervisor')
    fecha_str = request.POST.get('inicio_programado')
    ubicacion_id = request.POST.get('ubicacion')
    
    try:
        if tecnico_id:
            ot.tecnico = User.objects.get(pk=tecnico_id) if tecnico_id != 'none' else None
        
        if supervisor_id:
            ot.supervisor = User.objects.get(pk=supervisor_id) if supervisor_id != 'none' else None
            
        if ubicacion_id:
            ot.ubicacion = Ubicacion.objects.get(pk=ubicacion_id) if ubicacion_id != 'none' else None
            
        if fecha_str:
            # Formato esperado: YYYY-MM-DDTHH:MM (datetime-local)
            new_date = datetime.fromisoformat(fecha_str)
            if timezone.is_naive(new_date):
                new_date = timezone.make_aware(new_date)
            ot.inicio_programado = new_date
            
        ot.save()
        return JsonResponse({'status': 'success', 'message': 'Orden actualizada correctamente'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@staff_member_required
@mobile_permission_required('crear_aviso')
def mobile_crear_aviso(request, pk=None):
    if pk:
        instance = get_object_or_404(Aviso, pk=pk)
        activo = instance.activo
    else:
        instance = None
        aid = request.GET.get('activo')
        if request.method == 'POST' and not aid:
            aid = request.POST.get('activo')
            
        try:
            if aid:
                aid_clean = str(aid).replace(',', '').replace('.', '')
                activo = Activo.objects.filter(id=aid_clean).first()
            else:
                activo = None
        except ValueError:
            activo = None
    
    # Obtener ubicación por defecto (del GET o del perfil)
    uid = request.GET.get('ubicacion')
    ubi_defecto = None
    if uid:
        try:
            uid_clean = str(uid).replace(',', '').replace('.', '')
            ubi_defecto = Ubicacion.objects.filter(id=uid_clean).first()
        except Exception: pass
    
    if not ubi_defecto:
        perfil = getattr(request.user, 'perfil', None)
        ubi_defecto = perfil.ubicacion_defecto if perfil else None
    
    # Obtener catálogo de fallas relevante al puesto del usuario
    # Incluye fallas del puesto + fallas universales (sin puesto asignado)
    try:
        puesto_tecnico = request.user.perfil_tecnico
    except Exception:
        puesto_tecnico = None

    if puesto_tecnico:
        # Fallas asignadas al puesto del usuario (con sus hijos)
        # En lugar de un solo árbol genérico, mostramos todos los árboles (raíces) que el puesto de este usuario tiene asignados
        roots = Falla.objects.filter(puestos_trabajo=puesto_tecnico.puesto)
        fallas_ids = []
        
        def get_ids(node):
            fallas_ids.append(node.id)
            for h in node.hijos.all(): 
                get_ids(h)

        for r in roots:
            get_ids(r)

        # También incluir fallas universales (sin puesto, sin padre = roots genéricas)
        universales = Falla.objects.filter(puestos_trabajo__isnull=True, padre__isnull=True)
        for u in universales:
            get_ids(u)
            
        fallas = Falla.objects.filter(id__in=fallas_ids)
    else:
        fallas = Falla.objects.all()

    # Format fallas for JS filtering
    import json
    fallas_data = []
    for f in fallas:
        fallas_data.append({
            'id': f.id,
            'nombre': f.get_ruta_completa(),
            'tipo_aviso': f.tipo_aviso or ''
        })
    fallas_json = json.dumps(fallas_data, ensure_ascii=False)

    tipos = [(v, l, v == 'SOLICITUD') for v, l in Aviso.TIPO_CHOICES]
    prioridades = [(v, l, v == 'MEDIA') for v, l in Aviso.PRIORIDAD_CHOICES]
    ubicaciones = Ubicacion.objects.all().order_by('nombre')

    context = {
        'activo': activo,
        'ubi_defecto': ubi_defecto,
        'ubicaciones': ubicaciones,
        'fallas_json': fallas_json,
        'prioridades': prioridades,
        'tipos': tipos,
    }

    if request.method == 'POST':
        ubi_id = request.POST.get('ubicacion')
        ubicacion = Ubicacion.objects.filter(id=ubi_id).first() if ubi_id else None
        
        if not ubicacion:
            ubicacion = activo.ubicacion if activo else ubi_defecto
        
        if not ubicacion:
            # Recargar contexto para el error
            tipos = [(v, l, v == request.POST.get('tipo', 'SOLICITUD')) for v, l in Aviso.TIPO_CHOICES]
            prioridades = [(v, l, v == request.POST.get('prioridad', 'MEDIA')) for v, l in Aviso.PRIORIDAD_CHOICES]
            ubicaciones = Ubicacion.objects.all().order_by('nombre')
            return render(request, 'mantenimiento/mobile_crear_aviso.html', {
                'aviso': instance,
                'activo': activo, 
                'prioridades': prioridades, 
                'tipos': tipos,
                'fallas_json': fallas_json,
                'ubicaciones': ubicaciones,
                'error_mensaje': 'Debe seleccionar una ubicación para el reporte.'
            })

        data = {
            'activo': activo,
            'ubicacion': ubicacion,
            'falla_id': request.POST.get('falla'),
            'descripcion': request.POST.get('descripcion'),
            'prioridad': request.POST.get('prioridad', 'MEDIA'),
            'tipo': request.POST.get('tipo', 'SOLICITUD'),
        }
        
        # Estado solo si estamos editando o si se envía explícitamente
        estado_post = request.POST.get('estado')
        if estado_post:
            data['estado'] = estado_post
        elif not instance:
            data['estado'] = 'ABIERTO'

        # Procesar fechas si vienen en el POST
        fecha_reporte = request.POST.get('creado_en')
        if fecha_reporte:
            try:
                data['creado_en'] = timezone.make_aware(datetime.fromisoformat(fecha_reporte))
            except Exception: pass
            
        fecha_cierre = request.POST.get('fecha_cierre')
        if fecha_cierre:
            try:
                data['fecha_cierre'] = timezone.make_aware(datetime.fromisoformat(fecha_cierre))
            except Exception: 
                data['fecha_cierre'] = None
        elif instance:
            # Si estamos editando y no viene fecha_cierre, podría significar que se limpió o que no se mostró
            # Pero en este caso, si no viene en el POST, lo dejamos como estaba o lo limpiamos?
            # SAP PM: Si el estado cambia a CERRADO, se debería poner la fecha.
            pass

        if instance:
            for k, v in data.items(): setattr(instance, k, v)
            instance.save()
            aviso = instance
        else:
            data['solicitante'] = request.user
            aviso = Aviso.objects.create(**data)
        
        fotos = request.FILES.getlist('fotos')
        descripciones = request.POST.getlist('descripciones[]')
        
        if fotos:
            if not aviso.foto:
                aviso.foto = fotos[0]
                aviso.save()
            for i, f in enumerate(fotos):
                desc = descripciones[i] if i < len(descripciones) else ''
                FotoAviso.objects.create(aviso=aviso, foto=f, descripcion=desc)
        
        if activo: return redirect('activos:mobile_activo_detalle', pk=activo.id)
        return redirect('mantenimiento:mobile_aviso_detalle', pk=aviso.id)
    
    tipos = [(v, l, v == (instance.tipo if instance else 'SOLICITUD')) for v, l in Aviso.TIPO_CHOICES]
    prioridades = [(v, l, v == (instance.prioridad if instance else 'MEDIA')) for v, l in Aviso.PRIORIDAD_CHOICES]
    ubicaciones = Ubicacion.objects.all().order_by('nombre')
    
    return render(request, 'mantenimiento/mobile_crear_aviso.html', {
        'aviso': instance,
        'activo': activo, 
        'prioridades': prioridades, 
        'tipos': tipos,
        'ubi_defecto': ubi_defecto,
        'fallas_json': fallas_json,
        'ubicaciones': ubicaciones,
        'estados': Aviso.ESTADO_CHOICES
    })

@staff_member_required
@mobile_permission_required('crear_aviso')
def mobile_aviso_editar(request, pk):
    return mobile_crear_aviso(request, pk=pk)

@staff_member_required
@mobile_permission_required('tareas_hoy')
def mobile_ot_iniciar(request, pk):
    ot = get_object_or_404(OrdenTrabajo, pk=pk)
    if ot.estado in ['PROGRAMADA', 'ESPERA']:
        ot.estado = 'EJECUCION'
        ot.fecha_ejecucion = timezone.now()
        ot.save()
    return redirect('mantenimiento:mobile_ot_finalizar', pk=ot.id)

@staff_member_required
@mobile_permission_required('tareas_hoy')
def mobile_ot_finalizar(request, pk):
    ot = get_object_or_404(OrdenTrabajo, pk=pk)
    
    # Obtener el procedimiento y sus pasos
    pasos = []
    if ot.rutina:
        pasos = ot.rutina.pasos.all().order_by('orden')
    
    # Vincular cada paso de tipo MEDICION con un punto real del activo de la OT
    # NOTA: En este sistema, la OT puede tener múltiples activos, pero para el checklist 
    # tomaremos el primero como referencia principal si hay vinculación por código.
    activo_principal = ot.activos.first()
    
    for paso in pasos:
        if paso.tipo_respuesta == 'MEDICION':
            punto = None
            if paso.punto_medicion_exacto:
                punto = paso.punto_medicion_exacto
            elif paso.punto_medicion_codigo and activo_principal:
                punto = activo_principal.puntos_medicion.filter(codigo=paso.punto_medicion_codigo).first()
            
            paso.punto_vinculado = punto # Helper para el template

    # Obtener puntos de medición de los activos vinculados (los que NO están en el checklist)
    activos = ot.activos.all().prefetch_related('puntos_medicion')
    puntos_medicion_extra = []
    checklist_puntos_ids = [p.punto_vinculado.id for p in pasos if getattr(p, 'punto_vinculado', None)]
    
    for a in activos:
        for p in a.puntos_medicion.all():
            if p.id not in checklist_puntos_ids:
                p.activo_nombre = a.nombre
                puntos_medicion_extra.append(p)
            
    if request.method == 'POST':
        # 1. Guardar resultados del checklist
        for paso in pasos:
            valor_text = request.POST.get(f'paso_{paso.id}_text')
            valor_num = request.POST.get(f'paso_{paso.id}_num')
            valor_bool = request.POST.get(f'paso_{paso.id}_bool') == 'on'
            no_aplica = request.POST.get(f'paso_{paso.id}_na') == 'on'
            comentarios = request.POST.get(f'paso_{paso.id}_com')
            
            # Guardar fotos si es un paso tipo FOTO
            if paso.tipo_respuesta == 'FOTO':
                fotos_paso = request.FILES.getlist(f'paso_{paso.id}_fotos')
                for foto in fotos_paso:
                    ArchivoOrdenTrabajo.objects.create(
                        orden_trabajo=ot,
                        paso=paso,
                        archivo=foto,
                        subido_por=request.user,
                        tipo='IMAGEN'
                    )
                # Para FOTO iteramos para marcar el paso como capturado (crea ValorPasoOrden vacío si hay fotos para saber que no fue omitido)
                if fotos_paso:
                    valor_text = f"{len(fotos_paso)} foto(s) adjuntada(s)"

            if valor_text or valor_num or valor_bool or no_aplica or paso.tipo_respuesta == 'MEDICION' or paso.tipo_respuesta == 'FOTO':
                ValorPasoOrden.objects.update_or_create(
                    orden_trabajo=ot,
                    paso=paso,
                    defaults={
                        'valor_texto': valor_text,
                        'valor_numerico': float(valor_num) if valor_num else None,
                        'valor_bool': valor_bool,
                        'no_aplica': no_aplica,
                        'comentarios': comentarios,
                        'capturado_por': request.user
                    }
                )
                
                # Si es MEDICION, crear DocumentoMedicion
                if paso.tipo_respuesta == 'MEDICION' and valor_num and not no_aplica:
                    punto = getattr(paso, 'punto_vinculado', None)
                    if punto:
                        DocumentoMedicion.objects.create(
                            punto=punto,
                            valor=float(valor_num),
                            tecnico=request.user,
                            orden_trabajo=ot,
                            observaciones=f"Capturado vía checklist OT #{ot.id}"
                        )
        
        # 2. Guardar lecturas de puntos de medición extra
        for punto in puntos_medicion_extra:
            valor_lectura = request.POST.get(f'punto_{punto.id}')
            if valor_lectura:
                DocumentoMedicion.objects.create(
                    punto=punto,
                    valor=float(valor_lectura),
                    tecnico=request.user,
                    orden_trabajo=ot,
                    observaciones=f"Capturado durante cierre de OT #{ot.id}"
                )
        
        # 3. Guardar fotos de cierre
        fotos_cierre = request.FILES.getlist('fotos_cierre')
        for foto in fotos_cierre:
            archivo = ArchivoOrdenTrabajo(
                orden_trabajo=ot,
                archivo=foto,
                subido_por=request.user
            )
            archivo.save()
        
        # 4. Actualizar estado según la acción
        accion = request.POST.get('action')
        comentarios_cierre = request.POST.get('comentarios_cierre', '').strip()
        
        is_gerente = request.user.groups.filter(name='Gerentes').exists() or request.user.is_superuser
        
        if ot.estado == 'REALIZADA' and not is_gerente:
             return JsonResponse({'status': 'error', 'message': 'No tienes permiso para editar un reporte finalizado'}, status=403)

        if comentarios_cierre:
            # Si ya hay notas, concatenamos de forma limpia
            nueva_nota = f"\n[Edición {timezone.now().strftime('%d/%m %H:%M')}] {comentarios_cierre}"
            if ot.estado != 'REALIZADA': # Si es el primer cierre
                nueva_nota = f"\n[Cierre] {comentarios_cierre}"
            
            ot.notas = (ot.notas or '') + nueva_nota
            ot.save(update_fields=['notas'])
        
        if accion == 'finalize' or (ot.estado == 'REALIZADA' and is_gerente):
            if ot.estado != 'REALIZADA':
                ot.estado = 'REALIZADA'
                ot.fecha_termino = timezone.now()
            
            ot.save()
            
            # Disparar generación de PDF en segundo plano (para actualizar el PDF con los nuevos datos)
            try:
                task_generar_ot_pdf.delay(ot.id)
            except Exception as e:
                print(f"Error al encolar tarea de PDF: {e}")
                
            return redirect('mantenimiento:mobile_ot_detalle', pk=ot.id)
        
        # Por defecto solo guardamos y nos quedamos en la misma pantalla (o volvemos al detalle)
        return redirect('mantenimiento:mobile_ot_detalle', pk=ot.id)

    # Obtener resultados y fotos existentes para pre-cargar si estamos re-editando
    resultados_qs = ot.resultados_checklist.all()
    resultados_dict = {res.paso_id: res for res in resultados_qs}
    
    archivos_pasos = ot.archivos.filter(paso__isnull=False)
    import collections
    archivos_dict = collections.defaultdict(list)
    for a in archivos_pasos:
        archivos_dict[a.paso_id].append(a)
    
    # Decorar los pasos con su resultado y fotos previas
    for paso in pasos:
        paso.resultado = resultados_dict.get(paso.id)
        paso.fotos_guardadas = archivos_dict.get(paso.id, [])

    return render(request, 'mantenimiento/mobile_ot_finalizar.html', {
        'ot': ot,
        'pasos': pasos,
        'puntos_medicion': puntos_medicion_extra,
    })

@staff_member_required
def mobile_crear_ot_rutina(request, rutina_id):
    """
    Crea una OT inmediata basada en una rutina y ubicación específica.
    Usado desde el Visor de Planos (Modo App).
    """
    from ..models import Rutina
    rutina = get_object_or_404(Rutina, pk=rutina_id)
    ubicacion_id = request.GET.get('ubicacion_id')
    ubicacion = get_object_or_404(Ubicacion, pk=ubicacion_id) if ubicacion_id else None
    
    now = timezone.now()
    duracion = rutina.tiempo_estimado or timedelta(hours=1)
    
    ot = OrdenTrabajo.objects.create(
        rutina=rutina,
        ubicacion=ubicacion,
        tecnico=request.user,
        estado='PROGRAMADA',
        inicio_programado=now,
        fin_programado=now + duracion,
        notas=f"Generada desde Visor: {rutina.nombre}"
    )
    
    # Intento de vincular activos de esa ubicación que coincidan con la categoría
    if ubicacion and rutina.tipo:
        # Buscar activos en esta ubicación que sean de la categoría de la rutina
        cat_activo = rutina.tipo.categoria_activo
        if cat_activo:
            activos_candidatos = Activo.objects.filter(ubicacion=ubicacion, modelo__categoria=cat_activo)
            for a in activos_candidatos:
                ot.activos.add(a)
    
    return redirect('mantenimiento:mobile_ot_detalle', pk=ot.id)

@staff_member_required
@mobile_permission_required('tareas_hoy')
def mobile_mis_ordenes(request):
    """
    Muestra las órdenes de trabajo abiertas del usuario (por técnico o equipo).
    """
    user_q = Q(tecnico=request.user) | Q(equipo__in=request.user.groups.all())
    
    ordenes = OrdenTrabajo.objects.filter(user_q).exclude(
        estado__in=['REALIZADA', 'CANCELADA']
    ).select_related(
        'rutina', 'ubicacion', 'tecnico', 'aviso'
    ).prefetch_related('activos').distinct().order_by('-estado', 'inicio_programado')
    
    return render(request, 'mantenimiento/mobile_mis_ordenes.html', {
        'ordenes': ordenes,
    })

@staff_member_required
@mobile_permission_required('mis_avisos')
def mobile_mis_avisos(request):
    """
    Muestra los avisos del usuario y de sus compañeros de puesto.
    """
    # 1. Filtro base: Mis avisos
    query = Q(solicitante=request.user)
    
    # 2. Extensión: Avisos de compañeros del mismo puesto
    puesto_tecnico = getattr(request.user, 'perfil_tecnico', None)
    if puesto_tecnico:
        puesto = puesto_tecnico.puesto
        query |= Q(solicitante__perfil_tecnico__puesto=puesto)
    
    avisos = Aviso.objects.filter(query).select_related('activo', 'ubicacion', 'falla', 'solicitante').order_by('-creado_en')
    
    return render(request, 'mantenimiento/mobile_mis_avisos.html', {
        'avisos': avisos,
        'puesto': puesto_tecnico.puesto if puesto_tecnico else None
    })

@staff_member_required
@mobile_permission_required('mis_avisos')
def mobile_aviso_detalle(request, pk):
    """
    Muestra el detalle expandido de un aviso con sus fotos.
    """
    aviso = get_object_or_404(Aviso.objects.select_related(
        'falla', 'activo__modelo__marca', 'activo__ubicacion', 'ubicacion', 'solicitante'
    ), pk=pk)
    # Verificar acceso (mismo puesto o solicitante)
    # Por ahora permitimos visualización si es del mismo puesto o solicitante
    puesto_tecnico = getattr(request.user, 'perfil_tecnico', None)
    puede_ver = aviso.solicitante == request.user or (puesto_tecnico and getattr(aviso.solicitante, 'perfil_tecnico', None) and aviso.solicitante.perfil_tecnico.puesto == puesto_tecnico.puesto)
    
    if not puede_ver and not request.user.is_superuser:
        return redirect('mantenimiento:mobile_mis_avisos')

    return render(request, 'mantenimiento/mobile_aviso_detalle.html', {
        'aviso': aviso,
    })

@staff_member_required
def mobile_ot_upload_file(request, pk):
    """AJAX endpoint para subir archivos a una Orden de Trabajo."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
    
    ot = get_object_or_404(OrdenTrabajo, pk=pk)
    files = request.FILES.getlist('archivos')
    
    if not files:
        return JsonResponse({'status': 'error', 'message': 'No se recibieron archivos'}, status=400)
    
    created = []
    for f in files:
        archivo = ArchivoOrdenTrabajo(
            orden_trabajo=ot,
            archivo=f,
            subido_por=request.user
        )
        archivo.save()
        created.append({
            'id': archivo.id,
            'nombre': archivo.nombre,
            'tipo': archivo.tipo,
            'url': archivo.archivo.url,
            'creado_en': archivo.creado_en.strftime('%d/%m/%Y %H:%M'),
        })
    
    return JsonResponse({'status': 'success', 'archivos': created, 'message': f'{len(created)} archivo(s) subido(s)'})


@staff_member_required
def mobile_ot_delete_file(request, pk, archivo_id):
    """AJAX endpoint para eliminar un archivo de una OT."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
    
    archivo = get_object_or_404(ArchivoOrdenTrabajo, pk=archivo_id, orden_trabajo_id=pk)
    
    # Solo el que subió o un superusuario puede borrar
    if archivo.subido_por != request.user and not request.user.is_superuser:
        return JsonResponse({'status': 'error', 'message': 'No tienes permiso para eliminar este archivo'}, status=403)
    
    try:
        archivo.archivo.delete(save=False)  # Borrar del storage (MinIO/local)
        archivo.delete()
        return JsonResponse({'status': 'success', 'message': 'Archivo eliminado'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@staff_member_required
def mobile_crear_medicion(request, pk):
    """
    Renderiza interfaz SAP Fiori para registrar lectura de Punto de Medición
    y procesa el almacenamiento vía POST.
    """
    punto = get_object_or_404(PuntoMedicion, pk=pk)
    
    if request.method == 'POST':
        try:
            from django.http import JsonResponse
            valor = float(request.POST.get('valor', 0))
            obs = request.POST.get('observaciones', '')
            
            DocumentoMedicion.objects.create(
                punto=punto,
                activo=punto.activo,
                valor=valor,
                observaciones=obs,
                tecnico=request.user
            )
            return JsonResponse({'status': 'success'})
        except Exception as e:
            from django.http import JsonResponse
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
            
    return render(request, 'mantenimiento/mobile_crear_medicion.html', {'punto': punto})

@staff_member_required
def check_ot_pdf_status(request, pk):
    """
    Endpoint AJAX para verificar si el reporte PDF de una OT ya está disponible.
    """
    ot = get_object_or_404(OrdenTrabajo, pk=pk)
    filename = f"OT_{ot.id}.pdf"
    
    # Buscar en los archivos adjuntos
    archivo = ArchivoOrdenTrabajo.objects.filter(orden_trabajo=ot, nombre=filename).first()
    
    if archivo:
        return JsonResponse({
            'ready': True,
            'url': archivo.archivo.url,
            'nombre': archivo.nombre,
            'id': archivo.id
        })
    else:
        return JsonResponse({'ready': False})
