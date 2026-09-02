from django.db import migrations


def add_item(apps, schema_editor):
    AdminNavMenu = apps.get_model('core', 'AdminNavMenu')
    AdminNavColumn = apps.get_model('core', 'AdminNavColumn')
    AdminNavItem = apps.get_model('core', 'AdminNavItem')

    inventarios = AdminNavMenu.objects.filter(name="Inventarios").first()
    if not inventarios:
        return

    # Usar la primera columna del menú Inventarios (o crear una)
    col = inventarios.columns.order_by('order').first()
    if not col:
        col = AdminNavColumn.objects.create(menu=inventarios, heading="Materiales", order=1)

    # Evitar duplicados si la migración se corre más de una vez
    if not AdminNavItem.objects.filter(url="/inventarios/mi-departamento/").exists():
        AdminNavItem.objects.create(
            column=col,
            menu=inventarios,
            name="Mi Departamento",
            url="/inventarios/mi-departamento/",
            icon="fas fa-warehouse",
            permission="inventarios.view_solicitudmaterial",
            order=3,
        )


def remove_item(apps, schema_editor):
    AdminNavItem = apps.get_model('core', 'AdminNavItem')
    AdminNavItem.objects.filter(url="/inventarios/mi-departamento/").delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0036_add_aprobador_salidas_to_perfilusuario'),
    ]

    operations = [
        migrations.RunPython(add_item, remove_item),
    ]
