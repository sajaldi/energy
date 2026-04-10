from django import template

register = template.Library()

@register.filter
def dict_get(dictionary, key):
    """Acceso dinámico a diccionarios en plantillas"""
    if not dictionary:
        return None
    return dictionary.get(key)

@register.filter(name='has_group')
def has_group(user, group_name):
    return user.groups.filter(name=group_name).exists()
