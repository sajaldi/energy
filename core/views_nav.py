import json
from django.shortcuts import render, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from .models import AdminNavMenu, PerfilUsuario


@staff_member_required
def menu_config_view(request):
    user = request.user
    perfil, _ = PerfilUsuario.objects.get_or_create(usuario=user)
    config = perfil.nav_config or {}
    hidden_menus = config.get("hidden_menus", []) or []
    custom_menus = config.get("custom_menus", []) or []

    defaults = AdminNavMenu.objects.filter(active=True).order_by("order")

    if request.method == "POST":
        new_hidden = request.POST.getlist("hidden_menus")
        new_hidden = [h for h in new_hidden if h]

        custom_raw = request.POST.get("custom_menus_json", "[]")
        try:
            new_custom = json.loads(custom_raw)
            if not isinstance(new_custom, list):
                new_custom = []
        except (json.JSONDecodeError, TypeError):
            new_custom = []

        clean_custom = []
        for c in new_custom:
            if isinstance(c, dict) and c.get("name"):
                clean_custom.append(c)
        new_custom = clean_custom

        customized_raw = request.POST.get("customized_menus_json", "{}")
        try:
            customized = json.loads(customized_raw)
            if not isinstance(customized, dict):
                customized = {}
        except (json.JSONDecodeError, TypeError):
            customized = {}

        perfil.nav_config = {
            "hidden_menus": new_hidden,
            "custom_menus": new_custom,
            "customized_menus": customized,
        }
        perfil.save(update_fields=["nav_config"])
        messages.success(request, "Menú personalizado guardado correctamente.")
        return redirect("menu_config")

    customized = config.get("customized_menus", {}) or {}

    default_data = []
    for m in defaults:
        if m.superuser_only and not user.is_superuser:
            continue
        grouped = {}
        for item in m.items.order_by("group", "order"):
            heading = item.group or "General"
            if heading not in grouped:
                grouped[heading] = []
            grouped[heading].append({"name": item.name, "url": item.url})
        cols = [{"heading": h, "items": items} for h, items in grouped.items()]
        default_data.append({
            "id": m.id,
            "name": m.name,
            "icon": m.icon,
            "color": m.color,
            "columns": cols,
            "superuser_only": m.superuser_only,
        })

    return render(request, "admin/menu_config.html", {
        "defaults": default_data,
        "defaults_json": json.dumps(default_data, ensure_ascii=False),
        "hidden_menus": hidden_menus,
        "custom_menus_json": json.dumps(custom_menus, ensure_ascii=False),
        "customized_menus_json": json.dumps(customized, ensure_ascii=False),
    })
