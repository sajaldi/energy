import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

from documentos.models import Revision, Documento

def check():
    print("--- Ultimas 5 Revisiones ---")
    revs = Revision.objects.all().order_by('-fecha_revision')[:5]
    for r in revs:
        d = r.documento
        print(f"ID: {r.id} | Doc: {d.codigo} (ID: {d.id}) | Fecha: {r.fecha_revision}")
        text_len = len(d.contenido_texto) if d.contenido_texto else 0
        print(f"  Longitud Texto: {text_len}")
        if d.contenido_texto:
            print(f"  Preview: {d.contenido_texto[:100]}...")
            if "'" in d.contenido_texto:
                print(f"  [!] CONTIENE COMILLAS SIMPLES")
        else:
            print(f"  [!] SIN TEXTO")
        print("-" * 30)

if __name__ == "__main__":
    check()
