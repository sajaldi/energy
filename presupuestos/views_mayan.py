from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.csrf import csrf_exempt
from django.contrib.contenttypes.models import ContentType
from documentos.mayan_client import MayanEDMSClient
from documentos.models import MayanDocumentLink
from .models import Requisicion


@csrf_exempt
@staff_member_required
def upload_requisition_document_to_mayan(request):
    """
    Vista para subir un documento de requisición a Mayan EDMS
    
    POST params:
        - file: Archivo a subir
        - requisicion_id: ID de la requisición
        - title: Título del documento
        - description: Descripción/asunto del documento
        - document_type_id: ID del tipo de documento en Mayan (opcional, default=1)
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    file = request.FILES.get('file')
    requisicion_id = request.POST.get('requisicion_id')
    title = request.POST.get('title', '')
    description = request.POST.get('description', '')
    document_type_id = request.POST.get('document_type_id', 1)
    
    if not file:
        return JsonResponse({'error': 'No se proporcionó ningún archivo'}, status=400)
    
    if not requisicion_id:
        return JsonResponse({'error': 'No se proporcionó el ID de la requisición'}, status=400)
    
    if not title:
        return JsonResponse({'error': 'El título es obligatorio'}, status=400)
    
    try:
        # Verificar que la requisición existe
        requisicion = get_object_or_404(Requisicion, pk=requisicion_id)
        
        # Subir a Mayan
        client = MayanEDMSClient()
        mayan_doc = client.upload_document(
            file=file,
            document_type_id=document_type_id,
            description=description
        )
        
        if not mayan_doc or 'id' not in mayan_doc:
            return JsonResponse({
                'error': 'Error al subir el documento a Mayan',
                'details': mayan_doc
            }, status=500)
        
        # Obtener ContentType de Requisicion
        content_type = ContentType.objects.get_for_model(Requisicion)
        
        # Crear vínculo en Django
        link = MayanDocumentLink.objects.create(
            mayan_document_id=mayan_doc['id'],
            document_label=title,
            document_type=str(document_type_id),
            content_type=content_type,
            object_id=requisicion.pk,
            uploaded_by=request.user,
            description=description
        )
        
        return JsonResponse({
            'status': 'success',
            'message': 'Documento subido exitosamente a Mayan',
            'mayan_id': mayan_doc['id'],
            'link_id': link.id,
            'title': title,
            'description': description,
            'mayan_url': link.mayan_url,
            'download_url': link.download_url
        })
        
    except Requisicion.DoesNotExist:
        return JsonResponse({'error': 'Requisición no encontrada'}, status=404)
    except Exception as e:
        import traceback
        return JsonResponse({
            'error': str(e),
            'trace': traceback.format_exc()
        }, status=500)
