from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.utils import timezone
import json
from ..models import (
    PermisoTrabajo, TipoPermiso, RequisitoPermiso, VerificacionRequisito,
    Incidente, Inspeccion, AsignacionEPP, AnalisisRiesgo, LevantamientoConfiscacion
)
from mantenimiento.models import OrdenTrabajo
from django.db.models import Count, Q


@login_required
@permission_required('seguridad.add_permisotrabajo', raise_exception=True)
def generar_permiso_de_ot(request, ot_id):
    """
    Vista intermedia para crear un Permiso de Trabajo a partir de una OT.
    Pre-llena datos y vincula el permiso.
    """
    ot = get_object_or_404(OrdenTrabajo, pk=ot_id)
    
    if request.method == 'POST':
        tipo_id = request.POST.get('tipo_permiso')
        if not tipo_id:
            messages.error(request, "Debe seleccionar un tipo de permiso.")
            return redirect('seguridad:generar_permiso_ot', ot_id=ot.id)
            
        tipo = get_object_or_404(TipoPermiso, pk=tipo_id)
        
        # Crear Permiso
        permiso = PermisoTrabajo.objects.create(
            tipo=tipo,
            orden_trabajo=ot,
            ubicacion=ot.ubicacion,
            descripcion_trabajo=f"Trabajo vinculado a OT-{ot.id}: {ot.rutina.nombre if ot.rutina else ot.aviso.descripcion if ot.aviso else 'Mantenimiento General'}",
            fecha_inicio=ot.inicio_programado,
            fecha_fin=ot.fin_programado or (ot.inicio_programado + timezone.timedelta(hours=4)),
            solicitante=request.user,
            estado='BORRADOR'
        )
        
        # Generar Checklist de Requisitos
        requisitos = tipo.requisitos.all()
        for req in requisitos:
            VerificacionRequisito.objects.create(
                permiso=permiso,
                requisito=req
            )
            
        messages.success(request, f"Permiso de Trabajo #{permiso.id} generado exitosamente.")
        return redirect('seguridad:detalle_permiso', permiso_id=permiso.id)

    tipos_permiso = TipoPermiso.objects.all()
    context = {
        'ot': ot,
        'tipos_permiso': tipos_permiso,
        'title': f'Generar Permiso para OT-{ot.id}'
    }
    return render(request, 'seguridad/generar_permiso_form.html', context)

@login_required
def detalle_permiso_view(request, permiso_id):
    """
    Vista visual estilo 'papel' para ver/imprimir y gestionar el permiso.
    """
    permiso = get_object_or_404(PermisoTrabajo, pk=permiso_id)
    
    if request.method == 'POST':
        # Guardar cambios en el checklist
        for key, value in request.POST.items():
            if key.startswith('check_'):
                verif_id = key.split('_')[1]
                verif = VerificacionRequisito.objects.get(id=verif_id)
                verif.cumple = (value == 'on')
                verif.save()
            elif key.startswith('obs_'):
                verif_id = key.split('_')[1]
                verif = VerificacionRequisito.objects.get(id=verif_id)
                verif.observacion = value
                verif.save()
        
        # Acciones de Estado
        accion = request.POST.get('accion')
        if accion == 'solicitar':
            permiso.estado = 'SOLICITADO'
            permiso.save()
            messages.success(request, "Permiso solicitado para autorización.")
        elif accion == 'aprobar':
            if request.user.has_perm('seguridad.change_permisotrabajo'):
                permiso.estado = 'APROBADO'
                permiso.autorizado_por = request.user
                permiso.fecha_autorizacion = timezone.now()
                permiso.save()
                messages.success(request, "Permiso APROBADO.")
            else:
                messages.error(request, "No tiene permisos para aprobar.")
                
        return redirect('seguridad:detalle_permiso', permiso_id=permiso.id)

    context = {
        'permiso': permiso,
        'verificaciones': permiso.verificaciones.all(),
        'title': f'Permiso de Trabajo #{permiso.id}'
    }
    return render(request, 'seguridad/permiso_detail.html', context)

@login_required
def dashboard_view(request):
    """
    Dashboard principal de Seguridad con KPIs y visión global.
    """
    ahora = timezone.now()
    inicio_mes = ahora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # KPIs - Incidentes
    incidentes_abiertos = Incidente.objects.exclude(estado='CERRADO')
    total_incidentes_abiertos = incidentes_abiertos.count()
    incidentes_criticos = incidentes_abiertos.filter(severidad='CRITICA').count()
    
    # KPIs - Permisos
    permisos_activos = PermisoTrabajo.objects.filter(estado__in=['SOLICITADO', 'APROBADO'])
    total_permisos_activos = permisos_activos.count()
    
    # KPIs - Inspecciones
    inspecciones_mes = Inspeccion.objects.filter(fecha__gte=inicio_mes).count()
    
    # KPIs - Confiscaciones
    confiscaciones_activas = LevantamientoConfiscacion.objects.filter(finalizado=False).count()
    
    # Datos para Gráfico de Incidentes por Severidad
    incidentes_severidad = Incidente.objects.values('severidad').annotate(total=Count('id'))
    chart_severidad = {
        'labels': [s[1] for s in Incidente.SEVERIDAD_CHOICES],
        'data': [next((i['total'] for i in incidentes_severidad if i['severidad'] == s[0]), 0) for s in Incidente.SEVERIDAD_CHOICES],
        'colors': ['#22C55E', '#EAB308', '#F97316', '#EF4444'] # Verde, Amarillo, Naranja, Rojo
    }
    
    # Datos para Gráfico de Permisos por Estado
    permisos_estado = PermisoTrabajo.objects.values('estado').annotate(total=Count('id'))
    chart_permisos = {
        'labels': [e[1] for e in PermisoTrabajo.ESTADO_PERMISO],
        'data': [next((p['total'] for p in permisos_estado if p['estado'] == e[0]), 0) for e in PermisoTrabajo.ESTADO_PERMISO]
    }
    
    # Actividad Reciente (Últimos 10 eventos)
    recent_incidents = Incidente.objects.all().order_by('-fecha_reporte')[:5]
    recent_permits = PermisoTrabajo.objects.all().order_by('-id')[:5]
    
    activity = []
    for i in recent_incidents:
        activity.append({
            'tipo': 'INCIDENTE',
            'titulo': i.titulo,
            'fecha': i.fecha_reporte,
            'usuario': i.reportado_por,
            'estado': i.get_estado_display(),
            'color': 'danger' if i.severidad in ['ALTA', 'CRITICA'] else 'warning'
        })
    for p in recent_permits:
        activity.append({
            'tipo': 'PERMISO',
            'titulo': f"Permiso {p.tipo.nombre}",
            'fecha': p.fecha_inicio,
            'usuario': p.solicitante,
            'estado': p.get_estado_display(),
            'color': 'primary' if p.estado == 'APROBADO' else 'secondary'
        })
    
    # Ordenar actividad por fecha descendente
    activity.sort(key=lambda x: x['fecha'], reverse=True)
    activity = activity[:10]
    
    context = {
        'title': 'Dashboard de Seguridad',
        'total_incidentes_abiertos': total_incidentes_abiertos,
        'incidentes_criticos': incidentes_criticos,
        'total_permisos_activos': total_permisos_activos,
        'inspecciones_mes': inspecciones_mes,
        'confiscaciones_activas': confiscaciones_activas,
        'chart_severidad': json.dumps(chart_severidad),
        'chart_permisos': json.dumps(chart_permisos),
        'activity': activity
    }
    
    return render(request, 'seguridad/dashboard.html', context)
