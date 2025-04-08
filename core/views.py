from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import connection
from .models import InterfaceConsumo
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
                raise ValueError("Unsupported file format")

            # Convert 'fecha' column to datetime objects and format to 'YYYY-MM-DD'
            try:
                df['fecha'] = pd.to_datetime(df['fecha']).dt.strftime('%Y-%m-%d')
            except ValueError as e:
                messages.error(request, f'Error parsing date format: {str(e)}. Please ensure the "fecha" column is in a recognizable date format.')
                return redirect('admin:core_consumo_changelist')

            # Insert to staging table
            records = [
                InterfaceConsumo(
                    fecha=row['fecha'],
                    consumo=row['consumo'],
                    medidor=row['medidor']
                ) for _, row in df.iterrows()
            ]
            records_to_create = [record.save() for record in records]

            # Transfer to main table
            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO core_consumo (fecha, consumo, medidor)
                    SELECT i.fecha, i.consumo, i.medidor
                    FROM interface_core_consumo i
                    ON CONFLICT (fecha, medidor) DO NOTHING;

                    TRUNCATE TABLE interface_core_consumo;
                """)

            messages.success(request, f'Successfully imported {len(df)} records')
            return redirect('admin:core_consumo_changelist')

        except Exception as e:
            messages.error(request, f'Error importing data: {str(e)}')
            return redirect('admin:core_consumo_changelist')

    return render(request, 'admin/import_excel.html')


def admin_menu(request):
    return render(request, 'admin/menu.html')


