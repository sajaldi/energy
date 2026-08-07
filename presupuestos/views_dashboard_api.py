import json

from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods

from .models import DashboardView


@login_required
def dashboard_views_list_create(request):
    """
    GET  → Listar vistas del usuario autenticado.
    POST → Crear una nueva vista personalizada.
    """
    if request.method == 'GET':
        return _list_views(request)
    elif request.method == 'POST':
        return _create_view(request)
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)


def _list_views(request):
    """Retorna todas las vistas del usuario autenticado ordenadas por nombre."""
    views = DashboardView.objects.filter(user=request.user).values(
        'id', 'name', 'columns', 'sort_column', 'sort_direction', 'is_last_used'
    )
    return JsonResponse({'views': list(views)})


def _create_view(request):
    """Crea una nueva vista personalizada para el usuario autenticado."""
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse(
            {'status': 'error', 'message': 'JSON inválido'},
            status=400
        )

    name = data.get('name', '').strip()

    # Validar nombre no vacío
    if not name:
        return JsonResponse(
            {'status': 'error', 'message': 'El nombre de la vista es obligatorio.'},
            status=400
        )

    # Validar máximo 10 vistas por usuario
    if DashboardView.objects.filter(user=request.user).count() >= 10:
        return JsonResponse(
            {'status': 'error', 'message': 'Has alcanzado el límite de 10 vistas. Elimina una vista existente antes de crear una nueva.'},
            status=400
        )

    columns = data.get('columns', [])
    sort_column = data.get('sort_column') or None
    sort_direction = data.get('sort_direction') or None

    try:
        view = DashboardView.objects.create(
            user=request.user,
            name=name,
            columns=columns,
            sort_column=sort_column,
            sort_direction=sort_direction,
        )
    except IntegrityError:
        return JsonResponse(
            {'status': 'error', 'message': f'Ya existe una vista con el nombre "{name}".'},
            status=400
        )

    return JsonResponse({
        'status': 'ok',
        'view': {
            'id': view.id,
            'name': view.name,
            'columns': view.columns,
            'sort_column': view.sort_column,
            'sort_direction': view.sort_direction,
            'is_last_used': view.is_last_used,
        }
    }, status=201)


@login_required
@require_http_methods(["POST", "DELETE"])
def dashboard_view_delete(request, pk):
    """Elimina una vista personalizada. Verifica que pertenezca al usuario."""
    try:
        view = DashboardView.objects.get(pk=pk, user=request.user)
    except DashboardView.DoesNotExist:
        return JsonResponse(
            {'status': 'error', 'message': 'Vista no encontrada.'},
            status=404
        )

    view.delete()
    return JsonResponse({'status': 'ok'})


@login_required
@require_POST
def dashboard_view_apply(request, pk):
    """Marca una vista como última usada y desmarca las demás del usuario."""
    try:
        view = DashboardView.objects.get(pk=pk, user=request.user)
    except DashboardView.DoesNotExist:
        return JsonResponse(
            {'status': 'error', 'message': 'Vista no encontrada.'},
            status=404
        )

    # Desmarcar todas las vistas del usuario
    DashboardView.objects.filter(user=request.user, is_last_used=True).update(is_last_used=False)
    # Marcar la vista seleccionada
    view.is_last_used = True
    view.save(update_fields=['is_last_used', 'updated_at'])

    return JsonResponse({
        'status': 'ok',
        'view': {
            'id': view.id,
            'name': view.name,
            'columns': view.columns,
            'sort_column': view.sort_column,
            'sort_direction': view.sort_direction,
            'is_last_used': view.is_last_used,
        }
    })


@login_required
@require_POST
def dashboard_views_reset(request):
    """Limpia la última vista usada del usuario (todas is_last_used=False)."""
    DashboardView.objects.filter(user=request.user, is_last_used=True).update(is_last_used=False)
    return JsonResponse({'status': 'ok'})


@login_required
def requisicion_detail_api(request, pk):
    """Retorna los datos de una requisición + historial para el modal del dashboard."""
    from .models import Requisicion

    # Si llegó aquí sin estar autenticado (edge case), retornar 403 JSON
    if not request.user.is_authenticated:
        return JsonResponse({'status': 'error', 'message': 'No autenticado.'}, status=403)

    try:
        req = Requisicion.objects.select_related(
            'usuario_solicitante__perfil__departamento', 'aprobador', 'partida', 'proveedor',
        ).prefetch_related(
            'historial', 'articulos', 'ordenes_compra',
        ).get(pk=pk)
    except Requisicion.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Requisición no encontrada.'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Error al cargar requisición: {str(e)}'}, status=500)

    # Artículos
    articulos = []
    for art in req.articulos.all():
        articulos.append({
            'descripcion': art.cr8ca_articulo or '-',
            'cantidad': float(art.cr8ca_cantidad or 0),
            'costo_unitario': float(art.cr8ca_costoaproximado or 0),
            'subtotal': float((art.cr8ca_cantidad or 0) * (art.cr8ca_costoaproximado or 0)),
        })

    # Historial
    historial = []
    for h in req.historial.all().order_by('creado_en'):
        historial.append({
            'estado_anterior': h.get_estado_anterior_display() if h.estado_anterior else None,
            'estado_nuevo': h.get_estado_nuevo_display(),
            'estado_nuevo_raw': h.estado_nuevo,
            'fecha': h.creado_en.strftime('%d/%m/%Y %H:%M') if h.creado_en else '',
            'usuario': h.usuario.get_full_name() or h.usuario.username if h.usuario else None,
            'descripcion': h.descripcion or '',
        })

    # Órdenes de compra
    ordenes = []
    for oc in req.ordenes_compra.all():
        ordenes.append({
            'numero': oc.numero_oc,
            'estado': oc.get_estado_display() if hasattr(oc, 'get_estado_display') else oc.estado,
            'proveedor': str(oc.proveedor) if oc.proveedor else '-',
            'total': float(oc.total or 0),
        })

    # Departamento
    dept_nombre = '-'
    try:
        if req.usuario_solicitante and hasattr(req.usuario_solicitante, 'perfil') and req.usuario_solicitante.perfil.departamento:
            dept_nombre = req.usuario_solicitante.perfil.departamento.nombre
    except Exception:
        pass

    data = {
        'requisicion': req.cr8ca_requisicion,
        'asunto': req.cr8ca_asunto or '-',
        'motivo': req.cr8ca_motivo or '-',
        'comentarios': req.cr8ca_comentarios or '-',
        'fecha': req.fecha.strftime('%d/%m/%Y') if req.fecha else '-',
        'prioridad': req.get_cr8ca_prioridad_display() if req.cr8ca_prioridad else '-',
        'prioridad_valor': req.cr8ca_prioridad,
        'estado': req.get_estado_requisicion_display(),
        'estado_raw': req.estado_requisicion,
        'tipo': req.get_tipo_display() if req.tipo else '-',
        'total': float(req.cr8ca_totalenarticulos or 0),
        'solicitante': req.usuario_solicitante.get_full_name() or req.usuario_solicitante.username if req.usuario_solicitante else '-',
        'aprobador': req.aprobador.get_full_name() or req.aprobador.username if req.aprobador else '-',
        'departamento': dept_nombre,
        'proveedor': str(req.proveedor) if req.proveedor else '-',
        'partida': str(req.partida) if req.partida else '-',
        'articulos': articulos,
        'historial': historial,
        'ordenes_compra': ordenes,
        'edit_url': f'/presupuestos/requisiciones/editar/{req.pk}/',
    }

    return JsonResponse(data)
