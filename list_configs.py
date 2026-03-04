import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

from documentos.models import MetadatoConfig

def list_configs():
    configs = MetadatoConfig.objects.all()
    print(f"Total MetadatoConfig: {configs.count()}")
    for c in configs:
        print(f"ID: {c.id} | Name: {c.nombre} | Type: {c.tipo_campo} | Model: {c.modelo_relativo}")

if __name__ == "__main__":
    list_configs()
