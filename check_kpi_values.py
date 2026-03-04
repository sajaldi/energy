import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

from documentos.models import MetadatoValor, MetadatoConfig

def check_kpi_values():
    config_id = 6
    config = MetadatoConfig.objects.get(id=config_id)
    print(f"Checking values for Config: {config.nombre} (Type: {config.tipo_campo})")
    
    valores = MetadatoValor.objects.filter(config=config)
    print(f"Total values: {valores.count()}")
    
    for v in valores:
        print(f"ID: {v.id} | Doc: {v.documento.codigo} | Valor: '{v.valor}' | CT: {v.content_type_id} | ObjID: {v.object_id}")

if __name__ == "__main__":
    check_kpi_values()
