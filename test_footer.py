import os
import django
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "energy.settings")
django.setup()

from django.template.loader import render_to_string
from mantenimiento.models import OrdenTrabajo
import re

ot = OrdenTrabajo.objects.get(id=20961)
html = render_to_string('mantenimiento/mobile_ot_detalle.html', {'ot': ot})

footer = re.search(r'<div class="fiori-footer".*?</div>', html, re.DOTALL)
if footer:
    print("FOOTER HTML:")
    print(footer.group(0))
else:
    print("NO FOOTER FOUND")
