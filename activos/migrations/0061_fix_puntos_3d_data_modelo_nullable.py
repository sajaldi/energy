from django.db import migrations


class Migration(migrations.Migration):
    """
    Fix: ALTER puntos_3d_data in activos_modelo to be nullable.
    This column was added directly to the DB but the model doesn't declare it,
    causing NOT NULL constraint violations during asset import (bulk_create).
    """

    dependencies = [
        ('activos', '0060_reindex_tables'),
    ]

    operations = [
        migrations.RunSQL(
            # Forward: make the column nullable if it exists in activos_modelo
            sql="""
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name = 'activos_modelo' 
                        AND column_name = 'puntos_3d_data'
                    ) THEN
                        ALTER TABLE activos_modelo 
                            ALTER COLUMN puntos_3d_data DROP NOT NULL;
                    END IF;
                END;
                $$;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
