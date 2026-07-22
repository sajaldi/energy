import json
from datetime import datetime
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
import requests
from .models import Requisicion

import traceback
from .views_import import _registrar_historial

def requisicion_autorizar(request, pk):
    try:
        if request.method != 'POST':
            return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)
        
        requisicion = get_object_or_404(Requisicion, pk=pk)
        
        # 1. Información del Solicitante, Responsable y Aprobador
        solicitante = requisicion.usuario_solicitante
        perfil_sol = getattr(solicitante, 'perfil', None) if solicitante else None
        responsable = perfil_sol.responsable if perfil_sol else None
        perfil_resp = getattr(responsable, 'perfil', None) if responsable else None
        aprobador = requisicion.aprobador
        perfil_aprobador = getattr(aprobador, 'perfil', None) if aprobador else None

        # 2. Artículos de la Requisición
        articulos_list = []
        for art in requisicion.articulos.all():
            articulos_list.append({
                "descripcion": art.cr8ca_articulo or "",
                "cantidad": int(art.cr8ca_cantidad),
                "costo_unitario": int(round(float(art.cr8ca_costoaproximado or 0))),
                "subtotal": float(art.subtotal),
                "proveedor_sugerido": art.proveedor.nombre if art.proveedor else ""
            })

        # 3. Proveedores (Asignado + Sugeridos)
        proveedores_nombres = []
        if requisicion.proveedor:
            proveedores_nombres.append(requisicion.proveedor.nombre)
        for ps in requisicion.proveedores_sugeridos.all():
            if ps.nombre not in proveedores_nombres:
                proveedores_nombres.append(ps.nombre)

        # Payload Extendido para Power Automate
        payload = {
            "numero_requisicion": requisicion.cr8ca_requisicion,
            "asunto": requisicion.cr8ca_asunto,
            "motivo": requisicion.cr8ca_motivo or "",
            "costo_aproximado": float(requisicion.cr8ca_totalenarticulos or 0),
            "costo_total": float(requisicion.total_estimado or 0),
            "email_solicitante": (solicitante.email or "") if solicitante else "",
            "telefono_solicitante": (perfil_sol.telefono or "N/A") if perfil_sol else "N/A",
            "gerente_nombre": f"{responsable.first_name or ''} {responsable.last_name or ''}".strip() if responsable else "No asignado",
            "gerente_email": (responsable.email or "N/A") if responsable else "N/A",
            "gerente_telefono": (perfil_resp.telefono or "N/A") if perfil_resp else "N/A",
            "aprobador_nombre": f"{aprobador.first_name or ''} {aprobador.last_name or ''}".strip() if aprobador else "No asignado",
            "aprobador_email": (aprobador.email or "N/A") if aprobador else "N/A",
            "aprobador_telefono": (perfil_aprobador.telefono or "N/A") if perfil_aprobador else "N/A",
            "proveedores": ", ".join(proveedores_nombres),
            "vinculo_aprobacion": f"{settings.SITE_URL}{reverse('presupuestos:requisicion_editar', kwargs={'pk': requisicion.pk})}?step=4",
            "articulos": articulos_list,
            "timestamp": datetime.now().isoformat()
        }
        
        # DEBUG: log del payload exacto
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"PAYLOAD ENVIADO: {json.dumps(payload, indent=2, default=str)}")

        # URL de Power Automate
        url = "https://ce675e3ed2704594af019ed8d7d5f6.d7.environment.api.powerplatform.com:443/powerautomate/automations/direct/workflows/cc9e61ecc75f40e1bc6c502e14a7a47e/triggers/manual/paths/invoke?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=CpELVKybC1iwKmlr4qJXMHPgif2LoeH_mBgt902HbGI"
        
        response = requests.post(url, json=payload)
        logger.error(f"PA RESPONSE: {response.status_code} - {response.text}")
        if response.status_code in [200, 202]:
            _registrar_historial(requisicion, 'PENDIENTE', usuario=request.user)
            requisicion.estado_requisicion = 'PENDIENTE'
            requisicion.save()
            return JsonResponse({'success': True, 'message': 'Autorización solicitada exitosamente.'})
        else:
            return JsonResponse({'success': False, 'message': f'Error en Power Automate: {response.status_code}'}, status=500)
            
    except Exception as e:
        print(traceback.format_exc())
        return JsonResponse({'success': False, 'message': f"Error interno: {str(e)}"}, status=500)
