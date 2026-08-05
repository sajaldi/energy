# Backfill: AdminNavItem.menu a partir de su columna.
# El seed 0032 creó los items solo con 'column'; menus_base()/get_menus_usuario()
# leen por el FK 'menu', por lo que los módulos nuevos no mostraban sub-accesos.

from django.db import migrations


def backfill_menu(apps, schema_editor):
    AdminNavItem = apps.get_model("core", "AdminNavItem")
    for item in AdminNavItem.objects.filter(menu_id__isnull=True, column_id__isnull=False):
        item.menu_id = item.column.menu_id
        item.save(update_fields=["menu"])


def unbackfill_menu(apps, schema_editor):
    AdminNavItem = apps.get_model("core", "AdminNavItem")
    # No deshacemos: se preservan los enlaces para no romper la home.


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0032_seed_home_modulos"),
    ]

    operations = [
        migrations.RunPython(backfill_menu, unbackfill_menu),
    ]
