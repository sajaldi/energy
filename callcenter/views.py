from django.shortcuts import redirect
from django.contrib import messages
from .tasks import sync_tickets_task
from django.contrib.admin.views.decorators import staff_member_required

import logging
logger = logging.getLogger(__name__)

@staff_member_required
def trigger_sync_tickets(request):
    """
    Vista para activar la sincronización de tickets de forma manual.
    """
    days = int(request.GET.get('days', 2))
    
    try:
        logger.info(f"[DEBUG] Despachando tarea sync_tickets_task para los últimos {days} días...")
        sync_tickets_task.delay(days=days)
        logger.info("[DEBUG] Tarea despachada correctamente a Celery.")
        messages.success(request, f"Se ha iniciado la sincronización de los últimos {days} días en segundo plano.")
    except Exception as e:
        logger.error(f"[ERROR] No se pudo enviar la tarea a Celery: {e}")
        messages.error(request, f"Error al iniciar la sincronización: {e}")
    
    # Redirigir al listado de tickets en el admin
    return redirect('admin:callcenter_solicitudticket_changelist')
