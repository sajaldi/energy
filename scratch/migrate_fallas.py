import os
import sys
import django

# Setup Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

from callcenter.models import SolicitudTicket, FallaTicket
from django.db import transaction

def migrate_existing_fallas():
    print("Iniciando migración de fallas al catálogo (Versión Rápida)...")
    
    # Obtener todas las descripciones de falla únicas
    fallas_raw = list(SolicitudTicket.objects.exclude(
        falla_descripcion__isnull=True
    ).exclude(
        falla_descripcion=''
    ).values_list('falla_descripcion', flat=True).distinct())
    
    print(f"Encontradas {len(fallas_raw)} descripciones únicas.")
    
    count_created = 0
    mapa_fallas = {} # texto_limpio: objeto_catálogo
    
    with transaction.atomic():
        for f_text in fallas_raw:
            nombre_limpio = f_text.strip().upper()
            if not nombre_limpio:
                continue
                
            falla_obj, created = FallaTicket.objects.get_or_create(nombre=nombre_limpio)
            if created:
                count_created += 1
            mapa_fallas[f_text] = falla_obj
            
        print(f"Catálogo poblado: {count_created} nuevas entradas.")
        
        # Vincular tickets en lotes usando bulk_update
        tickets_list = list(SolicitudTicket.objects.exclude(falla_descripcion__isnull=True).exclude(falla_descripcion=''))
        total_tickets = len(tickets_list)
        print(f"Preparando {total_tickets} tickets para vinculación...")
        
        to_update = []
        for ticket in tickets_list:
            if ticket.falla_descripcion in mapa_fallas:
                ticket.falla_reportada = mapa_fallas[ticket.falla_descripcion]
                to_update.append(ticket)
        
        print(f"Iniciando bulk_update de {len(to_update)} registros...")
        if to_update:
            # Procesar en lotes de 1000 para no saturar memoria/db
            batch_size = 1000
            for i in range(0, len(to_update), batch_size):
                batch = to_update[i:i + batch_size]
                SolicitudTicket.objects.bulk_update(batch, ['falla_reportada'])
                print(f"Progreso: {min(i + batch_size, len(to_update))}/{len(to_update)}")

    print(f"Migración completada. {count_created} fallas creadas, {len(to_update)} tickets vinculados.")

if __name__ == "__main__":
    migrate_existing_fallas()
