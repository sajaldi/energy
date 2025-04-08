import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy import text

# Ruta del archivo Excel
excel_file = 'base.xlsx'

# Lee todas las hojas del archivo, convirtiendo la columna 'TimeStamp' a datetime
sheets = pd.read_excel(excel_file, sheet_name=None, parse_dates=['TimeStamp'])

# Configura la conexión a PostgreSQL
engine = create_engine('postgresql://postgres:@localhost:5432/energia')

# Procesamiento para cada hoja
for sheet_name, df in sheets.items():
    # Print column names to debug
    print(f"Columns in sheet {sheet_name}: {df.columns.tolist()}")
    
    # Eliminar filas donde 'Consumo' está vacío
    df = df.dropna(subset=['Consumo'])

    # Verificar unicidad de 'TimeStamp' y 'MEDIDOR'
    df = df.drop_duplicates(subset=['TimeStamp', 'MEDIDOR'])  

    # Ordenar por TimeStamp
    df = df.sort_values('TimeStamp')
    
    # First, let's check the existing table structure
    with engine.connect() as connection:
        # Create unique constraint if not exists
        connection.execute(text(f"""
            ALTER TABLE {sheet_name} 
            ADD CONSTRAINT unique_timestamp_medidor 
            UNIQUE ("TimeStamp", "MEDIDOR");
        """))
        connection.commit()

    # Subir la tabla a PostgreSQL using the actual column names
    with engine.connect() as connection:
        for index, row in df.iterrows():
            query = text(f"""
            INSERT INTO {sheet_name} ("TimeStamp", "Consumo", "MEDIDOR")
            VALUES (:timestamp, :consumo, :medidor)
            ON CONFLICT ("TimeStamp", "MEDIDOR") DO UPDATE SET
            "Consumo" = EXCLUDED."Consumo";
            """)
            try:
                connection.execute(query, {
                    "timestamp": row['TimeStamp'], 
                    "consumo": row['Consumo'],
                    "medidor": row['MEDIDOR']
                })
                connection.commit()
            except Exception as e:
                print(f"Error inserting row {index}: {e}")
                connection.rollback()

    print(f"Tabla '{sheet_name}' subida correctamente.")

print("Todos los datos se han subido a PostgreSQL.")
