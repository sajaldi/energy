import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

from documentos.models import Documento

def find():
    print("--- Buscando Documentos con '??' ---")
    # Texto reportado por el usuario
    target = 'provisi??n'
    query = Documento.objects.filter(contenido_texto__icontains=target)
    count = query.count()
    print(f"Total encontrados: {count}")
    
    for d in query[:10]:
        print(f"ID: {d.id} | Codigo: {d.codigo}")
        # Encontrar dónde está el error
        start_idx = d.contenido_texto.find('provisi??n')
        preview = d.contenido_texto[max(0, start_idx-50):start_idx+100]
        print(f"  Contexto: ...{preview}...")
        print("-" * 30)

if __name__ == "__main__":
    find()
