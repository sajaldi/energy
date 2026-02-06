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
