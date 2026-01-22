import os
from django.core.management.base import BaseCommand
from django.conf import settings
from callcenter.scraper import download_tickets_excel
from callcenter.utils import import_tickets_from_df
import pandas as pd

class Command(BaseCommand):
    help = 'Sincroniza los tickets desde el sitio web SIG GIA automáticamente'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=2, help='Cantidad de días hacia atrás para sincronizar')

    def handle(self, *args, **options):
        days = options['days']
        
        # Estas credenciales deberían estar en variables de entorno o settings por seguridad
        # Por ahora las usamos directamente como solicitó el usuario
        username = os.environ.get('CALLCENTER_USER', 'saul.alvarado')
        password = os.environ.get('CALLCENTER_PASS', '***REMOVED***')
        company = "Centro Cívico Gubernamental de Honduras"
        
        self.stdout.write(f'Iniciando sincronización de los últimos {days} días...')
        
        try:
            # Directorio temporal para descargas
            download_dir = os.path.join(settings.BASE_DIR, 'downloads')
            
            # Ejecutar el scraper
            file_path = download_tickets_excel(
                username=username,
                password=password,
                company_name=company,
                days=days,
                download_dir=download_dir
            )
            
            if not file_path or not os.path.exists(file_path):
                self.stdout.write(self.style.ERROR('No se pudo descargar el archivo de tickets.'))
                return

            self.stdout.write(f'Leyendo archivo descargado: {file_path}')
            df = pd.read_excel(file_path)
            
            creados, actualizados = import_tickets_from_df(df)
            
            self.stdout.write(self.style.SUCCESS(
                f'Sincronización finalizada.\nNuevos: {creados}\nActualizados: {actualizados}'
            ))
            
            # Limpiar archivo temporal
            # os.remove(file_path)
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Ocurrió un error catastrófico durante la sincronización: {e}'))
            import traceback
            self.stdout.write(traceback.format_exc())
