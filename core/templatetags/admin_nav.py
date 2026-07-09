import json
from django import template
from django.conf import settings
from django.core.cache import cache

register = template.Library()

CACHE_KEY = "admin_nav_groups_data"


def _build_from_db(user):
    from core.models import AdminNavMenu

    menus = AdminNavMenu.objects.filter(active=True).order_by("order")
    result = []
    for menu in menus:
        if menu.superuser_only and not user.is_superuser:
            continue
        columns = menu.columns.order_by("order")
        cols = []
        for col in columns:
            items = []
            for item in col.items.order_by("order"):
                perm = item.permission
                if perm:
                    try:
                        if not user.has_perm(perm):
                            continue
                    except Exception:
                        continue
                items.append({"name": item.name, "url": item.url})
            if items:
                cols.append({"heading": col.heading, "items": items})
        if cols:
            result.append({"name": menu.name, "icon": menu.icon, "color": menu.color, "columns": cols})
    return result


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

    return json.dumps(data)
