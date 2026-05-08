from django.core.management.base import BaseCommand
from django.apps import apps
from core.dynamics_registry import SYNC_CONFIG
from core.dynamics_sync import sync_instance_to_dynamics
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Realiza un respaldo inicial de todos los datos registrados hacia Dynamics 365.'

    def add_arguments(self, parser):
        parser.add_argument('--model', type=str, help='Especificar un modelo (ej: inventarios.Material)')

    def handle(self, *args, **options):
        target_model = options.get('model')
        
        models_to_process = SYNC_CONFIG.keys()
        if target_model:
            if target_model in SYNC_CONFIG:
                models_to_process = [target_model]
            else:
                self.stderr.write(self.style.ERROR(f"El modelo {target_model} no está registrado en SYNC_CONFIG"))
                return

        for model_name in models_to_process:
            self.stdout.write(f"Procesando respaldo para {model_name}...")
            try:
                model = apps.get_model(model_name)
                instances = model.objects.all()
                total = instances.count()
                
                success_count = 0
                error_count = 0
                
                for i, instance in enumerate(instances, 1):
                    # Sincronizar (esto detectará si ya existe por el dynamics_guid)
                    success = sync_instance_to_dynamics(instance)
                    if success:
                        success_count += 1
                    else:
                        error_count += 1
                    
                    if i % 10 == 0 or i == total:
                        self.stdout.write(f"  Progreso: {i}/{total}...")

                self.stdout.write(self.style.SUCCESS(f"Finalizado {model_name}: {success_count} exitosos, {error_count} errores."))
            
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Error procesando {model_name}: {str(e)}"))

        self.stdout.write(self.style.SUCCESS("Respaldo inicial completado."))
