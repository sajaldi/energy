import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

from documentos.models import MetadatoValor, MetadatoConfig
from servicios.models import KPI
from django.contrib.contenttypes.models import ContentType

def check_relations():
    print("=== RELACION FIELD DIAGNOSTIC ===")
    config_relacion = MetadatoConfig.objects.filter(tipo_campo='RELACION')
    for config in config_relacion:
        print(f"\nConfig Name: {config.nombre}")
        print(f"Target Model: {config.modelo_relativo}")
        
        # Find values for this config
        valores = MetadatoValor.objects.filter(config=config)
        print(f"Total values for this config: {valores.count()}")
        
        for v in valores:
            print(f"  ID: {v.id}")
            print(f"  Documento: {v.documento.codigo}")
            print(f"  Valor (text): '{v.valor}'")
            print(f"  Content Type: {v.content_type} (ID: {v.content_type_id})")
            print(f"  Object ID: {v.object_id}")
            print(f"  Linked Object Found: {v.objeto_vinculado}")
            print("-" * 10)

    kpi_ct = ContentType.objects.get_for_model(KPI)
    print(f"\nKPI ContentType: {kpi_ct} (ID: {kpi_ct.id})")

if __name__ == "__main__":
    check_relations()
