from django.db import migrations


def add_item(apps, schema_editor):
    AdminNavMenu = apps.get_model('core', 'AdminNavMenu')
    AdminNavColumn = apps.get_model('core', 'AdminNavColumn')
    AdminNavItem = apps.get_model('core', 'AdminNavItem')

    inventarios = AdminNavMenu.objects.filter(name="Inventarios").first()
    if not inventarios:
        return

    col = inventarios.columns.order_by('order').first()
    if not col:
        col = AdminNavColumn.objects.create(menu=inventarios, heading="Materiales", order=1)

    if not AdminNavItem.objects.filter(url="/inventarios/listo-recoleccion/").exists():
        AdminNavItem.objects.create(
            column=col,
            menu=inventarios,
            name="Listo para Recolección",
            url="/inventarios/listo-recoleccion/",
            icon="fas fa-cube",
            permission="inventarios.view_solicitudmaterial",
            order=4,
        )


def remove_item(apps, schema_editor):
    AdminNavItem = apps.get_model('core', 'AdminNavItem')
    AdminNavItem.objects.filter(url="/inventarios/listo-recoleccion/").delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0038_perfilusuario_expo_push_token'),
    ]

    operations = [
        migrations.RunPython(add_item, remove_item),
    ]
