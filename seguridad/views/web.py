from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.utils import timezone
from ..models import PermisoTrabajo, TipoPermiso, RequisitoPermiso, VerificacionRequisito
from mantenimiento.models import OrdenTrabajo


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
