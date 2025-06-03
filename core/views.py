from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import connection
from .models import InterfaceConsumo, Consumo, Medidor
import pandas as pd

def import_excel(request):
    if request.method == 'POST' and request.FILES.get('excel_file'):
        try:
            # Clear staging table
            with connection.cursor() as cursor:
                cursor.execute("TRUNCATE TABLE interface_core_consumo;")

            # Load Excel to DataFrame
            excel_file = request.FILES['excel_file']

            # Determine file type
            if excel_file.name.endswith('.xlsx') or excel_file.name.endswith('.xls'):
                df = pd.read_excel(excel_file)
            elif excel_file.name.endswith('.csv'):
                df = pd.read_csv(excel_file, encoding='utf-8', sep=';')
            else:
                raise ValueError("Formato de archivo no soportado")

            # Convert 'fecha' column to datetime objects and format to 'YYYY-MM-DD'
            try:
                df['fecha'] = pd.to_datetime(df['fecha']).dt.strftime('%Y-%m-%d')
            except ValueError as e:
                messages.error(request, f'Error en el formato de fecha: {str(e)}. Por favor asegúrese que la columna "fecha" tenga un formato de fecha válido.')
                return redirect('admin:core_consumo_changelist')

            # Insert to staging table
            records = []
            for _, row in df.iterrows():
                # Buscar o crear el medidor
                medidor_nombre = str(row['medidor']).strip()
                medidor, _ = Medidor.objects.get_or_create(
                    nombre=medidor_nombre,
                    defaults={'tipo': 'GENERICO'}
                )
                
                # Crear el registro de consumo
                consumo = Consumo(
                    fecha=row['fecha'],
                    consumo=float(row['consumo']),
                    medidor=medidor
                )
                records.append(consumo)

            # Guardar todos los registros
            Consumo.objects.bulk_create(records, ignore_conflicts=True)

            messages.success(request, f'Se importaron exitosamente {len(df)} registros')
            return redirect('admin:core_consumo_changelist')

        except Exception as e:
            messages.error(request, f'Error al importar datos: {str(e)}')
            return redirect('admin:core_consumo_changelist')

    return render(request, 'admin/import_excel.html')


def admin_menu(request):
    return render(request, 'admin/menu.html')


