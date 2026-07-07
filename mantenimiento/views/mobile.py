import collections
from datetime import datetime, timedelta
import collections
from datetime import datetime, timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib.auth.models import User, Group
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from django.db.models import Count, Q, Min
from django.conf import settings
from core.decorators import mobile_permission_required
from ..models import Programacion, OrdenTrabajo, Aviso, ValorPasoOrden, PasoRutina, Falla, FotoAviso, ArchivoOrdenTrabajo, Empresa, Rutina, TecnicoPuesto
from activos.models import Activo, Ubicacion, DocumentoMedicion, PuntoMedicion
from core.models import Departamento
from ..tasks import task_generar_ot_pdf
from webpush import send_user_notification

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
    ot = get_object_or_404(OrdenTrabajo.objects.select_related('rutina', 'ubicacion', 'tecnico', 'tecnico_puesto', 'supervisor', 'aviso', 'programacion').prefetch_related('activos', 'archivos', 'colaboradores_puesto'), pk=pk)
    
    # Listas para asignación
    supervisores = User.objects.filter(
        Q(is_staff=True) |
        Q(groups__name='Supervisor') | 
        Q(perfil_tecnico__puesto__nombre__icontains='Supervisor')
    ).distinct().order_by('first_name')
    
    personales = TecnicoPuesto.objects.select_related('user', 'puesto', 'empresa').filter(esta_vigente=True).order_by('nombre')
    empresas = Empresa.objects.filter(activo=True).order_by('nombre')
    
    is_gerente = request.user.groups.filter(name='Gerentes').exists() or request.user.is_superuser
    
    ubicaciones = None
    if not ot.ubicacion:
        ubicaciones = Ubicacion.objects.filter(padre__isnull=True).order_by('nombre')
    
    context = {
        'ot': ot,
        'supervisores': supervisores,
        'personales': personales,
        'empresas': empresas,
        'is_gerente': is_gerente,
        'ubicaciones': ubicaciones,
        'resultados': ot.resultados_checklist.select_related('paso').order_by('paso__orden'),
        'colaboradores_ids': list(ot.colaboradores_puesto.values_list('id', flat=True)),
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

    tecnico_id = request.POST.get('tecnico') # ID de TecnicoPuesto (Líder)
    tecnicos_ids = request.POST.getlist('tecnicos') # IDs de TecnicoPuesto (Colaboradores)
    supervisor_id = request.POST.get('supervisor')
    empresa_id = request.POST.get('empresa_responsable')
    fecha_str = request.POST.get('inicio_programado')
    fecha_fin_str = request.POST.get('fin_programado')
    ubicacion_id = request.POST.get('ubicacion')
    descripcion = request.POST.get('descripcion_detallada')
    
    try:
        if tecnico_id:
            if tecnico_id == 'none':
                ot.tecnico_puesto = None
                ot.tecnico = None
            else:
                tp = TecnicoPuesto.objects.filter(pk=tecnico_id).first()
                if tp:
                    ot.tecnico_puesto = tp
                    ot.tecnico = tp.user
        
        if tecnicos_ids:
            # Sincronizar Colaboradores (Personal)
            valid_ids = [tid for tid in tecnicos_ids if tid != 'none']
            ot.colaboradores_puesto.set(valid_ids)
            
            # Sincronizar Usuarios (para acceso al sistema de los que tengan cuenta)
            personales_equipo = TecnicoPuesto.objects.filter(id__in=valid_ids).exclude(user__isnull=True)
            user_ids = [p.user_id for p in personales_equipo]
            ot.tecnicos.set(user_ids)

        if supervisor_id:
            ot.supervisor = User.objects.get(pk=supervisor_id) if supervisor_id != 'none' else None
            
        if empresa_id:
            ot.empresa_responsable = Empresa.objects.get(pk=empresa_id) if empresa_id != 'none' else None

        if ubicacion_id:
            ot.ubicacion = Ubicacion.objects.get(pk=ubicacion_id) if ubicacion_id != 'none' else None
            
        if descripcion is not None:
            ot.descripcion_detallada = descripcion
            ot.descripcion_corta = descripcion[:200]
            
        if fecha_str:
            new_date = datetime.fromisoformat(fecha_str)
            if timezone.is_naive(new_date):
                new_date = timezone.make_aware(new_date)
            ot.inicio_programado = new_date

        if fecha_fin_str:
            new_end_date = datetime.fromisoformat(fecha_fin_str)
            if timezone.is_naive(new_end_date):
                new_end_date = timezone.make_aware(new_end_date)
            ot.fin_programado = new_end_date
            
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

    # Listas para asignación
    departamentos = Departamento.objects.all().order_by('nombre')
    # Técnicos y personal staff para responsables
    responsables = User.objects.filter(
        Q(is_staff=True) | 
        Q(groups__name='Tecnicos') | 
        Q(perfil_tecnico__isnull=False)
    ).select_related('perfil').distinct().order_by('first_name')

    context = {
        'activo': activo,
        'ubi_defecto': ubi_defecto,
        'ubicaciones': ubicaciones,
        'fallas_json': fallas_json,
        'prioridades': prioridades,
        'tipos': tipos,
        'departamentos': departamentos,
        'responsables': responsables,
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
            'descripcion': request.POST.get('descripcion') or request.POST.get('description') or '',
            'prioridad': request.POST.get('prioridad', 'MEDIA'),
            'tipo': request.POST.get('tipo', 'SOLICITUD'),
            'responsable_id': request.POST.get('responsable') if request.POST.get('responsable') and request.POST.get('responsable') != 'none' else None,
            'departamento_id': request.POST.get('departamento') if request.POST.get('departamento') and request.POST.get('departamento') != 'none' else None,
            'equipo_parado': request.POST.get('equipo_parado') == 'on',
        }

        if not data['descripcion'].strip():
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
                'error_mensaje': 'La descripción del aviso es obligatoria.'
            })
        
        # Estado solo si estamos editando o si se envía explícitamente
        estado_post = request.POST.get('estado')
        if estado_post:
            data['estado'] = estado_post
        elif not instance:
            data['estado'] = 'ABIERTO'

        # Si el estado cambia a CERRADO, asignar fecha_cierre y cerrado_por
        if data.get('estado') == 'CERRADO':
            if not data.get('fecha_cierre'):
                data['fecha_cierre'] = timezone.now()
            # Si estamos creando, no puede ser CERRADO
            if not instance:
                data['fecha_cierre'] = None

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

        # Campos de cierre: diagnóstico y acciones
        diagnostico = request.POST.get('diagnostico', '').strip()
        if diagnostico:
            data['diagnostico'] = diagnostico
        acciones = request.POST.get('acciones', '').strip()
        if acciones:
            data['acciones'] = acciones

        if instance:
            # Si cambia a CERRADO, registrar quién cerró
            if data.get('estado') == 'CERRADO' and instance.estado != 'CERRADO':
                data['cerrado_por'] = request.user
            for k, v in data.items(): setattr(instance, k, v)
            instance.save()
            aviso = instance
        else:
            data['solicitante'] = request.user
            aviso = Aviso.objects.create(**data)
        
        fotos = request.FILES.getlist('fotos')
        descripciones = request.POST.getlist('descripciones[]')
        foto_tipo = request.POST.get('foto_tipo', 'APERTURA')
        
        if fotos:
            if not aviso.foto:
                aviso.foto = fotos[0]
                aviso.save()
            for i, f in enumerate(fotos):
                desc = descripciones[i] if i < len(descripciones) else ''
                FotoAviso.objects.create(aviso=aviso, foto=f, descripcion=desc, tipo=foto_tipo)
        
        if activo: return redirect('activos:mobile_activo_detalle', pk=activo.id)
        return redirect('mantenimiento:mobile_aviso_detalle', pk=aviso.id)
    
    tipos = [(v, l, v == (instance.tipo if instance else 'SOLICITUD')) for v, l in Aviso.TIPO_CHOICES]
    prioridades = [(v, l, v == (instance.prioridad if instance else 'MEDIA')) for v, l in Aviso.PRIORIDAD_CHOICES]
    ubicaciones = Ubicacion.objects.all().order_by('nombre')
    departamentos = Departamento.objects.all().order_by('nombre')
    responsables = User.objects.filter(
        Q(is_staff=True) | 
        Q(groups__name='Tecnicos') | 
        Q(perfil_tecnico__isnull=False)
    ).select_related('perfil').distinct().order_by('first_name')
    
    return render(request, 'mantenimiento/mobile_crear_aviso.html', {
        'aviso': instance,
        'activo': activo, 
        'prioridades': prioridades, 
        'tipos': tipos,
        'ubi_defecto': ubi_defecto,
        'fallas_json': fallas_json,
        'ubicaciones': ubicaciones,
        'estados': Aviso.ESTADO_CHOICES,
        'departamentos': departamentos,
        'responsables': responsables,
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
        pasos = ot.rutina.pasos.prefetch_related('media_files').all().order_by('orden')
    
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
        
        # 3. Guardar fotos de inicio
        fotos_inicio = request.FILES.getlist('fotos_inicio')
        for foto in fotos_inicio:
            ArchivoOrdenTrabajo.objects.create(
                orden_trabajo=ot,
                archivo=foto,
                subido_por=request.user,
                momento='INICIO'
            )

        # 4. Guardar fotos de cierre
        fotos_cierre = request.FILES.getlist('fotos_cierre')
        for foto in fotos_cierre:
            ArchivoOrdenTrabajo.objects.create(
                orden_trabajo=ot,
                archivo=foto,
                subido_por=request.user,
                momento='CIERRE'
            )
        
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
                
                # Capturar fecha de cierre manual si existe
                fecha_cierre_str = request.POST.get('fecha_cierre')
                if fecha_cierre_str:
                    try:
                        ot.fecha_ejecucion = timezone.make_aware(datetime.fromisoformat(fecha_cierre_str))
                    except:
                        ot.fecha_ejecucion = timezone.now()
                else:
                    ot.fecha_ejecucion = timezone.now()
            
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
@login_required
def mobile_crear_ot_rutina(request, rutina_id):
    """
    Crea una OT inmediata basada en una rutina.
    Si la rutina tiene categoría asociada, permite seleccionar activos.
    """
    from ..models import Rutina
    rutina = get_object_or_404(Rutina, pk=rutina_id)
    
    # Determinar categoría asociada
    categoria = rutina.categoria_activo or (rutina.tipo.categoria_activo if rutina.tipo else None)
    
    if request.method == 'GET':
        # Si tiene categoría y no se especificó ubicación NI activos aún, ir a selección
        # EXCEPCIÓN: Si viene 'confirm=1' en la URL, saltamos la selección (para compatibilidad o rapidez)
        if categoria and not request.GET.get('ubicacion_id') and not request.GET.get('confirm'):
            from activos.models import Ubicacion
            ubicaciones = Ubicacion.objects.filter(padre__isnull=True).order_by('orden', 'nombre')
            return render(request, 'mantenimiento/mobile_seleccionar_activos_rutina.html', {
                'rutina': rutina,
                'categoria': categoria,
                'ubicaciones': ubicaciones,
            })
            
        # Comportamiento original o automático:
        ubicacion_id = request.GET.get('ubicacion_id')
        ubicacion = Ubicacion.objects.filter(pk=ubicacion_id).first() if ubicacion_id else None
        
        now = timezone.now()
        duracion = rutina.tiempo_estimado or timedelta(hours=1)
        
        ot = OrdenTrabajo.objects.create(
            rutina=rutina,
            ubicacion=ubicacion,
            tecnico=request.user,
            estado='PROGRAMADA',
            inicio_programado=now,
            fin_programado=now + duracion,
            notas=f"Generada via QR/App: {rutina.nombre}"
        )
        
        # Vincular automáticamente si hay ubicación y categoría
        if ubicacion and categoria:
             activos_candidatos = Activo.objects.filter(ubicacion=ubicacion, modelo__categoria=categoria)
             for a in activos_candidatos:
                 ot.activos.add(a)
        
        return redirect('mantenimiento:mobile_ot_detalle', pk=ot.id)

    elif request.method == 'POST':
        # Creación personalizada desde el template de selección
        ubicacion_id = request.POST.get('ubicacion')
        activos_ids = request.POST.getlist('activos')
        
        from activos.models import Ubicacion
        ubicacion = Ubicacion.objects.filter(pk=ubicacion_id).first() if ubicacion_id else None
        
        now = timezone.now()
        duracion = rutina.tiempo_estimado or timedelta(hours=1)
        
        ot = OrdenTrabajo.objects.create(
            rutina=rutina,
            ubicacion=ubicacion,
            tecnico=request.user,
            estado='PROGRAMADA',
            inicio_programado=now,
            fin_programado=now + duracion,
            notas=f"Generada via QR (Selección): {rutina.nombre}"
        )
        
        if activos_ids:
            activos = Activo.objects.filter(id__in=activos_ids)
            for a in activos:
                ot.activos.add(a)
        
        return JsonResponse({
            'status': 'success', 
            'ot_id': ot.id, 
            'message': 'Orden de trabajo creada con éxito.'
        })

@staff_member_required
@mobile_permission_required('tareas_hoy')
def mobile_mis_ordenes(request):
    """
    Muestra las órdenes de trabajo abiertas del usuario (por técnico o equipo)
    con soporte para búsqueda y filtrado.
    """
    user_q = Q(tecnico=request.user) | Q(equipo__in=request.user.groups.all())
    
    # Búsqueda
    search_query = request.GET.get('q', '')
    
    # Filtros
    estado_filter = request.GET.get('estado', '')
    prioridad_filter = request.GET.get('prioridad', '')
    
    ordenes = OrdenTrabajo.objects.filter(user_q).exclude(
        estado__in=['CANCELADA'] # Permitir ver Realizadas si se filtra? No, el usuario pidió "Abiertas" generalmente.
    )

    # Si no hay filtros de estado específicos, excluir REALIZADA
    if not estado_filter:
        ordenes = ordenes.exclude(estado='REALIZADA')

    if search_query:
        ordenes = ordenes.filter(
            Q(id__icontains=search_query) |
            Q(codigo_de_orden__icontains=search_query) |
            Q(rutina__nombre__icontains=search_query) |
            Q(aviso__descripcion__icontains=search_query) |
            Q(ubicacion__nombre__icontains=search_query)
        )
    
    if estado_filter:
        ordenes = ordenes.filter(estado=estado_filter)
    
    if prioridad_filter:
        ordenes = ordenes.filter(prioridad=prioridad_filter)

    ordenes = ordenes.select_related(
        'rutina', 'ubicacion', 'tecnico', 'aviso'
    ).prefetch_related('activos').distinct().order_by('-estado', 'inicio_programado')
    
    # Limitar para rendimiento móvil si no hay búsqueda
    if not search_query and not estado_filter:
        ordenes = ordenes[:50]

    return render(request, 'mantenimiento/mobile_mis_ordenes.html', {
        'ordenes': ordenes,
        'q': search_query,
        'estado_filter': estado_filter,
        'prioridad_filter': prioridad_filter,
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
    
    avisos = Aviso.objects.filter(query).select_related('activo', 'ubicacion', 'falla', 'solicitante').prefetch_related('fotos').order_by('-creado_en')
    
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
def aviso_fiori_view(request, pk):
    """Vista Fiori para el detalle de Aviso (usada en modal desde el dashboard)."""
    aviso = get_object_or_404(Aviso.objects.select_related(
        'falla', 'activo__modelo__marca', 'activo__ubicacion', 'ubicacion', 'solicitante',
        'responsable', 'departamento', 'proyecto'
    ).prefetch_related('ordenes'), pk=pk)
    ot_existente = aviso.ordenes.first()
    return render(request, 'mantenimiento/mobile_aviso_detalle.html', {
        'aviso': aviso,
        'iframe_mode': True,
        'ot_existente': ot_existente,
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
def mobile_crear_otnp(request):
    """
    Crea una Orden de Trabajo No Programada (OTNP) desde la app móvil.
    """
    if request.method == 'POST':
        try:
            ubi_id = request.POST.get('ubicacion')
            prio = request.POST.get('prioridad', 'MEDIA')
            desc = request.POST.get('descripcion', '').strip()
            tecnico_id = request.POST.get('tecnico') # ID de TecnicoPuesto (Personal)
            tecnicos_ids = request.POST.getlist('tecnicos') # IDs de TecnicoPuesto (Colaboradores)
            empresa_id = request.POST.get('empresa_responsable')
            activo_id = request.POST.get('activo')
            inicio_str = request.POST.get('inicio_programado')
            fin_str = request.POST.get('fin_programado')
            
            ubicacion = get_object_or_404(Ubicacion, pk=ubi_id) if ubi_id else None
            tecnico_puesto = TecnicoPuesto.objects.filter(pk=tecnico_id).first() if tecnico_id and tecnico_id != 'none' else None
            empresa = Empresa.objects.filter(pk=empresa_id).first() if empresa_id and empresa_id != 'none' else None
            activo = Activo.objects.filter(pk=activo_id).first() if activo_id else None
            
            # Determinar técnico líder (User) a partir del puesto si existe
            tecnico_user = tecnico_puesto.user if tecnico_puesto and tecnico_puesto.user else None
            if not tecnico_user and not tecnico_puesto:
                tecnico_user = request.user

            now = timezone.now()
            
            # Procesar fechas si vienen
            inicio_dt = now
            if inicio_str:
                try:
                    inicio_dt = timezone.make_aware(datetime.fromisoformat(inicio_str))
                except: pass
                
            fin_dt = inicio_dt + timedelta(hours=2)
            if fin_str:
                try:
                    fin_dt = timezone.make_aware(datetime.fromisoformat(fin_str))
                except: pass

            ot = OrdenTrabajo.objects.create(
                tipo='NO_PROGRAMADA',
                prioridad=prio,
                ubicacion=ubicacion,
                tecnico=tecnico_user,
                tecnico_puesto=tecnico_puesto,
                empresa_responsable=empresa,
                descripcion_corta=desc[:200],
                descripcion_detallada=desc,
                estado='PROGRAMADA',
                inicio_programado=inicio_dt,
                fin_programado=fin_dt
            )

            if activo:
                ot.activos.add(activo)

            if tecnicos_ids:
                valid_ids = [tid for tid in tecnicos_ids if tid != 'none']
                ot.colaboradores_puesto.set(valid_ids)
                # Sincronizar usuarios
                personales_equipo = TecnicoPuesto.objects.filter(id__in=valid_ids).exclude(user__isnull=True)
                ot.tecnicos.set([p.user_id for p in personales_equipo])
            
            return JsonResponse({'status': 'success', 'ot_id': ot.id, 'codigo': ot.codigo_de_orden})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    # GET: Mostrar formulario
    ubicaciones_qs = Ubicacion.objects.all()
    ubicaciones = []
    for u in ubicaciones_qs:
        u.full_path = u.get_ruta_completa()
        u.depth = u.level
        u.has_children = u.sub_ubicaciones.exists()
        ubicaciones.append(u)
    
    ubicaciones.sort(key=lambda x: x.full_path)

    prioridades = OrdenTrabajo.PRIORIDAD_CHOICES
    
    # Todos los técnicos/personal (con o sin usuario)
    personales = TecnicoPuesto.objects.select_related('user', 'puesto', 'empresa').filter(esta_vigente=True).order_by('nombre')
    empresas = Empresa.objects.filter(activo=True).order_by('nombre')
    
    return render(request, 'mantenimiento/mobile_crear_otnp.html', {
        'ubicaciones': ubicaciones,
        'prioridades': prioridades,
        'personales': personales,
        'empresas': empresas,
    })

@login_required
def mobile_crear_ot_desde_puesto(request):
    """
    Lista rutinas asociadas al puesto del usuario y permite crear una OT inmediata.
    """
    try:
        puesto_tecnico = request.user.perfil_tecnico
        puesto = puesto_tecnico.puesto
    except Exception:
        puesto = None

    # Si es superusuario o staff sin puesto, permitimos ver todas las rutinas?
    # El requerimiento dice "asociadas al puesto del usuario", pero para administradores es mejor ver todo.
    if request.user.is_superuser and not puesto:
        rutinas = Rutina.objects.all().select_related('tipo', 'frecuencia', 'puesto_trabajo')
    elif puesto:
        rutinas = Rutina.objects.filter(puesto_trabajo=puesto).select_related('tipo', 'frecuencia')
    else:
        rutinas = []

    if request.method == 'POST':
        try:
            rutina_id = request.POST.get('rutina')
            ubi_id = request.POST.get('ubicacion')
            activo_id = request.POST.get('activo')
            
            rutina = get_object_or_404(Rutina, pk=rutina_id)
            ubicacion = get_object_or_404(Ubicacion, pk=ubi_id) if ubi_id else None
            activo = Activo.objects.filter(id=activo_id).first() if activo_id else None
            
            now = timezone.now()
            duracion = rutina.tiempo_estimado or timedelta(hours=1)
            
            ot = OrdenTrabajo.objects.create(
                tipo='NO_PROGRAMADA',
                rutina=rutina,
                ubicacion=ubicacion or (activo.ubicacion if activo else None) or rutina.ubicacion_predeterminada,
                tecnico=request.user,
                estado='PROGRAMADA',
                inicio_programado=now,
                fin_programado=now + duracion,
                prioridad='MEDIA',
                descripcion_corta=f"Ejecución Manual: {rutina.nombre}",
                descripcion_detallada=f"Orden generada manualmente por el usuario basada en la rutina: {rutina.nombre}"
            )
            
            if activo:
                ot.activos.add(activo)
            elif ubicacion and rutina.tipo:
                # Intentar auto-vincular activos si la rutina tiene tipo/categoria
                cat_activo = rutina.tipo.categoria_activo
                if cat_activo:
                    activos_candidatos = Activo.objects.filter(ubicacion=ubicacion, modelo__categoria=cat_activo)
                    for a in activos_candidatos:
                        ot.activos.add(a)
            
            return JsonResponse({'status': 'success', 'ot_id': ot.id, 'codigo': ot.codigo_de_orden})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    ubicaciones = Ubicacion.objects.all().order_by('nombre')
    
    return render(request, 'mantenimiento/mobile_crear_ot_rutina.html', {
        'rutinas': rutinas,
        'ubicaciones': ubicaciones,
        'puesto': puesto
    })

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

@staff_member_required
def mobile_ot_eliminar(request, pk):
    """
    Elimina una Orden de Trabajo. SOLO PERMITIDO PARA SUPERUSER.
    """
    if not request.user.is_superuser:
        return JsonResponse({'status': 'error', 'message': 'Solo los administradores pueden eliminar órdenes.'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
    
    ot = get_object_or_404(OrdenTrabajo, pk=pk)
    ot_id = ot.id
    
    try:
        ot.delete()
        return JsonResponse({'status': 'success', 'message': f'Orden #{ot_id} eliminada correctamente.'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@staff_member_required
def mobile_ot_update_file_name(request, ot_id, file_id):
    """
    Actualiza el nombre/descripción de un archivo adjunto.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
    
    nuevo_nombre = request.POST.get('nombre', '').strip()
    if not nuevo_nombre:
        return JsonResponse({'status': 'error', 'message': 'El nombre no puede estar vacío'}, status=400)
    
    archivo = get_object_or_404(ArchivoOrdenTrabajo, pk=file_id, orden_trabajo_id=ot_id)
    archivo.nombre = nuevo_nombre
    archivo.save()
    
    return JsonResponse({'status': 'success', 'message': 'Nombre actualizado'})

@staff_member_required
def mobile_ot_webhook(request, pk):
    """
    Triggers a webhook to n8n with OT details and PDF report.
    If PDF doesn't exist, it triggers generation first.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
    
    ot = get_object_or_404(OrdenTrabajo, pk=pk)
    
    # 1. Asegurar que el PDF existe (o disparar generación)
    filename = f"OT_{ot.id}.pdf"
    archivo_pdf = ArchivoOrdenTrabajo.objects.filter(orden_trabajo=ot, nombre=filename).first()
    
    # Si no existe, lo generamos síncronamente para asegurar que el webhook lo lleve
    if not archivo_pdf:
        from ..services import WorkOrderService
        try:
            archivo_pdf = WorkOrderService.save_ot_pdf_as_attachment(ot.id)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'Error generando PDF: {str(e)}'}, status=500)

    # 2. Preparar payload para n8n
    webhook_url = getattr(settings, 'N8N_OT_WEBHOOK_URL', None)
    if not webhook_url:
        return JsonResponse({'status': 'error', 'message': 'Webhook URL no configurada en settings'}, status=500)

    # Preparar datos extendidos del técnico para el correo
    tecnico_dni = "N/A"
    tecnico_empresa = "DCC"
    if ot.tecnico and hasattr(ot.tecnico, 'perfil_tecnico'):
        tecnico_dni = ot.tecnico.perfil_tecnico.dni or "N/A"
        if ot.tecnico.perfil_tecnico.empresa:
            tecnico_empresa = ot.tecnico.perfil_tecnico.empresa.nombre

    # Preparar lista de técnicos colaboradores
    tecnicos_list = ot.tecnicos.all()
    tecnicos_nombres = ", ".join([t.get_full_name() or t.username for t in tecnicos_list])
    if not tecnicos_nombres:
        tecnicos_nombres = ot.tecnico.get_full_name() if ot.tecnico else "No asignado"

    # Empresa Responsable
    empresa_final = tecnico_empresa
    if ot.empresa_responsable:
        empresa_final = ot.empresa_responsable.nombre

    try:
        # 3. Obtener correos del departamento del usuario que dispara
        departamento_emails = ""
        if hasattr(request.user, 'perfil') and request.user.perfil.departamento:
            dept = request.user.perfil.departamento
            usuarios_dept = User.objects.filter(perfil__departamento=dept).exclude(email='').distinct()
            # Unir con punto y coma para compatibilidad con sistemas de correo (Power Automate, Outlook, etc)
            departamento_emails = ";".join(list(usuarios_dept.values_list('email', flat=True)))

        from django.utils import timezone # Reload forced at 2026-05-04 20:29
        
        # 4. Obtener Activos asociados (De la OT o del Aviso vinculado como fallback)
        activos_qs = list(ot.activos.values_list('nombre', flat=True))
        if not activos_qs and ot.aviso and ot.aviso.activo:
            activos_qs = [ot.aviso.activo.nombre]
        activos_nombres = ", ".join(activos_qs) if activos_qs else "No especificados"

        # 5. Fechas formateadas para evitar líos de zona horaria en Power Automate
        inicio_local = timezone.localtime(ot.inicio_programado)
        fin_local = timezone.localtime(ot.fin_programado)
        termino_local = timezone.localtime(ot.fecha_ejecucion) if ot.fecha_ejecucion else None

        # 6. Obtener nombre del Técnico Líder (Prioridad: Personal asignado > Usuario > No asignado)
        nombre_tecnico = "No asignado"
        if ot.tecnico_puesto:
            nombre_tecnico = ot.tecnico_puesto.nombre
        elif ot.tecnico:
            nombre_tecnico = ot.tecnico.get_full_name() or ot.tecnico.username

        data = {
            'event': 'ot_report_sent',
            'ot_id': ot.id,
            'codigo': str(ot.codigo_de_orden or ""),
            'tipo_ot': str(ot.tipo or ""),
            'estado': str(ot.get_estado_display() or ""),
            'fecha_termino': str(ot.fecha_ejecucion.isoformat()) if ot.fecha_ejecucion else "",
            'inicio_programado': str(ot.inicio_programado.isoformat()) if ot.inicio_programado else "",
            'fin_programado': str(ot.fin_programado.isoformat()) if ot.fin_programado else "",
            
            # Campos de texto pre-formateados (Recomendado para Power Automate)
            'inicio_str': inicio_local.strftime('%d/%m/%Y %H:%M'),
            'fin_str': fin_local.strftime('%d/%m/%Y %H:%M'),
            'termino_str': termino_local.strftime('%d/%m/%Y %H:%M') if termino_local else "Pendiente / En Ejecución",

            'tecnico_lider': str(nombre_tecnico),
            'tecnicos_equipo': str(tecnicos_nombres),
            'tecnico_dni': str(tecnico_dni),
            'tecnico_empresa': str(empresa_final),
            'supervisor': str(ot.supervisor.get_full_name() if ot.supervisor else "No asignado"),
            'activos': str(activos_nombres),
            'ubicacion': str(ot.ubicacion.nombre if ot.ubicacion else "No especificada"),
            'ubicacion_completa': str(ot.ubicacion.get_ruta_completa() if ot.ubicacion else "No especificada"),
            'descripcion_corta': str(ot.descripcion_corta or (ot.rutina.nombre if ot.rutina else "OT Correctiva")),
            'descripcion_detallada': str(ot.descripcion_detallada or ""),
            'pdf_url': str(request.build_absolute_uri(archivo_pdf.archivo.url)) if archivo_pdf else "",
            'pdf_name': str(archivo_pdf.nombre) if archivo_pdf else "",
            'user_triggered': str(request.user.get_full_name() or request.user.username),
            'site_url': str(settings.SITE_URL or ""),
            'emails_departamento': departamento_emails,
        }

        import requests
        response = requests.post(webhook_url, json=data, timeout=10)
        
        # Si el status code es 400, forzar el detalle en la excepción
        if not response.ok:
            raise Exception(f"{response.status_code} - {response.text}")
            
        return JsonResponse({'status': 'success', 'message': 'OTNP enviada'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Error llamando al webhook: {str(e)}'}, status=500)

@staff_member_required
def mobile_ot_whatsapp_webhook(request, pk):
    """
    Triggers a WhatsApp notification via n8n.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
    
    ot = get_object_or_404(OrdenTrabajo, pk=pk)
    
    # 1. Asegurar que el PDF existe
    filename = f"OT_{ot.id}.pdf"
    archivo_pdf = ArchivoOrdenTrabajo.objects.filter(orden_trabajo=ot, nombre=filename).first()
    
    if not archivo_pdf:
        from ..services import WorkOrderService
        try:
            archivo_pdf = WorkOrderService.save_ot_pdf_as_attachment(ot.id)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'Error generando PDF: {str(e)}'}, status=500)

    # --- Web Push Notification (Directa desde Django) ---
    try:
        pdf_url_full = str(request.build_absolute_uri(archivo_pdf.archivo.url)) if archivo_pdf else ""
        payload = {
            "title": f"🛠️ Notificación OT {ot.id}",
            "body": f"Se ha solicitado seguimiento para la OT {ot.id} en {ot.ubicacion.nombre if ot.ubicacion else 'S/U'}",
            "icon": "/static/core/img/icon-512.png",
            "url": pdf_url_full
        }
        
        if ot.tecnico:
            send_user_notification(user=ot.tecnico, payload=payload, ttl=1000)
        if ot.supervisor:
            send_user_notification(user=ot.supervisor, payload=payload, ttl=1000)
        
        # Enviar también al usuario que gatilló la acción (tú)
        if request.user != ot.tecnico and request.user != ot.supervisor:
            send_user_notification(user=request.user, payload=payload, ttl=1000)
            
    except Exception as push_err:
        print(f"Error enviando Web Push: {str(push_err)}")

    # --- Webhook para n8n ---
    webhook_url = getattr(settings, 'N8N_OT_WHATSAPP_WEBHOOK_URL', None) # Reutilizamos la misma variable
    if webhook_url:
        tecnico_nombre = ot.tecnico_puesto.nombre if ot.tecnico_puesto else (ot.tecnico.get_full_name() if ot.tecnico else "No asignado")
        data = {
            'event': 'ot_notification',
            'ot_id': ot.id,
            'codigo': str(ot.codigo_de_orden or ""),
            'tecnico': tecnico_nombre,
            'ubicacion': str(ot.ubicacion.nombre if ot.ubicacion else "No especificada"),
            'descripcion': str(ot.descripcion_corta or ""),
            'pdf_url': pdf_url_full,
        }
        try:
            import requests
            requests.post(webhook_url, json=data, timeout=5)
        except:
            pass

    return JsonResponse({'status': 'success', 'message': 'Notificaciones enviadas (Web Push + n8n)'})
