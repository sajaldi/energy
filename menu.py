import pandas as pd
from sqlalchemy import create_engine

def list_medidor_numbers():
    # Configura la conexión a PostgreSQL
    engine = create_engine('postgresql://postgres:@localhost:5432/energia')

    # Consulta para obtener todos los números de medidor
    query = "SELECT DISTINCT numero FROM medidor_table"  # Replace 'medidor_table' with your actual table name
    df = pd.read_sql_query(query, engine)

    # Muestra los números de medidor disponibles
    print("Números de Medidor disponibles:")
    print(df['numero'].tolist())

def visualize_data():
    # Lista los números de medidor antes de solicitar el número
    list_medidor_numbers()

    # Define el rango de fechas y el número de medidor
    medidor_numero = input("Ingrese el número de medidor: ")
    start_date = input("Ingrese la fecha de inicio (YYYY-MM-DD): ")
    end_date = input("Ingrese la fecha de fin (YYYY-MM-DD): ")

    # Configura la conexión a PostgreSQL
    engine = create_engine('postgresql://postgres:@localhost:5432/energia')

    # Consulta la tabla y carga los datos en un DataFrame
    query = f"""
    SELECT * FROM consumo_table  # Replace 'consumo_table' with your actual table name
    WHERE medidor = '{medidor_numero}'
    AND fecha BETWEEN '{start_date}' AND '{end_date}'
    """
    df = pd.read_sql_query(query, engine)

    # Muestra los primeros registros
    print(df.head())

    # Opcional: Muestra estadísticas descriptivas
    print(df.describe())

def main_menu():
    while True:
        print("\nMenú Principal")
        print("1. Visualizar datos por Medidor y rango de fechas")
        print("2. Salir")

        choice = input("Seleccione una opción: ")

        if choice == '1':
            visualize_data()
        elif choice == '2':
            print("Saliendo del programa.")
            break
        else:
            print("Opción inválida. Por favor, intente de nuevo.")

if __name__ == "__main__":
    main_menu()