from django import template

register = template.Library()

@register.filter
def div(value, arg):
    try:
        return float(value) / float(arg)
    except (ValueError, ZeroDivisionError, TypeError):
        return 0

@register.filter
def mul(value, arg):
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def sub(value, arg):
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def index(sequence, position):
    try:
        return sequence[position]
    except (IndexError, TypeError):
        return 0

@register.filter
def addstr(arg1, arg2):
    """concaterate arg1 & arg2"""
    return str(arg1) + str(arg2)

@register.filter
def currency(value):
    """Format decimal as currency: 1,234.56"""
    try:
        import locale
        # locale.setlocale(locale.LC_ALL, 'en_US.UTF-8') # Removed to avoid platform issues
        return "{:,.2f}".format(float(value))
    except (ValueError, TypeError):
        return value

@register.filter
def percentage(value):
    """Format decimal as percentage: 50.00%"""
    try:
        return "{:,.2f}%".format(float(value))
    except (ValueError, TypeError):
        return value

from itertools import groupby as _groupby

@register.filter
def group_by_year(periodo_cols):
    """
    Agrupa una lista de (anio, mes, label) por año.
    Retorna [(anio, [col, ...]), ...]
    """
    result = []
    for anio, group in _groupby(periodo_cols, key=lambda x: x[0]):
        result.append((anio, list(group)))
    return result


@register.filter
def col_anio(periodo_cols, col_num):
    """
    Dado el número de columna (1-based), retorna el año correspondiente.
    periodo_cols es una lista de (anio, mes, label).
    """
    try:
        idx = int(col_num) - 1
        return periodo_cols[idx][0]
    except (IndexError, TypeError, ValueError):
        return ''


@register.filter
def col_mes(periodo_cols, col_num):
    """
    Dado el número de columna (1-based), retorna el mes correspondiente.
    periodo_cols es una lista de (anio, mes, label).
    """
    try:
        idx = int(col_num) - 1
        return periodo_cols[idx][1]
    except (IndexError, TypeError, ValueError):
        return ''
