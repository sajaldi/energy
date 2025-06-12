from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import connection, transaction, IntegrityError
from .models import InterfaceConsumo, Consumo, Medidor # Asegúrate que tus modelos están aquí
import pandas as pd
import logging
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone # Para fechas conscientes de zona horaria si es necesario

logger = logging.getLogger(__name__)

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
                    df = pd.read_csv(excel_file, encoding='utf-8', sep=',') # O el separador que uses
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


# Asumiendo que esta es otra vista, también debería estar protegida si es parte del admin
@staff_member_required
def admin_menu(request):
    return render(request, 'admin/')
