import pandas as pd
from sqlalchemy import create_engine

# Configura la conexión a PostgreSQL
engine = create_engine('postgresql://postgres:@localhost:5432/energia')

# Nombre de la tabla que deseas visualizar
table_name = 'consumos'  # Replace with the actual table name

# Consulta la tabla y carga los datos en un DataFrame
df = pd.read_sql_table(table_name, engine)

# Muestra los primeros registros
print(df.head())

# Opcional: Muestra estadísticas descriptivas
print(df.describe())