import os
import sys
import django

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

from django.contrib.auth.models import User
from presupuestos.models import Requisicion
from presupuestos.forms import RequisicionForm

try:
    req_uuid = '2a3809e4-39d9-4912-b979-d922cbbc7bb0'
    req = Requisicion.objects.get(pk=req_uuid)
    
    print(f"Requisicion UUID: {req.pk}")
    print(f"Solicitante: {req.usuario_solicitante}")
    if req.usuario_solicitante and hasattr(req.usuario_solicitante, 'perfil'):
        print(f"Solicitante Dept: {req.usuario_solicitante.perfil.departamento}")
        
    print("\n--- Inicializando Form con request.user = admin ---")
    admin_user = User.objects.filter(is_superuser=True).first()
    form = RequisicionForm(instance=req, user=admin_user)
    
    print(f"Form partida field queryset count: {form.fields['partida'].queryset.count()}")
    print("Partidas en el queryset:")
    for p in form.fields['partida'].queryset:
        print(f" - {p.id}: {p} (Presupuesto Dept: {p.presupuesto_anual.departamento})")
        
except Exception as e:
    print(f"Error: {e}")
