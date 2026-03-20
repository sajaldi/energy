import os
import sys

from django.template.loader import render_to_string
from mantenimiento.models import OrdenTrabajo

ot = OrdenTrabajo.objects.get(id=20961)
context = {'ot': ot}
html = render_to_string('mantenimiento/mobile_ot_detalle.html', context)

with open(r'd:\Apps\energia\energy\test_render.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("HTML guardado exitosamente en test_render.html")
