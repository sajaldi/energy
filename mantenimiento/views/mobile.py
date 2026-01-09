import collections
from datetime import datetime
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from django.db.models import Count, Q, Min
from ..models import Programacion, OrdenTrabajo, Aviso
from activos.models import Activo, Ubicacion

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
