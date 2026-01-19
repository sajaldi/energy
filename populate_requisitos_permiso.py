# Script para crear requisitos de ejemplo para tipos de permiso
from seguridad.models import TipoPermiso, RequisitoPermiso

# Trabajo en Altura
tipo_altura = TipoPermiso.objects.filter(nombre__icontains='altura').first()
if tipo_altura:
    RequisitoPermiso.objects.get_or_create(
        tipo_permiso=tipo_altura,
        texto='Uso de arnés de seguridad completo con doble línea de vida',
        defaults={'es_critico': True, 'orden': 1}
    )
    RequisitoPermiso.objects.get_or_create(
        tipo_permiso=tipo_altura,
        texto='Inspección visual del equipo anticaídas antes de uso',
        defaults={'es_critico': True, 'orden': 2}
    )
    RequisitoPermiso.objects.get_or_create(
        tipo_permiso=tipo_altura,
        texto='Área de trabajo delimitada y señalizada',
        defaults={'es_critico': True, 'orden': 3}
    )
    RequisitoPermiso.objects.get_or_create(
        tipo_permiso=tipo_altura,
        texto='Puntos de anclaje certificados identificados',
        defaults={'es_critico': True, 'orden': 4}
    )
    RequisitoPermiso.objects.get_or_create(
        tipo_permiso=tipo_altura,
        texto='Personal capacitado en trabajo en alturas',
        defaults={'es_critico': True, 'orden': 5}
    )
    RequisitoPermiso.objects.get_or_create(
        tipo_permiso=tipo_altura,
        texto='Plan de rescate definido y comunicado',
        defaults={'es_critico': True, 'orden': 6}
    )
    RequisitoPermiso.objects.get_or_create(
        tipo_permiso=tipo_altura,
        texto='Condiciones climáticas evaluadas (viento, lluvia)',
        defaults={'es_critico': False, 'orden': 7}
    )
    RequisitoPermiso.objects.get_or_create(
        tipo_permiso=tipo_altura,
        texto='Comunicación establecida con supervisor',
        defaults={'es_critico': False, 'orden': 8}
    )
    print(f"✅ Requisitos creados para: {tipo_altura.nombre}")

# Trabajo en Caliente
tipo_caliente = TipoPermiso.objects.filter(nombre__icontains='caliente').first()
if tipo_caliente:
    RequisitoPermiso.objects.get_or_create(
        tipo_permiso=tipo_caliente,
        texto='Extintor de incendios disponible y accesible',
        defaults={'es_critico': True, 'orden': 1}
    )
    RequisitoPermiso.objects.get_or_create(
        tipo_permiso=tipo_caliente,
        texto='Área libre de materiales inflamables (radio 10m)',
        defaults={'es_critico': True, 'orden': 2}
    )
    RequisitoPermiso.objects.get_or_create(
        tipo_permiso=tipo_caliente,
        texto='Vigía de incendio designado y en posición',
        defaults={'es_critico': True, 'orden': 3}
    )
    RequisitoPermiso.objects.get_or_create(
        tipo_permiso=tipo_caliente,
        texto='Equipo de soldadura/corte en buen estado',
        defaults={'es_critico': True, 'orden': 4}
    )
    RequisitoPermiso.objects.get_or_create(
        tipo_permiso=tipo_caliente,
        texto='Manta ignífuga disponible',
        defaults={'es_critico': False, 'orden': 5}
    )
    RequisitoPermiso.objects.get_or_create(
        tipo_permiso=tipo_caliente,
        texto='Ventilación adecuada verificada',
        defaults={'es_critico': False, 'orden': 6}
    )
    print(f"✅ Requisitos creados para: {tipo_caliente.nombre}")

# Espacio Confinado
tipo_confinado = TipoPermiso.objects.filter(nombre__icontains='confinado').first()
if tipo_confinado:
    RequisitoPermiso.objects.get_or_create(
        tipo_permiso=tipo_confinado,
        texto='Medición de atmósfera (O2, gases tóxicos, explosivos)',
        defaults={'es_critico': True, 'orden': 1}
    )
    RequisitoPermiso.objects.get_or_create(
        tipo_permiso=tipo_confinado,
        texto='Vigía designado fuera del espacio',
        defaults={'es_critico': True, 'orden': 2}
    )
    RequisitoPermiso.objects.get_or_create(
        tipo_permiso=tipo_confinado,
        texto='Equipo de respiración autónomo disponible',
        defaults={'es_critico': True, 'orden': 3}
    )
    RequisitoPermiso.objects.get_or_create(
        tipo_permiso=tipo_confinado,
        texto='Sistema de ventilación forzada operando',
        defaults={'es_critico': True, 'orden': 4}
    )
    RequisitoPermiso.objects.get_or_create(
        tipo_permiso=tipo_confinado,
        texto='Equipo de rescate y arnés preparado',
        defaults={'es_critico': True, 'orden': 5}
    )
    RequisitoPermiso.objects.get_or_create(
        tipo_permiso=tipo_confinado,
        texto='Comunicación continua establecida',
        defaults={'es_critico': True, 'orden': 6}
    )
    print(f"✅ Requisitos creados para: {tipo_confinado.nombre}")

print("\n✅ Script completado. Requisitos de ejemplo agregados a los tipos de permiso.")
