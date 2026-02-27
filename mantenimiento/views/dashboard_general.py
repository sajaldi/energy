from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from ..models import OrdenTrabajo, Aviso, TecnicoPuesto
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

    context = {
        'title': 'Sistema de Gestión de Mantenimiento',
        'ots_totales': ots_totales,
        'ots_pendientes': ots_pendientes,
        'ots_ejecucion': ots_ejecucion,
        'ots_preventivas': ots_preventivas,
        'ots_correctivas': ots_correctivas,
        'avisos_abiertos': avisos_abiertos,
        'avisos_criticos': avisos_criticos,
        'tecnicos_total': tecnicos_total,
        'tecnicos_disponibles': tecnicos_disponibles,
        'proximas_ots': proximas_ots,
        'avisos_prioritarios': avisos_prioritarios,
    }
    
    return render(request, 'mantenimiento/dashboard.html', context)
