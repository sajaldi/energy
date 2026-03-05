
import io
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import connection, transaction, IntegrityError
from django.db.models import Q
from django.urls import reverse
from mantenimiento.models import OrdenTrabajo, Aviso
from inventarios.models import Material, StockRecord, MovimientoInventario, SolicitudMaterial
from activos.models import Activo, VisorPlano
from .models import InterfaceConsumo, Consumo, Medidor, PerfilUsuario
import pandas as pd
import logging
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.utils import timezone # Para fechas conscientes de zona horaria si es necesario
from datetime import datetime, timedelta
import io
import base64
import matplotlib
matplotlib.use('Agg') # Importante: evita que Matplotlib intente usar un backend de GUI
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.cm as cm
import numpy as np
import json

logger = logging.getLogger(__name__)

def landing_page(request):
    """
    Landing page de SoftCom CCG en la ruta principal.
    """
    return render(request, 'core/landing_page.html')

@staff_member_required
def import_excel(request):
    if request.method == 'POST' and request.FILES.get('excel_file'):
        excel_file = request.FILES['excel_file']
        try:
            # --- 1. TRUNCATE staging table (InterfaceConsumo) ---
            # This clears the staging table before loading new data.
            staging_table_name = InterfaceConsumo._meta.db_table
            with transaction.atomic(): # Envolver truncate y carga a staging
                with connection.cursor() as cursor:
                    try:
                        # PostgreSQL specific for resetting identity.
                        # Adjust for other DBs if ID is auto-increment and needs reset.
                        cursor.execute(f"TRUNCATE TABLE {staging_table_name} RESTART IDENTITY;")
                        logger.info(f"Staging table '{staging_table_name}' truncated and identity reset.")
                    except Exception as e_truncate_restart:
                        logger.warning(f"TRUNCATE ... RESTART IDENTITY failed for {staging_table_name}: {e_truncate_restart}. Trying DELETE...")
                        cursor.execute(f"DELETE FROM {staging_table_name};")
                        # For SQLite, if you need to reset auto-increment for a table named 'staging_table_name':
                        # cursor.execute(f"DELETE FROM sqlite_sequence WHERE name='{staging_table_name}';")
                        logger.info(f"Staging table '{staging_table_name}' cleared with DELETE.")

                # --- 2. Load Excel/CSV to DataFrame and Basic Validations ---
                if excel_file.name.endswith('.xlsx'):
                    df = pd.read_excel(excel_file, engine='openpyxl')
                elif excel_file.name.endswith('.xls'):
                    df = pd.read_excel(excel_file, engine='xlrd')
                elif excel_file.name.endswith('.csv'):
                    # Intento de decodificación robusta para CSVs
                    content = excel_file.read()
                    success = False
                    for enc in ['utf-8-sig', 'iso-8859-1', 'windows-1252', 'utf-8']:
                        try:
                            df = pd.read_csv(io.BytesIO(content), encoding=enc, sep=',')
                            success = True
                            break
                        except UnicodeDecodeError:
                            continue
                    
                    if not success:
                        # Fallback forzado
                        df = pd.read_csv(io.BytesIO(content), encoding='utf-8', encoding_errors='ignore', sep=',')
                else:
                    messages.error(request, "Formato de archivo no soportado. Use .xlsx, .xls o .csv.")
                    return redirect('admin:core_consumo_changelist') # Ajusta el redirect a tu vista de lista

                if df.empty:
                    messages.error(request, "El archivo está vacío.")
                    return redirect('admin:core_consumo_changelist')

                required_columns = ['fecha', 'consumo', 'medidor'] # Nombres de columnas en Excel/CSV
                missing_columns = [col for col in required_columns if col not in df.columns]
                if missing_columns:
                    messages.error(request, f"Columnas faltantes en el archivo: {', '.join(missing_columns)}. Se requieren: {', '.join(required_columns)}")
                    return redirect('admin:core_consumo_changelist')

                # --- 3. Date Parsing and Validation (Output: datetime objects) ---
                try:
                    # Intenta varios formatos, el resultado debe ser datetime objects
                    parsed_dates = pd.to_datetime(df['fecha'], format='%d/%m/%Y %H:%M', errors='coerce')
                    if parsed_dates.isnull().any():
                        failed_indices_1 = parsed_dates[parsed_dates.isnull()].index
                        parsed_dates_fallback_1 = pd.to_datetime(df.loc[failed_indices_1, 'fecha'], format='%d/%m/%Y %H', errors='coerce')
                        parsed_dates.loc[failed_indices_1] = parsed_dates.loc[failed_indices_1].fillna(parsed_dates_fallback_1)
                    if parsed_dates.isnull().any():
                        failed_indices_2 = parsed_dates[parsed_dates.isnull()].index
                        parsed_dates_fallback_2 = pd.to_datetime(df.loc[failed_indices_2, 'fecha'], format='%d/%m/%Y', errors='coerce')
                        parsed_dates.loc[failed_indices_2] = parsed_dates.loc[failed_indices_2].fillna(parsed_dates_fallback_2)
                    if parsed_dates.isnull().any():
                        failed_indices_3 = parsed_dates[parsed_dates.isnull()].index
                        parsed_dates_fallback_3 = pd.to_datetime(df.loc[failed_indices_3, 'fecha'], infer_datetime_format=True, errors='coerce')
                        parsed_dates.loc[failed_indices_3] = parsed_dates.loc[failed_indices_3].fillna(parsed_dates_fallback_3)

                    if parsed_dates.isnull().any():
                        problem_indices = parsed_dates[parsed_dates.isnull()].index.tolist()
                        example_problems = df.loc[problem_indices, 'fecha'].astype(str).head(5).tolist()
                        messages.error(request, (
                            f"Error en el formato de fecha para algunas filas. "
                            f"Se intentó con DD/MM/YYYY HH:MM, DD/MM/YYYY HH, DD/MM/YYYY y formatos genéricos. "
                            f"Ejemplos de valores problemáticos en la columna 'fecha': {', '.join(example_problems)}. "
                            "Por favor, corrija el archivo."
                        ))
                        return redirect('admin:core_consumo_changelist')

                    # Almacenar objetos datetime. Si USE_TZ=True, considera hacerlos conscientes.
                    # Por ahora, asumimos que Django los manejará como naive y los convertirá si es necesario.
                    df['fecha_for_db'] = parsed_dates # Ahora es una serie de datetimes

                except KeyError:
                    messages.error(request, "La columna 'fecha' no se encontró en el archivo.")
                    return redirect('admin:core_consumo_changelist')
                except Exception as e:
                    logger.error(f"Error inesperado procesando la columna 'fecha': {e}", exc_info=True)
                    messages.error(request, f'Error inesperado procesando la columna "fecha": {str(e)}')
                    return redirect('admin:core_consumo_changelist')

                # --- 4. Prepare and Bulk Insert into InterfaceConsumo (Staging Table) ---
                interface_records_to_create = []
                skipped_rows_validation_errors = []

                for index, row in df.iterrows():
                    try:
                        # row['fecha_for_db'] es ahora un objeto datetime de Pandas (Timestamp)
                        # o NaT si falló la conversión.
                        fecha_dt_obj = row['fecha_for_db']

                        if pd.isna(fecha_dt_obj):
                            skipped_rows_validation_errors.append(f"Fila {index + 2}: Fecha '{row['fecha']}' no pudo ser procesada a datetime.")
                            continue

                        # Convertir Pandas Timestamp a Python datetime si es necesario para el ORM,
                        # aunque Django suele manejar Timestamps bien.
                        # Si InterfaceConsumo.fecha es DateTimeField, esto es correcto.
                        # Si InterfaceConsumo.fecha fuera DateField, usarías: fecha_dt_obj.date()
                        python_datetime = fecha_dt_obj.to_pydatetime()


                        try:
                            consumo_valor = float(row['consumo'])
                        except ValueError:
                            skipped_rows_validation_errors.append(f"Fila {index + 2}: Valor de 'consumo' ('{row['consumo']}') no es un número válido.")
                            continue

                        # --- Handling Medidor Name from File ---
                        medidor_nombre_from_file_raw = row.get('medidor')
                        if pd.isna(medidor_nombre_from_file_raw) or not str(medidor_nombre_from_file_raw).strip():
                            skipped_rows_validation_errors.append(f"Fila {index + 2}: Nombre de medidor (columna 'medidor') vacío o ausente.")
                            continue
                        # Clean the medidor name - this should be the full string
                        medidor_nombre_cleaned = str(medidor_nombre_from_file_raw).strip()
                        # --- End Handling Medidor Name ---

                        interface_records_to_create.append(InterfaceConsumo(
                            fecha=python_datetime, # Usar el datetime completo
                            consumo=consumo_valor,
                            medidor=medidor_nombre_cleaned # Storing the cleaned, full name in staging
                        ))
                    except KeyError as e:
                        skipped_rows_validation_errors.append(f"Fila {index + 2}: Columna faltante '{e}' al preparar para staging.")
                    except Exception as e:
                        logger.error(f"Error preparando fila {index + 2} para staging: {e}", exc_info=True)
                        skipped_rows_validation_errors.append(f"Fila {index + 2}: Error inesperado '{str(e)}' al preparar para staging.")

                if not interface_records_to_create:
                    if skipped_rows_validation_errors:
                        error_summary = "; ".join(skipped_rows_validation_errors[:3]) + ("..." if len(skipped_rows_validation_errors) > 3 else "")
                        messages.warning(request, f"Ninguna fila válida para staging. {len(skipped_rows_validation_errors)} filas del archivo con errores: {error_summary}")
                    else:
                        messages.error(request, "El archivo no contiene registros válidos para cargar en la tabla de staging.")
                    return redirect('admin:core_consumo_changelist')

                # InterfaceConsumo tiene unique_together = ['fecha', 'medidor']
                # Usar ignore_conflicts=True para evitar errores si el archivo tiene duplicados exactos
                # que coincidan con esta restricción de la tabla de staging.
                # This bulk_create should save the full 'medidor_nombre_cleaned' strings.
                InterfaceConsumo.objects.bulk_create(interface_records_to_create, ignore_conflicts=True)
                # Nota: ignore_conflicts=True no devuelve IDs, y el número de creados podría ser menor
                # si hubo conflictos. Para un conteo exacto, necesitarías consultar la tabla.
                # Por simplicidad, asumimos que la mayoría o todos se cargan.
                actual_staged_count = InterfaceConsumo.objects.count() # Contar después para saber cuántos hay realmente
                logger.info(f"{len(interface_records_to_create)} records intentados para staging. {actual_staged_count} records ahora en staging '{staging_table_name}'.")
            # Fin del transaction.atomic() para staging

            # --- 5. Process from InterfaceConsumo to Consumo ---
            staged_records = InterfaceConsumo.objects.all() # Fetching records from staging

            if not staged_records.exists():
                 messages.info(request, "No hay registros en la tabla de staging para procesar (posiblemente todos eran duplicados dentro del archivo).")
                 return redirect('admin:core_consumo_changelist')

            # --- Extracting Medidor Names from Staging ---
            # This set should contain the full medidor names as stored in InterfaceConsumo
            medidor_names_from_staging = set(s.medidor for s in staged_records if s.medidor)
            # --- End Extracting Medidor Names ---

            if not medidor_names_from_staging:
                messages.error(request, "No se encontraron nombres de medidores válidos en los datos de staging.")
                return redirect('admin:core_consumo_changelist')

            # Fetch existing Medidor objects by their name
            existing_medidores_dict = {m.nombre: m for m in Medidor.objects.filter(nombre__in=medidor_names_from_staging)}

            # --- MODIFICACIÓN: No crear nuevos medidores si no existen ---
            # Comentamos o eliminamos la lógica de creación de nuevos medidores
            # medidores_to_create_names = list(medidor_names_from_staging - set(existing_medidores_dict.keys()))
            # if medidores_to_create_names:
            #     new_medidores_objs = [Medidor(nombre=name, tipo='IMPORTADO_EXCEL') for name in medidores_to_create_names]
            #     try:
            #         Medidor.objects.bulk_create(new_medidores_objs, ignore_conflicts=True)
            #         logger.info(f"Intentada creación masiva de {len(new_medidores_objs)} nuevos medidores.")
            #         for med_obj in Medidor.objects.filter(nombre__in=medidores_to_create_names):
            #              if med_obj.nombre not in existing_medidores_dict:
            #                   existing_medidores_dict[med_obj.nombre] = med_obj
            #     except IntegrityError as ie:
            #         logger.error(f"Error de integridad al crear medidores: {ie}", exc_info=True)
            #         messages.error(request, f"Error al crear nuevos medidores: {str(ie)}")
            #         return redirect('admin:core_consumo_changelist')
            # --- FIN MODIFICACIÓN ---

            consumo_records_to_create_candidates = []
            skipped_by_python_duplicate_check = 0
            errors_processing_staging = []
            skipped_medidor_not_found = [] # Lista para notificar medidores no encontrados

            # Consumo.fecha es DateTimeField, Consumo.medidor es ForeignKey
            # Crear un set de tuplas (datetime, medidor_id) para chequeo de duplicados
            # Fetching existing Consumo records to check for duplicates before inserting
            existing_consumo_tuples = set(
                (c.fecha, c.medidor_id) for c in Consumo.objects.filter(
                    medidor__nombre__in=medidor_names_from_staging # Efficient filter using names found in staging
                ).only('fecha', 'medidor_id')
            )

            with transaction.atomic(): # Transacción para la carga a la tabla Consumo
                for stag_rec in staged_records: # stag_rec.fecha es datetime
                    # --- Linking Staging Record to Medidor Object ---
                    # Using the full medidor name from the staging record to find the Medidor object
                    medidor_obj = existing_medidores_dict.get(stag_rec.medidor) # stag_rec.medidor is the full name
                    # --- End Linking ---

                    # --- MODIFICACIÓN: Omitir si el medidor no se encuentra ---
                    if not medidor_obj or not medidor_obj.id:
                        error_msg = f"Medidor '{stag_rec.medidor}' (fecha: {stag_rec.fecha.strftime('%Y-%m-%d %H:%M') if stag_rec.fecha else 'N/A'}) no encontrado en la base de datos. Registro omitido."
                        skipped_medidor_not_found.append(error_msg) # Añadir a la lista de omitidos por medidor no encontrado
                        logger.warning(error_msg)
                        continue # Omitir este registro
                    # --- FIN MODIFICACIÓN ---

                    # stag_rec.fecha ya es un objeto datetime (si InterfaceConsumo.fecha es DateTimeField)
                    # Si InterfaceConsumo.fecha es DateField, stag_rec.fecha es date.
                    # En ese caso, Consumo.fecha (DateTimeField) tomaría la hora 00:00:00.
                    # Asumiendo que stag_rec.fecha es datetime:
                    current_consumo_tuple = (stag_rec.fecha, medidor_obj.id)

                    if current_consumo_tuple not in existing_consumo_tuples:
                        consumo_records_to_create_candidates.append(Consumo(
                            fecha=stag_rec.fecha, # stag_rec.fecha is the datetime
                            consumo=stag_rec.consumo,
                            medidor=medidor_obj # Linking to the correct Medidor object (with full name)
                        ))
                    else:
                        skipped_by_python_duplicate_check += 1

                final_imported_count_candidates = len(consumo_records_to_create_candidates)
                if consumo_records_to_create_candidates:
                    try:
                        # Consumo.Meta.unique_together = [['fecha', 'medidor']]
                        # ignore_conflicts=True hace que la BD maneje los duplicados silenciosamente
                        # This bulk_create inserts Consumo records linked to the Medidor objects.
                        Consumo.objects.bulk_create(consumo_records_to_create_candidates, ignore_conflicts=True)
                    except IntegrityError as e: # No debería ocurrir con ignore_conflicts=True y unique_together
                        logger.error(f"IntegrityError durante bulk_create final en Consumo (inesperado con ignore_conflicts): {e}", exc_info=True)
                        messages.error(request, f"Error de base de datos al guardar consumos finales: {str(e)}")
                        return redirect('admin:core_consumo_changelist')

            # --- Mensajes consolidados ---
            total_rows_in_file = len(df)
            initial_staged_intent_count = len(interface_records_to_create) # Los que pasaron validación de fila

            if initial_staged_intent_count > 0:
                 messages.success(request, f'{initial_staged_intent_count} registros del archivo pasaron la validación inicial y se intentaron cargar a staging. {actual_staged_count} registros están ahora en staging.')
            if skipped_rows_validation_errors:
                 error_summary_validation = "; ".join(skipped_rows_validation_errors[:3]) + ("..." if len(skipped_rows_validation_errors) > 3 else "")
                 messages.warning(request, f'{len(skipped_rows_validation_errors)} de {total_rows_in_file} filas del archivo fueron omitidas por errores de validación antes del staging. Ejemplos: {error_summary_validation}')

            if final_imported_count_candidates > 0:
                # Este es el número de registros que pasaron el chequeo de duplicados de Python y se enviaron a la BD.
                # El número real insertado podría ser menor si ignore_conflicts actuó sobre duplicados no detectados por Python.
                messages.success(request, f'{final_imported_count_candidates} registros de staging fueron preparados para importación a la tabla principal (Consumo).')
            elif actual_staged_count > 0 and not errors_processing_staging and not skipped_medidor_not_found and skipped_by_python_duplicate_check == actual_staged_count:
                 messages.info(request, 'No se prepararon nuevos registros para la tabla principal: todos los registros válidos de staging ya existían (según chequeo).')
            elif actual_staged_count > 0:
                 messages.info(request, 'No se prepararon nuevos registros para la tabla principal (verifique duplicados, errores de procesamiento desde staging y medidores no encontrados).')


            if skipped_by_python_duplicate_check > 0:
                messages.info(request, f'{skipped_by_python_duplicate_check} registros de staging fueron identificados como duplicados (según chequeo Python) y no se intentaron cargar a la tabla principal.')

            # --- MODIFICACIÓN: Mensaje para medidores no encontrados ---
            if skipped_medidor_not_found:
                error_summary_medidor = "; ".join(skipped_medidor_not_found[:3]) + ("..." if len(skipped_medidor_not_found) > 3 else "")
                messages.warning(request, f"{len(skipped_medidor_not_found)} registros fueron omitidos porque el medidor asociado no existe en la base de datos. Ejemplos: {error_summary_medidor}")
            # --- FIN MODIFICACIÓN ---

            if errors_processing_staging:
                error_summary_staging = "; ".join(errors_processing_staging[:3]) + ("..." if len(errors_processing_staging) > 3 else "")
                messages.warning(request, f"{len(errors_processing_staging)} errores ocurrieron al procesar registros desde staging hacia Consumo. Ejemplos: {error_summary_staging}")

            # Opcional: Limpiar InterfaceConsumo después del procesamiento.
            # Comenta esto si quieres revisar InterfaceConsumo después de la importación.
            # InterfaceConsumo.objects.all().delete()
            # logger.info(f"Staging table '{staging_table_name}' cleared after processing.")

            return redirect('admin:core_consumo_changelist') # Ajusta a tu vista

        except pd.errors.EmptyDataError:
            messages.error(request, "El archivo Excel/CSV está vacío o no contiene datos legibles.")
            logger.warning("Pandas EmptyDataError durante importación.", exc_info=True)
            return redirect('admin:core_consumo_changelist')
        except IntegrityError as e_outer: # Por ejemplo, si el TRUNCATE falla dentro de la transacción
            logger.error(f"Error de integridad general durante la importación: {e_outer}", exc_info=True)
            messages.error(request, f'Error de base de datos durante la importación: {str(e_outer)}')
            return redirect('admin:core_consumo_changelist')
        except Exception as e:
            logger.error(f"Error general durante la importación del archivo Excel/CSV: {e}", exc_info=True)
            messages.error(request, f'Error crítico al importar datos: {str(e)}')
            return redirect('admin:core_consumo_changelist')

    return render(request, 'admin/import_excel.html') # Asegúrate que tu template de importación existe




# --- NUEVA VISTA PARA EL REPORTE DE CONSUMO ---
@staff_member_required
# core/views.py

# ... (tus importaciones existentes, asegúrate de que 'json' esté)
# ...

@staff_member_required

# ==============================================================================
# VISTA 1: REPORTE MENSUAL (VERSIÓN CON print() PARA DEPURACIÓN)
# ==============================================================================
@staff_member_required
def reporte_consumo_mensual(request):
    # ==============================================================================
    # PRINT DE ARRANQUE: Este tiene que aparecer siempre que se carga la página.
    # ==============================================================================
    print("\n[INFO] La función 'reporte_consumo_mensual' ha sido llamada.", flush=True)

    medidores = Medidor.objects.all().order_by('nombre')
    context = { 'medidores': medidores, 'report_results': None, 'selected_medidores': [], 'start_date_str': '', 'end_date_str': '' }

    if request.method == 'POST':
        print("[INFO] La petición es de tipo POST.", flush=True)

        selected_ids_str = request.POST.getlist('medidores')
        start_date_str = request.POST.get('start_date')
        end_date_str = request.POST.get('end_date')

        context.update({'selected_medidores': selected_ids_str, 'start_date_str': start_date_str, 'end_date_str': end_date_str})

        if not all([selected_ids_str, start_date_str, end_date_str]):
             messages.error(request, "Debes seleccionar al menos un medidor y un rango de fechas.")
             return render(request, 'admin/reporte_consumo.html', context)
        
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        except (ValueError, TypeError):
             messages.error(request, "Formato de fechas inválido.")
             return render(request, 'admin/reporte_consumo.html', context)
        
        report_results = []
        selected_ids = [int(id_str) for id_str in selected_ids_str]
        
        for medidor_id in selected_ids:
            try:
                medidor_obj = Medidor.objects.select_related('unidad').get(pk=medidor_id)
                unidad_simbolo = "unidades"
                if medidor_obj.unidad and medidor_obj.unidad.simbolo:
                    unidad_simbolo = medidor_obj.unidad.simbolo

                tipo_bruto_db = medidor_obj.tipo
                tipo_normalizado = (tipo_bruto_db or "").strip().upper()

                # !!====================================================================!!
                # !! PASO DE DEPURACIÓN CRÍTICO: Usar print() con flush=True            !!
                # !!====================================================================!!
                print("\n#<===================[ INICIO DEBUG MEDIDOR ]===================>#", flush=True)
                print(f"#<== ID: {medidor_id} | Nombre: {medidor_obj.nombre}", flush=True)
                print(f"#<== Valor 'tipo' en BD: '{tipo_bruto_db}' (Tipo Python: {type(tipo_bruto_db)})", flush=True)
                print(f"#<== Valor 'tipo' Normalizado: '{tipo_normalizado}'", flush=True)
                
                query_mensual = ""
                if tipo_normalizado == 'PUNTUAL':
                    print("#<== DECISIÓN: Lógica para 'PUNTUAL' (SUMA).", flush=True)
                    query_mensual = f"""
                        SELECT TO_CHAR(fecha, 'YYYY-MM') AS mes, SUM(consumo) AS consumo_mensual
                        FROM core_consumo WHERE medidor_id = {medidor_id} AND fecha >= '{start_date.strftime('%Y-%m-%d')}' AND fecha < '{end_date.strftime('%Y-%m-%d')}'
                        GROUP BY TO_CHAR(fecha, 'YYYY-MM') HAVING SUM(consumo) IS NOT NULL ORDER BY mes;
                    """
                else:
                    print("#<== DECISIÓN: Lógica para 'ACUMULADO/OTRO' (RESTA).", flush=True)
                    query_mensual = f"""
                        SELECT mes, (consumo_actual - consumo_anterior) AS consumo_mensual FROM (
                            SELECT TO_CHAR(fecha_final_mes, 'YYYY-MM') AS mes, consumo_final_mes AS consumo_actual,
                                   LAG(consumo_final_mes) OVER (PARTITION BY medidor_id ORDER BY fecha_final_mes) AS consumo_anterior
                            FROM (
                                SELECT medidor_id, MAX(fecha) AS fecha_final_mes,
                                       (SELECT consumo FROM core_consumo WHERE medidor_id = c.medidor_id AND fecha = MAX(c.fecha)) AS consumo_final_mes
                                FROM core_consumo c WHERE fecha >= '{start_date.strftime('%Y-%m-%d')}' AND fecha < '{end_date.strftime('%Y-%m-%d')}' AND medidor_id = {medidor_id}
                                GROUP BY medidor_id, TO_CHAR(fecha, 'YYYY-MM')
                            ) AS lecturas
                        ) AS calculo WHERE consumo_anterior IS NOT NULL ORDER BY mes;
                    """
                print("#<====================[ FIN DEBUG MEDIDOR ]=====================>#\n", flush=True)

                df_mensual = pd.read_sql(query_mensual, connection)

                if df_mensual.empty: continue

                # (El resto del código para generar el gráfico, tabla, etc. se mantiene igual)
                df_mensual['mes_ordinal'] = pd.to_datetime(df_mensual['mes'])
                df_mensual = df_mensual.sort_values('mes_ordinal')
                fig, ax = plt.subplots(figsize=(12, 6))
                bars = ax.bar(df_mensual['mes'], df_mensual['consumo_mensual'], label=f'Consumo Mensual ({unidad_simbolo})')
                ax.bar_label(bars, fmt=lambda x: f'{x:,.0f} {unidad_simbolo}'.replace(',', '.'), padding=3, color='white', fontsize=11, bbox=dict(facecolor='#003366', edgecolor='none', boxstyle='round,pad=0.4'))
                max_height = df_mensual['consumo_mensual'].max()
                if max_height > 0: ax.set_ylim(top=max_height * 1.20)
                ax.set_ylabel(f'Consumo ({unidad_simbolo})')
                ax.set_title(f"Consumo Mensual - {medidor_obj.nombre}")
                ax.legend()
                ax.grid(True, which='both', linestyle='--', linewidth=0.5)
                fig.autofmt_xdate(rotation=45, ha='right')
                plt.tight_layout()
                buf = io.BytesIO()
                plt.savefig(buf, format='png')
                img_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
                plt.close(fig)

                links_html = '<div><strong>Ver detalle diario por mes:</strong></div><p>'
                links = []
                for mes in df_mensual['mes']:
                    url = reverse('core:reporte_detalle_diario_ajax', args=[medidor_id, mes])
                    links.append(f'<a href="{url}" class="btn btn-outline-primary btn-sm m-1 daily-detail-link">{mes}</a>')
                links_html += ' '.join(links) + '</p>'

                medidor_result = { 'name': medidor_obj.nombre, 'id': medidor_id, 'chart_b64': img_base64, 'links_html': links_html, 'table_data': df_mensual.to_dict('records'), 'unidad_simbolo': unidad_simbolo }
                report_results.append(medidor_result)

            except Exception as e:
                logging.error(f"Error procesando medidor {medidor_id}: {e}", exc_info=True)
                messages.warning(request, f"Ocurrió un error al procesar el medidor ID {medidor_id}.")

        context['report_results'] = report_results
    return render(request, 'admin/reporte_consumo.html', context)

@staff_member_required
def reporte_consumo_diario(request, medidor_id, mes_str):
    try:
        medidor = Medidor.objects.select_related('unidad').get(pk=medidor_id)
        datetime.strptime(mes_str, '%Y-%m')
    except (Medidor.DoesNotExist, ValueError):
        return HttpResponseBadRequest("Parámetros inválidos.", status=400)

    unidad_simbolo = "unidades"
    if medidor.unidad and medidor.unidad.simbolo:
        unidad_simbolo = medidor.unidad.simbolo

    tipo_medidor_normalizado = (medidor.tipo or "").strip().upper()
    logging.info(f"DEBUG DIARIO: Medidor ID: {medidor_id}, Tipo Normalizado: '{tipo_medidor_normalizado}'")
    
    query_diario = ""
    if tipo_medidor_normalizado == 'PUNTUAL':
        logging.info(f"==> (DIARIO) Medidor {medidor_id} es PUNTUAL. Usando SUM().")
        query_diario = f"""
            SELECT TO_CHAR(fecha, 'YYYY-MM-DD') AS dia, SUM(consumo) AS consumo_diario
            FROM core_consumo WHERE medidor_id = {medidor_id} AND TO_CHAR(fecha, 'YYYY-MM') = '{mes_str}'
            GROUP BY DATE(fecha) HAVING SUM(consumo) IS NOT NULL ORDER BY dia;
        """
    else:
        logging.info(f"==> (DIARIO) Medidor {medidor_id} es ACUMULADO/OTRO. Usando LAG().")
        query_diario = f"""
            SELECT TO_CHAR(dia, 'YYYY-MM-DD') AS dia, (lectura_dia - COALESCE(lectura_anterior, lectura_dia)) as consumo_diario FROM (
                SELECT dia, lectura_dia, LAG(lectura_dia, 1) OVER (ORDER BY dia) as lectura_anterior FROM (
                    SELECT DATE(fecha) as dia, MAX(consumo) as lectura_dia FROM core_consumo
                    WHERE medidor_id = {medidor_id} AND TO_CHAR(fecha, 'YYYY-MM') = '{mes_str}'
                    GROUP BY DATE(fecha)
                ) as lecturas_diarias
            ) as calculo_diario WHERE (lectura_dia - COALESCE(lectura_anterior, lectura_dia)) >= 0 ORDER BY dia;
        """

    df_diario = pd.read_sql(query_diario, connection)

    if df_diario.empty:
        return HttpResponse(f"<div class='alert alert-info'>No se encontraron datos de consumo diario para '{medidor.nombre}' en {mes_str}.</div>")
    
    df_diario['dia_dt'] = pd.to_datetime(df_diario['dia'])
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(df_diario['dia_dt'], df_diario['consumo_diario'], marker='o', linestyle='-', label=f'Consumo Diario ({unidad_simbolo})')
    ax.set_ylabel(f'Consumo ({unidad_simbolo})')
    ax.set_title(f"Detalle de Consumo Diario - {medidor.nombre} ({mes_str})")
    ax.legend()
    ax.grid(True, which='both', linestyle='--', linewidth=0.5)
    fig.autofmt_xdate(rotation=45, ha='right')
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    img_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    plt.close(fig)

    html_response = f'<img src="data:image/png;base64,{img_base64}" class="img-fluid" alt="Gráfico de consumo diario">'
    return HttpResponse(html_response)


@staff_member_required
def finalizar_tutorial(request):
    if request.method == 'POST':
        perfil, created = PerfilUsuario.objects.get_or_create(usuario=request.user)
        perfil.visto_tutorial = True
        perfil.save()
        return json_response({'status': 'ok'})
    return HttpResponseBadRequest("Método no permitido")

def json_response(data):
    return HttpResponse(json.dumps(data), content_type="application/json")



@login_required
def mobile_dashboard(request):
    """
    Dashboard optimizado para dispositivos móviles.
    """
    today = timezone.now().date()
    
    # OTs del día
    ots_hoy = OrdenTrabajo.objects.filter(
        inicio_programado__date=today
    ).exclude(estado='REALIZADA').select_related('rutina', 'ubicacion').order_by('inicio_programado')
    
    # OTs próximas (Siguientes 7 días)
    tomorrow = today + timedelta(days=1)
    next_week = today + timedelta(days=8)
    ots_proximas = OrdenTrabajo.objects.filter(
        inicio_programado__date__range=[tomorrow, next_week]
    ).exclude(estado='REALIZADA').select_related('rutina', 'ubicacion').order_by('inicio_programado')

    # Si el usuario es técnico, filtrar por sus tareas (directas o por equipo)
    if not request.user.is_superuser:
        user_groups = request.user.groups.all()
        ots_hoy = ots_hoy.filter(
            Q(tecnico=request.user) | Q(equipo__in=user_groups)
        ).distinct()
        ots_proximas = ots_proximas.filter(
            Q(tecnico=request.user) | Q(equipo__in=user_groups)
        ).distinct()

    # Aplicar el recorte de seguridad al final para evitar crashes de memoria en móvil
    ots_hoy = ots_hoy[:10]
    ots_proximas = ots_proximas[:10]

    # Estadísticas rápidas
    total_activos = Activo.objects.count()
    avisos_abiertos = Aviso.objects.filter(estado='ABIERTO').count()
    
    # Accesos rápidos a planos
    planos_recientes = VisorPlano.objects.all().order_by('-creado_en')[:3]

    from activos.models.ubicacion import Ubicacion
    ubicaciones_raiz = Ubicacion.objects.filter(padre__isnull=True).order_by('orden', 'nombre')[:4]

    # Pedidos de material (NUEVO)
    pedidos_pendientes_count = SolicitudMaterial.objects.filter(usuario=request.user, estado='PENDIENTE').count()

    context = {
        'ots_hoy': ots_hoy,
        'ots_proximas': ots_proximas,
        'total_activos': total_activos,
        'avisos_abiertos': avisos_abiertos,
        'planos_recientes': planos_recientes,
        'ubicaciones_raiz': ubicaciones_raiz,
        'pedidos_pendientes_count': pedidos_pendientes_count,
        'today': today,
    }
    return render(request, 'core/mobile_dashboard.html', context)


@login_required
def mobile_scanner(request):
    """
    Vista del escáner QR.
    """
    return render(request, 'core/mobile_scanner.html')


@login_required
def qr_resolver(request):
    """
    Resuelve el contenido de un código QR.
    Redirige si es una URL conocida o busca por código de activo.
    """
    code = request.GET.get('code', '').strip()
    if not code:
        return JsonResponse({'success': False, 'error': 'No se recibió ningún código'}, status=400)

    # Caso 1: Es una URL de nuestra propia app (mantenimiento/app/ot/...)
    if '/mantenimiento/app/' in code:
        return JsonResponse({'success': True, 'redirect': code})

    # Caso 2: Es un código interno de un activo
    activo = Activo.objects.filter(codigo_interno__iexact=code).first()
    if activo:
        # Redirigir a la nueva vista móvil del activo
        return JsonResponse({
            'success': True, 
            'redirect': reverse('activos:mobile_activo_detalle', args=[activo.id]),
            'message': f'Equipo encontrado: {activo.nombre}'
        })

    return JsonResponse({'success': False, 'error': 'Código no reconocido en el sistema'}, status=404)
@staff_member_required
def global_search(request):
    """
    Búsqueda unificada en todo el sistema con múltiples modelos y pestañas.
    """
    query = request.GET.get('q', '').strip()
    results = {
        'activos': [],
        'tickets': [],
        'documentos': [],
        'materiales': [],
        'rutinas': [],
        'presupuestos': [],
    }
    
    if query:
        from activos.models.activo import Activo
        from callcenter.models import SolicitudTicket
        from documentos.models import Documento
        from inventarios.models import Material
        from mantenimiento.models import Rutina
        from presupuestos.models import PresupuestoAnual
        
        # 1. Activos
        results['activos'] = Activo.objects.filter(
            Q(nombre__icontains=query) |
            Q(codigo_interno__icontains=query) |
            Q(serie__icontains=query) |
            Q(epc__icontains=query) |
            Q(descripcion__icontains=query)
        ).select_related('ubicacion', 'modelo__marca')[:20]
        
        # 2. Tickets
        results['tickets'] = SolicitudTicket.objects.filter(
            Q(folio__icontains=query) |
            Q(id_solicitud__icontains=query) |
            Q(solicitante__icontains=query) |
            Q(solicitud_descripcion__icontains=query)
        )[:20]

        # 3. Documentos
        results['documentos'] = Documento.objects.filter(
            Q(codigo__icontains=query) |
            Q(titulo__icontains=query) |
            Q(contenido_extraido__icontains=query)
        ).select_related('tipo_documento')[:20]

        # 4. Materiales
        results['materiales'] = Material.objects.filter(
            Q(nombre__icontains=query) |
            Q(descripcion__icontains=query)
        ).select_related('categoria_material', 'unidad_medida')[:20]

        # 5. Rutinas
        results['rutinas'] = Rutina.objects.filter(
            Q(nombre__icontains=query)
        ).select_related('categoria')[:20]

        # 6. Presupuestos
        results['presupuestos'] = PresupuestoAnual.objects.filter(
            Q(nombre__icontains=query) |
            Q(anio__icontains=query)
        )[:20]

    from django.contrib import admin
    total_results = sum(len(v) for v in results.values())
    
    context = {
        'query': query,
        'results': results,
        'total_results': total_results,
        'title': f'Búsqueda Global: {query}',
        **admin.site.each_context(request),
    }
    return render(request, 'admin/global_search_results.html', context)


@login_required
def system_portal(request):
    """
    Menú general del sistema interactivo y visual (Portal).
    """
    from django.contrib import admin
    context = {
        'title': 'Portal del Sistema',
    }
    try:
        context.update(admin.site.each_context(request))
    except Exception:
        pass
        
    return render(request, 'core/system_portal.html', context)


from django.views.decorators.csrf import csrf_exempt
from django.contrib.contenttypes.models import ContentType
from .models import VistaPersonalizada

@login_required
@csrf_exempt
@staff_member_required
def guardar_vista_personalizada(request):
    """Guarda una vista personalizada (URL con filtros) para el admin."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            nombre = data.get('nombre')
            app_label = data.get('app_label')
            model_name = data.get('model_name')
            query_string = data.get('query_string')
            es_publica = data.get('es_publica', False)

            if not all([nombre, app_label, model_name, query_string]):
                return JsonResponse({'status': 'error', 'message': 'Faltan datos requeridos'}, status=400)

            vista, created = VistaPersonalizada.objects.update_or_create(
                usuario=request.user,
                nombre=nombre,
                app_label=app_label,
                model_name=model_name,
                defaults={
                    'query_string': query_string,
                    'es_publica': es_publica
                }
            )

            return JsonResponse({
                'status': 'success', 
                'message': 'Vista guardada correctamente',
                'id': vista.id,
                'created': created
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

@login_required
@csrf_exempt
@staff_member_required
def eliminar_vista_personalizada(request, vista_id):
    """Elimina una vista personalizada."""
    if request.method == 'POST':
        try:
            vista = VistaPersonalizada.objects.get(id=vista_id, usuario=request.user)
            vista.delete()
            return JsonResponse({'status': 'success', 'message': 'Vista eliminada'})
        except VistaPersonalizada.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Vista no encontrada'}, status=404)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

