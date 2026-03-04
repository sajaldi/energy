import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

from documentos.models import MetadatoValor, MetadatoConfig
from servicios.models import KPI
from django.contrib.contenttypes.models import ContentType

def check_relations():
    print("Listing all MetadatoValor...")
    valores = MetadatoValor.objects.all()
    print(f"Total MetadatoValor records: {valores.count()}")
    
    for v in valores:
        print(f"ID: {v.id} | Document: {v.documento.codigo} | Config: {v.config.nombre} | Type: {v.config.tipo_campo}")
        print(f"  Valor (text): '{v.valor}'")
        print(f"  Content Type ID: {v.content_type_id}")
        print(f"  Object ID: {v.object_id}")
        print("-" * 20)
        
    kpi_ct = ContentType.objects.get_for_model(KPI)
    print(f"\nKPI ContentType: {kpi_ct} (ID: {kpi_ct.id})")
    
    config_relacion = MetadatoConfig.objects.filter(tipo_campo='RELACION')
    print(f"\nMetadata Configs of type RELACION: {config_relacion.count()}")
    for c in config_relacion:
        print(f"  Config: {c.nombre} | Model: {c.modelo_relativo}")

if __name__ == "__main__":
    check_relations()
