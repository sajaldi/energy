from django.shortcuts import render, get_object_or_404
from .models import ArticuloAyuda, CategoriaAyuda
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from core.storage import MinIOStorage
import uuid
import os

@staff_member_required
def help_index(request):
    categorias = CategoriaAyuda.objects.prefetch_related('articulos').all()
    return render(request, 'ayuda/help_index.html', {'categorias': categorias})

@staff_member_required
def help_detail(request, slug):
    articulo = get_object_or_404(ArticuloAyuda, slug=slug)
    return render(request, 'ayuda/help_detail.html', {'articulo': articulo})

@staff_member_required
def upload_image_admin(request):
    """
    Endpoint para subir imágenes desde el editor de ayuda via AJAX (Ctrl+V).
    """
    if request.method == 'POST' and request.FILES.get('image'):
        try:
            image_file = request.FILES['image']
            ext = os.path.splitext(image_file.name)[1] or '.png'
            filename = f"help_img_{uuid.uuid4().hex}{ext}"
            
            storage = MinIOStorage()
            save_path = f"ayuda/articulos/{filename}"
            final_path = storage.save(save_path, image_file)
            url = storage.url(final_path)
            
            return JsonResponse({'status': 'success', 'url': url})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
            
    return JsonResponse({'status': 'error', 'message': 'Petición inválida'}, status=400)

@staff_member_required
def help_editor(request):
    categorias = CategoriaAyuda.objects.prefetch_related('articulos').all()
    return render(request, 'ayuda/help_editor.html', {'categorias': categorias})

@staff_member_required
def ajax_get_article(request):
    article_id = request.GET.get('id')
    articulo = get_object_or_404(ArticuloAyuda, pk=article_id)
    return JsonResponse({
        'status': 'success',
        'data': {
            'id': articulo.id,
            'titulo': articulo.titulo,
            'contenido': articulo.contenido,
            'video_url': articulo.video_url,
            'categoria_id': articulo.categoria_id,
        }
    })

@staff_member_required
def ajax_save_article(request):
    if request.method == 'POST':
        import json
        data = json.loads(request.body)
        article_id = data.get('id')
        articulo = get_object_or_404(ArticuloAyuda, pk=article_id)
        
        articulo.titulo = data.get('titulo', articulo.titulo)
        articulo.contenido = data.get('contenido', articulo.contenido)
        articulo.video_url = data.get('video_url', articulo.video_url)
        articulo.save()
        
        return JsonResponse({'status': 'success', 'message': 'Artículo guardado correctamente'})
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

@staff_member_required
def ajax_create_article(request):
    if request.method == 'POST':
        import json
        data = json.loads(request.body)
        categoria_id = data.get('categoria_id')
        categoria = get_object_or_404(CategoriaAyuda, pk=categoria_id)
        
        articulo = ArticuloAyuda.objects.create(
            categoria=categoria,
            titulo="Nuevo Artículo",
            contenido="# Título\n\nContenido aquí..."
        )
        
        return JsonResponse({
            'status': 'success', 
            'article_id': articulo.id,
            'titulo': articulo.titulo
        })
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
