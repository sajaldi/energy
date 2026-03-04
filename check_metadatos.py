import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

from documentos.models import MetadatoValor
from servicios.models import KPI
from django.contrib.contenttypes.models import ContentType

def check_relations():
    print("Checking MetadatoValor relations...")
    # List all MetadatoValor with a bound object
    valores = MetadatoValor.objects.exclude(object_id__isnull=True)
    print(f"Total MetadatoValor with object_id: {valores.count()}")
    
    for v in valores:
        print(f"Document: {v.documento.codigo} | Config: {v.config.nombre}")
        print(f"  Content Type: {v.content_type}")
        print(f"  Object ID: {v.object_id}")
        print(f"  Linked Object: {v.objeto_vinculado}")
        
    kpi_ct = ContentType.objects.get_for_model(KPI)
    print(f"\nKPI ContentType ID: {kpi_ct.id}")
    
    kpi_valores = MetadatoValor.objects.filter(content_type=kpi_ct)
    print(f"MetadatoValor filtered by KPI ContentType: {kpi_valores.count()}")

if __name__ == "__main__":
    check_relations()
