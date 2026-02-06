from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.csrf import csrf_exempt
from .mayan_client import MayanEDMSClient
from .models import MayanDocumentLink
from django.contrib.contenttypes.models import ContentType
from .models import TipoDocumento, Documento
from django.shortcuts import render, redirect, get_object_or_404

@csrf_exempt
@staff_member_required
def upload_document_to_mayan(request):
    """
    Vista para subir un documento a Mayan y vincularlo con un objeto
    
    POST params:
        - file: Archivo a subir
        - model: Nombre del modelo (ej: 'activo')
        - object_id: ID del objeto
        - document_type_id: ID del tipo de documento en Mayan
        - description: Descripción opcional
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    file = request.FILES.get('file')
    model_name = request.POST.get('model')
    object_id = request.POST.get('object_id')
    document_type_id = request.POST.get('document_type_id', 1)
    description = request.POST.get('description', '')
    
    if not file or not model_name or not object_id:
        return JsonResponse({'error': 'Faltan parámetros: file, model, object_id'}, status=400)
    
    try:
        # Subir a Mayan
        client = MayanEDMSClient()
        mayan_doc = client.upload_document(
            file=file,
            document_type_id=document_type_id,
            description=description
        )
        
        if not mayan_doc or 'id' not in mayan_doc:
            return JsonResponse({'error': 'Error al subir a Mayan', 'details': mayan_doc}, status=500)

        # Buscar ContentType
        try:
            content_type = ContentType.objects.get(model=model_name.lower())
        except ContentType.DoesNotExist:
             return JsonResponse({'error': f'Modelo no encontrado: {model_name}'}, status=400)
        
        # Crear vínculo en Django
        link = MayanDocumentLink.objects.create(
            mayan_document_id=mayan_doc['id'],
            document_label=file.name,
            document_type=str(document_type_id),
            content_type=content_type,
            object_id=object_id,
            uploaded_by=request.user,
            description=description
        )
        
        return JsonResponse({
            'status': 'success',
            'mayan_id': mayan_doc['id'],
            'link_id': link.id,
            'url': link.mayan_url
        })
        
    except Exception as e:
        import traceback
        return JsonResponse({'error': str(e), 'trace': traceback.format_exc()}, status=500)
