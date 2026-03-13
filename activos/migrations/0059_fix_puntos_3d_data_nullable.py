from django.db import migrations


class Migration(migrations.Migration):
    """
    Fix: ALTER puntos_3d_data and related 3D columns in activos_ubicacion 
    to be nullable. These columns were added directly to the DB but the 
    model doesn't declare them, causing NOT NULL constraint violations in 
    sync_tickets_task.
    """

    dependencies = [
        ('activos', '0058_alter_modelo_precio_promedio'),
    ]

    operations = [
        migrations.RunSQL(
            # Forward: make the column nullable if it exists
            sql="""
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name = 'activos_ubicacion' 
                        AND column_name = 'puntos_3d_data'
                    ) THEN
                        ALTER TABLE activos_ubicacion 
                            ALTER COLUMN puntos_3d_data DROP NOT NULL;
                    END IF;
                END;
                $$;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
