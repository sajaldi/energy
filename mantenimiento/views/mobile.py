import collections
from datetime import datetime
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from django.db.models import Count, Q, Min
from ..models import Programacion, OrdenTrabajo, Aviso, ValorPasoOrden, PasoProcedimiento
from activos.models import Activo, Ubicacion, DocumentoMedicion

@staff_member_required
def mobile_cronograma(request):
    user_filter = Q()
    if not request.user.is_superuser:
        user_filter = Q(ordenes__tecnico=request.user) | Q(ordenes__equipo__in=request.user.groups.all())
    progs = Programacion.objects.select_related('rutina__frecuencia', 'rutina__categoria')
    if not request.user.is_superuser: progs = progs.filter(user_filter).distinct()
    progs = progs.annotate(total_ots=Count('ordenes', filter=user_filter if not request.user.is_superuser else None), completas_ots=Count('ordenes', filter=(Q(ordenes__estado='REALIZADA') & user_filter) if not request.user.is_superuser else Q(ordenes__estado='REALIZADA')), proxima_ot=Min('ordenes__inicio_programado', filter=(Q(ordenes__inicio_programado__gte=timezone.now()) & user_filter) if not request.user.is_superuser else Q(ordenes__inicio_programado__gte=timezone.now()))).order_by('rutina__nombre')
    for p in progs: p.progreso_porcentaje = int((p.completas_ots / p.total_ots) * 100) if p.total_ots > 0 else 0
    return render(request, 'mantenimiento/mobile_cronograma.html', {'programaciones': progs})

@staff_member_required
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
def mobile_ot_detalle(request, pk):
    ot = get_object_or_404(OrdenTrabajo.objects.select_related('rutina', 'ubicacion', 'tecnico', 'aviso', 'programacion').prefetch_related('activos'), pk=pk)
    return render(request, 'mantenimiento/mobile_ot_detalle.html', {'ot': ot})

@staff_member_required
def mobile_crear_aviso(request):
    aid = request.GET.get('activo'); activo = get_object_or_404(Activo, id=aid) if aid else None
    if request.method == 'POST':
        aviso = Aviso.objects.create(activo=activo, ubicacion=activo.ubicacion if activo else None, descripcion=request.POST.get('descripcion'), prioridad=request.POST.get('prioridad', 'MEDIA'), tipo=request.POST.get('tipo', 'SOLICITUD'), solicitante=request.user, foto=request.FILES.get('foto'))
        if activo: return redirect('activos:mobile_activo_detalle', pk=activo.id)
        return redirect('core:mobile_dashboard')
    return render(request, 'mantenimiento/mobile_crear_aviso.html', {'activo': activo, 'prioridades': Aviso.PRIORIDAD_CHOICES, 'tipos': Aviso.TIPO_CHOICES})

@staff_member_required
def mobile_ot_iniciar(request, pk):
    ot = get_object_or_404(OrdenTrabajo, pk=pk)
    if ot.estado in ['PROGRAMADA', 'ESPERA']:
        ot.estado = 'EJECUCION'
        ot.fecha_ejecucion = timezone.now()
        ot.save()
    return redirect('mantenimiento:mobile_ot_finalizar', pk=ot.id)

@staff_member_required
def mobile_ot_finalizar(request, pk):
    ot = get_object_or_404(OrdenTrabajo, pk=pk)
    
    # Obtener el procedimiento y sus pasos
    pasos = []
    if ot.rutina and ot.rutina.procedimiento_estandar:
        pasos = ot.rutina.procedimiento_estandar.pasos.all().order_by('orden')
    
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
            
            if valor_text or valor_num or valor_bool or no_aplica or paso.tipo_respuesta == 'MEDICION':
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
        
        # 3. Actualizar estado según la acción
        accion = request.POST.get('action')
        if accion == 'finalize':
            ot.estado = 'REALIZADA'
            ot.fecha_termino = timezone.now()
            ot.save()
            return redirect('mantenimiento:mobile_ot_detalle', pk=ot.id)
        
        # Por defecto solo guardamos y nos quedamos en la misma pantalla (o volvemos al detalle)
        return redirect('mantenimiento:mobile_ot_detalle', pk=ot.id)

    return render(request, 'mantenimiento/mobile_ot_finalizar.html', {
        'ot': ot,
        'pasos': pasos,
        'puntos_medicion': puntos_medicion_extra
    })
