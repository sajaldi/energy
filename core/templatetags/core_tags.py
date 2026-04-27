from django import template

register = template.Library()

@register.filter(name='dict_get')
def dict_get(dictionary, key):
    """Acceso dinámico a diccionarios en plantillas"""
    if not dictionary:
        return None
    return dictionary.get(key)

@register.filter(name='get_item')
def get_item(dictionary, key):
    return dict_get(dictionary, key)

@register.filter(name='has_group')
def has_group(user, group_name):
    return user.groups.filter(name=group_name).exists()

@register.filter(name='mul')
def multiply(value, arg):
    """Multiplica el valor por el argumento"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0
