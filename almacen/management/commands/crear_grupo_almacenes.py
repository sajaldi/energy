from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from inventarios.models import Material, MovimientoInventario


class Command(BaseCommand):
    help = 'Crea el grupo Almacenes y asigna los permisos necesarios'

    def handle(self, *args, **options):
        # 1. Crear el grupo
        group, created = Group.objects.get_or_create(name='Almacenes')
        if created:
            self.stdout.write(self.style.SUCCESS(f'Grupo "{group.name}" creado.'))
        else:
            self.stdout.write(f'Grupo "{group.name}" ya existe.')

        # 2. Obtener permisos para Material
        material_ct = ContentType.objects.get_for_model(Material)
        material_perms = Permission.objects.filter(content_type=material_ct)

        # 3. Obtener permisos para MovimientoInventario
        movimiento_ct = ContentType.objects.get_for_model(MovimientoInventario)
        movimiento_perms = Permission.objects.filter(content_type=movimiento_ct)

        # 4. Asignar permisos al grupo
        # Queremos que puedan ver, añadir y cambiar materiales
        # Y que puedan liquidar movimientos (permiso personalizado)
        for perm in material_perms:
            group.permissions.add(perm)
        
        for perm in movimiento_perms:
            group.permissions.add(perm)

        self.stdout.write(self.style.SUCCESS(f'Permisos asignados al grupo "{group.name}".'))
