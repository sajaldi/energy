import json
from django.http import JsonResponse
from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Notificacion


@require_GET
def api_conteo(request):
    if not request.user.is_authenticated:
        return JsonResponse({'count': 0})
    count = Notificacion.conteo_no_leidas(request.user)
    return JsonResponse({'count': count})


@require_GET
def api_no_leidas(request):
    if not request.user.is_authenticated:
        return JsonResponse({'notificaciones': []})
    notifs = Notificacion.no_leidas(request.user)[:10]
    data = [{
        'id': n.id,
        'titulo': n.titulo,
        'mensaje': n.mensaje,
        'tipo': n.tipo,
        'modulo': n.modulo,
        'enlace': n.enlace,
        'icono': n.icono,
        'creado_en': n.creado_en.strftime('%Y-%m-%d %H:%M:%S'),
        'tiempo': _tiempo_relativo(n.creado_en),
    } for n in notifs]
    return JsonResponse({'notificaciones': data})


@require_GET
def api_todas(request):
    if not request.user.is_authenticated:
        return JsonResponse({'notificaciones': [], 'total': 0})
    notifs = Notificacion.objects.filter(user=request.user)
    tipo = request.GET.get('tipo')
    modulo = request.GET.get('modulo')
    leida = request.GET.get('leida')
    q = request.GET.get('q')
    if tipo:
        notifs = notifs.filter(tipo=tipo)
    if modulo:
        notifs = notifs.filter(modulo=modulo)
    if leida in ('0', '1'):
        notifs = notifs.filter(leida=(leida == '1'))
    if q:
        notifs = notifs.filter(Q(titulo__icontains=q) | Q(mensaje__icontains=q))
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 20))
    paginator = Paginator(notifs, per_page)
    page_obj = paginator.get_page(page)
    data = [{
        'id': n.id,
        'titulo': n.titulo,
        'mensaje': n.mensaje,
        'tipo': n.tipo,
        'modulo': n.modulo,
        'enlace': n.enlace,
        'icono': n.icono,
        'leida': n.leida,
        'creado_en': n.creado_en.strftime('%Y-%m-%d %H:%M:%S'),
        'tiempo': _tiempo_relativo(n.creado_en),
    } for n in page_obj]
    return JsonResponse({
        'notificaciones': data,
        'total': paginator.count,
        'page': page,
        'pages': paginator.num_pages,
    })


@csrf_exempt
@require_POST
def api_marcar_leida(request):
    if not request.user.is_authenticated:
        return JsonResponse({'status': 'error', 'message': 'No autenticado'}, status=401)
    try:
        data = json.loads(request.body)
        notif_id = data.get('notif_id')
        if notif_id:
            Notificacion.objects.filter(id=notif_id, user=request.user).update(leida=True)
        else:
            Notificacion.objects.filter(user=request.user, leida=False).update(leida=True)
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@staff_member_required
def pagina_notificaciones(request):
    tipos = [{'value': c[0], 'label': c[1]} for c in Notificacion.TIPO_CHOICES]
    modulos = [{'value': c[0], 'label': c[1]} for c in Notificacion.MODULO_CHOICES]
    return render(request, 'notificaciones/admin_pagina.html', {
        'tipos': tipos,
        'modulos': modulos,
        'title': 'Centro de Notificaciones',
    })


def portal_notificaciones(request):
    tipos = [{'value': c[0], 'label': c[1]} for c in Notificacion.TIPO_CHOICES]
    modulos = [{'value': c[0], 'label': c[1]} for c in Notificacion.MODULO_CHOICES]
    return render(request, 'notificaciones/portal_pagina.html', {
        'tipos': tipos,
        'modulos': modulos,
        'active_tab': 'notificaciones',
    })


def _tiempo_relativo(dt):
    from django.utils import timezone
    delta = timezone.now() - dt
    if delta.days > 0:
        return f'hace {delta.days}d'
    if delta.seconds >= 3600:
        return f'hace {delta.seconds // 3600}h'
    if delta.seconds >= 60:
        return f'hace {delta.seconds // 60}min'
    return 'ahora'
