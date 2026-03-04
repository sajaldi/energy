import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

from documentos.models import MetadatoValor

def repair_records():
    print("Repairing MetadatoValor records...")
    # Get relational records with missing content_type
    valores = MetadatoValor.objects.filter(
        config__tipo_campo='RELACION',
        content_type__isnull=True
    )
    
    count = valores.count()
    print(f"Found {count} records to repair.")
    
    repaired = 0
    for v in valores:
        if v.config.modelo_relativo:
            v.content_type = v.config.modelo_relativo
            v.save()
            repaired += 1
            print(f"Repaired ID {v.id}: {v.documento.codigo} -> {v.content_type}")
            
    print(f"Successfully repaired {repaired} records.")

if __name__ == "__main__":
    repair_records()
