import os
import sys
import django

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

from django.contrib.auth.models import User
from presupuestos.models import PartidaPresupuestaria, PresupuestoAnual
from core.models import Departamento

try:
    print("--- Buscando usuario 'eder.molina' ---")
    user = User.objects.get(username='eder.molina')
    print(f"Usuario: {user.username} (ID: {user.id})")
    
    if hasattr(user, 'perfil'):
        profile = user.perfil
        print(f"Perfil encontrado: ID {profile.id}")
        depto = profile.departamento
        if depto:
            print(f"Departamento: {depto.nombre} (ID: {depto.id}, Codigo: {depto.codigo})")
        else:
            print("Departamento del Perfil es None!")
    else:
        print("El usuario no tiene Perfil!")
        
    print("\n--- Departamentos en el sistema ---")
    for d in Departamento.objects.all():
        print(f"ID: {d.id} | Codigo: {d.codigo} | Nombre: {d.nombre}")

    print("\n--- Partidas Presupuestarias y sus Filtros ---")
    partidas = PartidaPresupuestaria.objects.all()
    print(f"Total Partidas: {partidas.count()}")
    for p in partidas[:15]:
        deptos_str = ", ".join([d.nombre for d in p.departamentos.all()]) if p.departamentos.exists() else "Global (Sin departamentos)"
        pa = p.presupuesto_anual
        pa_depto = pa.departamento.nombre if pa.departamento else "Global (Sin departamento)"
        print(f"ID: {p.id} | Desc: {p} | Presupuesto: {pa.nombre} (Depto: {pa_depto}) | Departamentos Permitidos: {deptos_str}")
        
except Exception as e:
    print(f"Error: {e}")
