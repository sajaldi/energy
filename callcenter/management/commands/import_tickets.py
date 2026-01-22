import pandas as pd
from django.core.management.base import BaseCommand
from callcenter.models import SolicitudTicket
from django.utils import timezone
import math

class Command(BaseCommand):
    help = 'Importa tickets desde un archivo Excel local'

    def add_arguments(self, parser):
        parser.add_argument('file_path', type=str, help='Ruta al archivo Excel')

    def handle(self, *args, **options):
        file_path = options['file_path']
        self.stdout.write(f'Leyendo archivo: {file_path}')
        
        try:
            df = pd.read_excel(file_path)
            from callcenter.utils import import_tickets_from_df
            creados, actualizados = import_tickets_from_df(df)
            self.stdout.write(self.style.SUCCESS(
                f'Importación finalizada. Creados: {creados}, Actualizados: {actualizados}'
            ))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error al leer Excel: {e}'))
            return
