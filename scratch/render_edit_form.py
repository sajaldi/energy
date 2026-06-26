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
    admin_user = User.objects.filter(is_superuser=True).first()
    
    # Instantiate form
    form = RequisicionForm(instance=req, user=admin_user)
    
    # Render the select field only
    print("--- Rendered Partida Field HTML ---")
    print(form['partida'].as_widget())
    
except Exception as e:
    print(f"Error: {e}")
