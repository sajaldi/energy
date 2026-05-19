import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

from seguridad.models import PeligroCatalogo, MedidaControlCatalogo

peligros = [
    ('Arco Eléctrico', 'Contacto directo o indirecto con electricidad', 'ELECTRICO'),
    ('Trabajo en Alturas', 'Riesgo de caída a distinto nivel (>1.5m)', 'FISICO'),
    ('Espacios Confinados', 'Atmósfera peligrosa o atrapamiento', 'LOCATIVO'),
    ('Superficies Calientes', 'Riesgo de quemaduras', 'FISICO'),
    ('Carga Suspendida', 'Riesgo de aplastamiento por caída de objetos', 'MECANICO'),
    ('Ruido Intenso', 'Exposición a niveles altos de decibeles', 'FISICO'),
    ('Gases Tóxicos', 'Inhalación de sustancias químicas', 'QUIMICO'),
    ('Posturas Forzadas', 'Riesgo ergonómico por movimientos repetitivos', 'ERGONOMICO'),
]

controles = [
    ('Bloqueo LOTO', 'Bloqueo y etiquetado de fuentes de energía', 'INGENIERIA'),
    ('Uso de EPP Dieléctrico', 'Guantes, botas y careta certificada', 'EPP'),
    ('Línea de Vida / Arnés', 'Protección contra caídas certificada', 'EPP'),
    ('Ventilación Forzada', 'Renovación de aire en espacios cerrados', 'INGENIERIA'),
    ('Señalización de Área', 'Cintas, conos y letreros de advertencia', 'ADMINISTRATIVO'),
    ('Permiso de Trabajo Caliente', 'Autorización específica para soldadura/corte', 'ADMINISTRATIVO'),
    ('Extintor PQS', 'Equipo contra incendios de polvo químico seco', 'ADMINISTRATIVO'),
]

print("Poblando catálogos de seguridad...")

for nombre, desc, cat in peligros:
    PeligroCatalogo.objects.get_or_create(nombre=nombre, defaults={'descripcion': desc, 'categoria': cat})

for nombre, desc, tipo in controles:
    MedidaControlCatalogo.objects.get_or_create(nombre=nombre, defaults={'descripcion': desc, 'tipo': tipo})

print("¡Listo!")
