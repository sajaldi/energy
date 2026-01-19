from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from django.db.models import Q
from ..models import PermisoTrabajo, TipoPermiso, VerificacionRequisito, RequisitoPermiso
from mantenimiento.models import OrdenTrabajo

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
    ).order_by('-creado_en')
    
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
        # Guardar cambios en el checklist
        for key, value in request.POST.items():
            if key.startswith('check_'):
                verif_id = key.split('_')[1]
                verif = VerificacionRequisito.objects.get(id=verif_id, permiso=permiso)
                verif.cumple = (value == 'on')
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
    
    verificaciones = permiso.verificaciones.select_related('requisito').all()
    
    return render(request, 'seguridad/mobile/permiso_detalle.html', {
        'permiso': permiso,
        'verificaciones': verificaciones
    })

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
