from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(name='escape_script')
def escape_script(value):
    """Escapes </script> tags inside content so it can be safely placed inside a <script type='text/html'> block."""
    if not value:
        return ''
    # Replace </script> with a placeholder that cannot be confused with a closing tag
    escaped = value.replace('</script>', '##ENDSCRIPT##')
    return mark_safe(escaped)
