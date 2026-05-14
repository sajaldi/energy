from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from ..models import AnalisisRiesgo, PasoTrabajo, Riesgo, Control, PeligroCatalogo, MedidaControlCatalogo
from mantenimiento.models import OrdenTrabajo

@login_required
def ast_wizard_view(request, ot_id=None):
    """
    Vista del Wizard para crear un Análisis de Seguridad en el Trabajo (AST).
    """
    ot = None
    if ot_id:
        ot = get_object_or_404(OrdenTrabajo, id=ot_id)

    if request.method == 'POST':
        # Aquí procesaremos el guardado final (AJAX recomendado para Wizards complejos)
        pass

    import json
    # Datos iniciales para el Wizard
    peligros_qs = PeligroCatalogo.objects.prefetch_related('controles_recomendados').all().order_by('categoria', 'nombre')
    
    peligros_controles_map = {
        p.id: list(p.controles_recomendados.values_list('id', flat=True))
        for p in peligros_qs
    }

    ots_pendientes = OrdenTrabajo.objects.filter(
        requiere_permiso=True, 
        estado__in=['ESPERA', 'PROGRAMADA', 'EJECUCION']
    ).order_by('-id') if not ot else []

    context = {
        'ot': ot,
        'ots_pendientes': ots_pendientes,
        'peligros_cat': peligros_qs,
        'controles_cat': MedidaControlCatalogo.objects.all().order_by('tipo', 'nombre'),
        'peligros_controles_map_json': json.dumps(peligros_controles_map),
        'hoy': timezone.now().date(),
    }
    return render(request, 'seguridad/ast_wizard.html', context)

@login_required
def save_ast_ajax(request):
    """
    Guarda los datos del AST enviados vía JSON desde el Wizard.
    """
    import json
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # Limpiar IDs: convertir strings vacíos a None
            ot_id = data.get('ot_id')
            if ot_id == '' or ot_id is None:
                ot_id = None
            else:
                ot_id = int(ot_id)
            
            ubicacion_id = data.get('ubicacion_id')
            if ubicacion_id == '' or ubicacion_id is None:
                ubicacion_id = None
            else:
                ubicacion_id = int(ubicacion_id)
            
            # 1. Crear el AST
            ast = AnalisisRiesgo.objects.create(
                descripcion_trabajo=data.get('descripcion', 'Sin descripción'),
                ubicacion_id=ubicacion_id,
                lider=request.user,
                orden_trabajo_id=ot_id,
                fecha=timezone.now()
            )
            
            # 2. Agregar ejecutantes
            ejecutantes_ids = data.get('ejecutantes', [])
            if ejecutantes_ids:
                ast.ejecutantes.set(ejecutantes_ids)

            # 3. Procesar Pasos, Riesgos y Controles
            for idx, paso_data in enumerate(data.get('pasos', [])):
                paso = PasoTrabajo.objects.create(
                    analisis=ast,
                    descripcion=paso_data.get('descripcion', ''),
                    orden=idx
                )
                
                for riesgo_data in paso_data.get('riesgos', []):
                    peligro_id = riesgo_data.get('peligro_id')
                    if peligro_id == '' or peligro_id is None:
                        peligro_id = None
                    else:
                        peligro_id = int(peligro_id)
                    
                    riesgo = Riesgo.objects.create(
                        paso=paso,
                        peligro_base_id=peligro_id,
                        descripcion=riesgo_data.get('descripcion_manual', ''),
                        probabilidad=int(riesgo_data.get('probabilidad', 1)),
                        consecuencia=int(riesgo_data.get('consecuencia', 1))
                    )
                    
                    for control_id in riesgo_data.get('controles_ids', []):
                        if control_id == '' or control_id is None:
                            continue
                        # Obtener nombre del control del catálogo para el campo descripcion
                        control_base = MedidaControlCatalogo.objects.filter(id=int(control_id)).first()
                        Control.objects.create(
                            riesgo=riesgo,
                            control_base_id=int(control_id),
                            descripcion=control_base.nombre if control_base else f'Control #{control_id}'
                        )

            return JsonResponse({'status': 'success', 'ast_id': ast.id})
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    
    return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)


@login_required
def ast_view_partial(request, ast_id):
    """
    Retorna un partial HTML de solo lectura para visualizar un AST en un modal.
    """
    ast = get_object_or_404(
        AnalisisRiesgo.objects.prefetch_related(
            'pasos__riesgos__peligro_base',
            'pasos__riesgos__controles__control_base',
        ).select_related('lider', 'ubicacion', 'orden_trabajo'),
        id=ast_id
    )
    return render(request, 'seguridad/ast_view_partial.html', {'ast': ast})
