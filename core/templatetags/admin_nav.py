import json
from django import template
from django.conf import settings
from django.core.cache import cache

register = template.Library()

CACHE_KEY = "admin_nav_groups_data"


def _get_user_config(user):
    try:
        perfil = getattr(user, "perfil", None)
        if perfil and isinstance(perfil.nav_config, dict):
            return perfil.nav_config
    except Exception:
        pass
    return {}


def _build_from_db(user):
    from core.models import AdminNavMenu

    menus = AdminNavMenu.objects.filter(active=True).order_by("order")
    result = []
    for menu in menus:
        if menu.superuser_only and not user.is_superuser:
            continue

        items_qs = menu.items.order_by("group", "order")

        grouped = {}
        for item in items_qs:
            perm = item.permission
            if perm:
                try:
                    if not user.has_perm(perm):
                        continue
                except Exception:
                    continue

            heading = item.group or "General"
            if heading not in grouped:
                grouped[heading] = []
            grouped[heading].append({"name": item.name, "url": item.url})

        cols = [{"heading": h, "items": items} for h, items in grouped.items()]
        if cols:
            result.append({"name": menu.name, "icon": menu.icon, "color": menu.color, "columns": cols})
    return result


def _merge_user_config(default_data, user_config):
    if not user_config:
        return default_data

    hidden_menus = user_config.get("hidden_menus", []) or []
    custom_menus = user_config.get("custom_menus", []) or []
    customized = user_config.get("customized_menus", {}) or {}

    result = []
    for menu in default_data:
        if menu["name"] in hidden_menus:
            continue
        if menu["name"] in customized:
            merged = dict(menu)
            merged["columns"] = customized[menu["name"]].get("columns", menu["columns"])
            result.append(merged)
        else:
            result.append(menu)

    result.extend(custom_menus)
    return result


@register.simple_tag(takes_context=True)
def admin_nav_groups_json(context):
    user = context.get("user")
    if not user or not user.is_authenticated:
        return "[]"

    try:
        from core.models import AdminNavMenu
        has_db = AdminNavMenu.objects.exists()
    except Exception:
        has_db = False

    if has_db:
        data = _build_from_db(user)
    else:
        data = _build_from_settings(user)

    user_config = _get_user_config(user)
    data = _merge_user_config(data, user_config)

    return json.dumps(data)


def _build_from_settings(user):
    groups = getattr(settings, "ADMIN_NAV_GROUPS", [])
    result = []
    for group in groups:
        if group.get("superuser_only") and not user.is_superuser:
            continue
        cols = group.get("columns", [])
        filtered_cols = []
        for col in cols:
            items = []
            for item in col.get("items", []):
                perm = item.get("perm")
                if perm:
                    try:
                        if not user.has_perm(perm):
                            continue
                    except Exception:
                        continue
                items.append({"name": item["name"], "url": item["url"]})
            if items:
                filtered_cols.append({"heading": col.get("heading", ""), "items": items})
        if filtered_cols:
            result.append({
                "name": group["name"],
                "icon": group.get("icon", ""),
                "color": group.get("color", ""),
                "columns": filtered_cols,
            })
    return result
