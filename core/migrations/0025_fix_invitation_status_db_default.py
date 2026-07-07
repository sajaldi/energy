from django.db import migrations


class Migration(migrations.Migration):
    """
    Fix: Set PostgreSQL-level DEFAULT for invitation_status so any INSERT
    that bypasses Django's ORM default still gets a valid value.
    """

    dependencies = [
        ('core', '0024_add_invitation_status_to_perfilusuario'),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE core_perfilusuario ALTER COLUMN invitation_status SET DEFAULT 'active';",
            reverse_sql="ALTER TABLE core_perfilusuario ALTER COLUMN invitation_status DROP DEFAULT;",
        ),
    ]
