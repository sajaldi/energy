from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from ..models import OrdenTrabajo, Aviso, TecnicoPuesto, Empresa, Rutina
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
    # Incluye NO_PROGRAMADA sin filtro de fecha (siempre visibles)
    proximas_ots = OrdenTrabajo.objects.filter(
        Q(inicio_programado__date=today, estado__in=['ESPERA', 'PROGRAMADA', 'EJECUCION']) |
        Q(tipo='NO_PROGRAMADA')
    ).select_related('rutina', 'aviso', 'ubicacion', 'tecnico').order_by('inicio_programado')[:15]
    
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


@staff_member_required
def ordenes_lista_view(request):
    """Vista de listado de órdenes de trabajo con búsqueda avanzada y selección de columnas."""
    from django.db.models import Max

    q = request.GET.get('q', '')
    estado = request.GET.get('estado', '')
    tipo = request.GET.get('tipo', '')
    prioridad = request.GET.get('prioridad', '')
    rutina_id = request.GET.get('rutina', '').split(',')[0].strip()
    if rutina_id and not rutina_id.isdigit():
        rutina_id = ''

    ordenes = OrdenTrabajo.objects.select_related(
        'rutina', 'ubicacion', 'tecnico_puesto', 'empresa_responsable'
    ).order_by('-inicio_programado')

    if q:
        ordenes = ordenes.filter(
            Q(codigo_de_orden__icontains=q) |
            Q(descripcion_corta__icontains=q) |
            Q(descripcion_detallada__icontains=q) |
            Q(rutina__nombre__icontains=q) |
            Q(ubicacion__nombre__icontains=q)
        )
    if estado:
        ordenes = ordenes.filter(estado=estado)
    if tipo:
        ordenes = ordenes.filter(tipo=tipo)
    if prioridad:
        ordenes = ordenes.filter(prioridad=prioridad)
    if rutina_id:
        ordenes = ordenes.filter(rutina_id=rutina_id)

    # Filtro de rango de fechas
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    if fecha_desde:
        ordenes = ordenes.filter(inicio_programado__date__gte=fecha_desde)
    if fecha_hasta:
        ordenes = ordenes.filter(inicio_programado__date__lte=fecha_hasta)

    # Rutinas para el selector
    rutinas = Rutina.objects.order_by('nombre').values_list('id', 'nombre')

    context = {
        'ordenes': ordenes[:100],
        'total': ordenes.count(),
        'q': q,
        'estado_filter': estado,
        'tipo_filter': tipo,
        'prioridad_filter': prioridad,
        'rutina_filter': rutina_id,
        'rutinas': rutinas,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
    }
    return render(request, 'mantenimiento/ordenes_lista.html', context)


@staff_member_required
def ordenes_bulk_delete(request):
    """Eliminación masiva de órdenes de trabajo con verificación de contraseña (con gracia de 10 min)."""
    import json
    from django.http import JsonResponse
    from django.contrib.auth import authenticate
    from django.utils import timezone

    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

    try:
        data = json.loads(request.body)
        password = data.get('password', '')
        orden_ids = data.get('ids', [])

        if not orden_ids:
            return JsonResponse({'status': 'error', 'message': 'No se seleccionaron órdenes.'}, status=400)

        # Check if password was verified recently (10-minute grace period)
        last_verified = request.session.get('bulk_delete_verified_at')
        now = timezone.now().timestamp()
        grace_period = 600  # 10 minutes

        if last_verified and (now - last_verified) < grace_period:
            # Within grace period — no password needed
            pass
        else:
            # Require password verification
            if not password:
                return JsonResponse({'status': 'error', 'message': 'Ingresa tu contraseña.'}, status=403)
            user = authenticate(username=request.user.username, password=password)
            if user is None:
                return JsonResponse({'status': 'error', 'message': 'Contraseña incorrecta.'}, status=403)
            # Store verification timestamp
            request.session['bulk_delete_verified_at'] = now

        # Eliminar las órdenes
        ordenes = OrdenTrabajo.objects.filter(id__in=orden_ids)
        count = ordenes.count()
        ordenes.delete()

        return JsonResponse({
            'status': 'success',
            'message': f'{count} orden(es) eliminada(s) correctamente.'
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@staff_member_required
def ordenes_bulk_status(request):
    """Cambio masivo de estado de órdenes de trabajo con fecha de finalización."""
    import json
    from django.http import JsonResponse
    from django.utils import timezone
    from datetime import datetime

    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

    try:
        data = json.loads(request.body)
        ordenes_data = data.get('ordenes', [])

        if not ordenes_data:
            return JsonResponse({'status': 'error', 'message': 'No se enviaron órdenes.'}, status=400)

        updated = 0
        for item in ordenes_data:
            ot_id = item.get('id')
            nuevo_estado = item.get('estado')
            fecha_fin_str = item.get('fecha_fin', '')

            if not ot_id or not nuevo_estado:
                continue

            try:
                ot = OrdenTrabajo.objects.get(id=ot_id)
                if nuevo_estado in dict(OrdenTrabajo.ESTADO_CHOICES):
                    ot.estado = nuevo_estado
                    if nuevo_estado == 'REALIZADA' and fecha_fin_str:
                        try:
                            ot.fin_programado = datetime.strptime(fecha_fin_str, '%Y-%m-%d')
                        except ValueError:
                            pass
                    if nuevo_estado == 'EJECUCION' and not ot.fecha_ejecucion:
                        ot.fecha_ejecucion = timezone.now()
                    ot.save()
                    updated += 1
            except OrdenTrabajo.DoesNotExist:
                continue

        return JsonResponse({
            'status': 'success',
            'message': f'{updated} orden(es) actualizada(s) correctamente.'
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
