from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from ..models import OrdenTrabajo, Aviso, TecnicoPuesto, Empresa
from seguridad.models import TipoPermiso
from callcenter.models import SolicitudTicket, FallaTicket
from core.models import Departamento
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta

@staff_member_required
def mantenimiento_dashboard(request):
    """
    Dashboard principal premium para el módulo de Mantenimiento.
    Muestra métricas clave, OTs del día y avisos pendientes.
    """
    now = timezone.now()
    today = now.date()
    
    # Métricas de OTs activas (sin contar las finalizadas)
    activas_filter = Q(estado__in=['ESPERA', 'PROGRAMADA', 'EJECUCION'])
    
    ots_totales = OrdenTrabajo.objects.filter(activas_filter).count()
    ots_pendientes = OrdenTrabajo.objects.filter(estado='ESPERA').count()
    ots_ejecucion = OrdenTrabajo.objects.filter(estado='EJECUCION').count()
    
    ots_preventivas = OrdenTrabajo.objects.filter(activas_filter, tipo='PREVENTIVA').count()
    ots_correctivas = OrdenTrabajo.objects.filter(activas_filter, tipo='CORRECTIVA').count()
    
    # Avisos (Notificaciones de falla) - Solo los abiertos
    avisos_abiertos = Aviso.objects.filter(estado='ABIERTO').count()
    avisos_criticos = Aviso.objects.filter(estado='ABIERTO', prioridad='CRITICA').count()
    
    # Personal
    tecnicos_total = TecnicoPuesto.objects.count()
    tecnicos_disponibles = TecnicoPuesto.objects.filter(disponible=True).count()
    
    # OTs para hoy (proximas 24 horas o del calendario de hoy)
    proximas_ots = OrdenTrabajo.objects.filter(
        inicio_programado__date=today,
        estado__in=['ESPERA', 'PROGRAMADA', 'EJECUCION']
    ).select_related('rutina', 'aviso', 'ubicacion', 'tecnico').order_by('inicio_programado')[:10]
    
    # Avisos recientes y críticos
    avisos_prioritarios = Aviso.objects.filter(
        estado__in=['ABIERTO', 'PROCESO']
    ).select_related('ubicacion', 'activo', 'solicitante').order_by('-prioridad', '-creado_en')[:8]

    # Datos para modal de creación de OTNP
    personales = TecnicoPuesto.objects.select_related('user', 'puesto', 'empresa').filter(esta_vigente=True).order_by('nombre')
    empresas = Empresa.objects.filter(activo=True).order_by('nombre')
    prioridades = OrdenTrabajo.PRIORIDAD_CHOICES
    tipos_permiso = TipoPermiso.objects.all().order_by('nombre')

    # Órdenes del departamento del usuario
    ots_mi_departamento = 0
    nombre_departamento = ""
    try:
        perfil = getattr(request.user, 'perfil', None)
        if perfil and perfil.departamento:
            nombre_departamento = perfil.departamento.nombre
            ots_mi_departamento = OrdenTrabajo.objects.filter(
                activas_filter,
                aviso__departamento=perfil.departamento
            ).count()
    except Exception:
        pass

    # Tickets abiertos del mes del departamento del usuario
    tickets_mi_depto = 0
    tickets_list = []
    inicio_mes = today.replace(day=1)
    try:
        perfil = getattr(request.user, 'perfil', None)
        if perfil and perfil.departamento:
            tickets_qs = SolicitudTicket.objects.filter(
                fecha_cierre__isnull=True, cierre_enviado=False,
                fecha_solicitud__gte=inicio_mes,
                falla_reportada__departamento_responsable=perfil.departamento
            ).select_related('ubicacion').order_by('-fecha_solicitud')[:50]
            tickets_mi_depto = tickets_qs.count()
            tickets_list = [
                {
                    'id': t.id,
                    'folio': t.folio or f"TKT-{t.id_solicitud}",
                    'solicitante': t.solicitante or '—',
                    'descripcion': (t.solicitud_descripcion or t.falla_descripcion or '')[:120],
                    'fecha': t.fecha_solicitud,
                    'ubicacion': t.ubicacion.nombre if t.ubicacion else '—',
                    'estado': 'Abierto',
                }
                for t in tickets_qs
            ]
    except Exception:
        pass

    context = {
        'title': 'Sistema de Gestión de Mantenimiento',
        'ots_totales': ots_totales,
        'ots_pendientes': ots_pendientes,
        'ots_ejecucion': ots_ejecucion,
        'ots_preventivas': ots_preventivas,
        'ots_correctivas': ots_correctivas,
        'ots_mi_departamento': ots_mi_departamento,
        'nombre_departamento': nombre_departamento,
        'avisos_abiertos': avisos_abiertos,
        'avisos_criticos': avisos_criticos,
        'tecnicos_total': tecnicos_total,
        'tecnicos_disponibles': tecnicos_disponibles,
        'proximas_ots': proximas_ots,
        'avisos_prioritarios': avisos_prioritarios,
        'personales': personales,
        'empresas': empresas,
        'prioridades': prioridades,
        'tipos_permiso': tipos_permiso,
        'tickets_mi_depto': tickets_mi_depto,
        'tickets_list': tickets_list,
    }
    
    return render(request, 'mantenimiento/dashboard.html', context)
