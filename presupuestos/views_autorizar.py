from datetime import datetime
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
import requests
from .models import Requisicion

import traceback

def requisicion_autorizar(request, pk):
    try:
        if request.method != 'POST':
            return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)
        
        requisicion = get_object_or_404(Requisicion, pk=pk)
        
        # 1. Información del Solicitante y Responsable
        solicitante = requisicion.usuario_solicitante
        perfil_sol = getattr(solicitante, 'perfil', None) if solicitante else None
        responsable = perfil_sol.responsable if perfil_sol else None
        perfil_resp = getattr(responsable, 'perfil', None) if responsable else None

        # 2. Artículos de la Requisición
        articulos_list = []
        for art in requisicion.articulos.all():
            articulos_list.append({
                "descripcion": art.cr8ca_articulo,
                "cantidad": float(art.cr8ca_cantidad),
                "costo_unitario": float(art.cr8ca_costoaproximado or 0),
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
            "motivo": requisicion.cr8ca_motivo,
            "costo_total": float(requisicion.total_estimado or 0),
            "email_solicitante": solicitante.email if solicitante else "",
            "telefono_solicitante": perfil_sol.telefono if perfil_sol else "N/A",
            "gerente_nombre": f"{responsable.first_name} {responsable.last_name}".strip() if responsable else "No asignado",
            "gerente_email": responsable.email if responsable else "N/A",
            "gerente_telefono": perfil_resp.telefono if perfil_resp else "N/A",
            "proveedores": ", ".join(proveedores_nombres),
            "articulos": articulos_list,
            "timestamp": datetime.now().isoformat()
        }
        
        # URL de Power Automate
        url = "https://ce675e3ed2704594af019ed8d7d5f6.d7.environment.api.powerplatform.com:443/powerautomate/automations/direct/workflows/cc9e61ecc75f40e1bc6c502e14a7a47e/triggers/manual/paths/invoke?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=CpELVKybC1iwKmlr4qJXMHPgif2LoeH_mBgt902HbGI"
        
        response = requests.post(url, json=payload)
        if response.status_code in [200, 202]:
            requisicion.estado_requisicion = 'PENDIENTE'
            requisicion.save()
            return JsonResponse({'success': True, 'message': 'Autorización solicitada exitosamente.'})
        else:
            return JsonResponse({'success': False, 'message': f'Error en Power Automate: {response.status_code}'}, status=500)
            
    except Exception as e:
        print(traceback.format_exc())
        return JsonResponse({'success': False, 'message': f"Error interno: {str(e)}"}, status=500)
