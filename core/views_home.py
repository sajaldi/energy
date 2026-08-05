import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from .models import AdminNavMenu, PerfilUsuario


@login_required
def home(request):
    """
    Página de inicio personalizable por perfil: grilla de tarjetas (módulos)
    con sub-accesos, filtrada por rol (grupos), permisos y la personalización
    individual de PerfilUsuario.nav_config.
    """
    user = request.user
    menus = AdminNavMenu.get_menus_usuario(user)

    base = AdminNavMenu.menus_base(user)
    perfil = getattr(user, 'perfil', None)
    config = (perfil.nav_config or {}) if perfil else {}
    hidden = config.get('hidden_menus', []) or []
    custom = config.get('custom_menus', []) or []
    customized = config.get('customized_menus', {}) or {}

    all_menus = []
    for m in base:
        item = dict(m)
        item['hidden'] = m['name'] in hidden
        item['customized'] = m['name'] in customized
        all_menus.append(item)

    context = {
        'title': 'Inicio',
        'user': user,
        'menus_json': json.dumps(menus, ensure_ascii=False),
        'all_menus_json': json.dumps(all_menus, ensure_ascii=False),
        'hidden_menus_json': json.dumps(hidden, ensure_ascii=False),
        'custom_menus_json': json.dumps(custom, ensure_ascii=False),
    }
    return render(request, 'core/home.html', context)


@login_required
@csrf_exempt
def guardar_home_config(request):
    """
    Guarda la personalización del inicio del usuario en PerfilUsuario.nav_config
    (misma estructura que el editor del menú del admin: hidden_menus, custom_menus).
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        payload = {}

    perfil, _ = PerfilUsuario.objects.get_or_create(usuario=request.user)
    config = perfil.nav_config or {}

    if 'hidden_menus' in payload:
        config['hidden_menus'] = [h for h in (payload.get('hidden_menus') or []) if h]

    if 'custom_menus' in payload:
        clean = []
        for c in payload.get('custom_menus') or []:
            if isinstance(c, dict) and c.get('name'):
                clean.append(c)
        config['custom_menus'] = clean

    perfil.nav_config = config
    perfil.save(update_fields=['nav_config'])
    return JsonResponse({'ok': True})
