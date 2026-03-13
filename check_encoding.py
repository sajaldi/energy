import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

from documentos.models import Documento

def check():
    print("--- Verificando Codificación en BD ---")
    # Buscar documentos que tengan el texto con el problema
    docs = Documento.objects.filter(contenido_texto__icontains='??').order_by('-id')[:5]
    if not docs:
        print("No se encontraron documentos con '??'. Buscando los últimos actualizados...")
        docs = Documento.objects.all().order_by('-actualizado_en')[:5]
    
    for d in docs:
        print(f"ID: {d.id} | Codigo: {d.codigo}")
        texto = d.contenido_texto or ""
        print(f"  Longitud: {len(texto)}")
        if texto:
            print(f"  Preview: {texto[:200]}...")
            # Verificar si hay caracteres no ASCII o con problemas
            try:
                texto.encode('ascii')
                print("  [OK] El texto es puramente ASCII (no debería tener acentos).")
            except UnicodeEncodeError:
                print("  [INFO] El texto contiene caracteres no-ASCII (acentos u otros).")
                
            if '??' in texto:
                print("  [!] ERROR: El texto contiene '??' literalmente.")
        else:
            print("  [!] SIN TEXTO")
        print("-" * 30)

if __name__ == "__main__":
    check()
