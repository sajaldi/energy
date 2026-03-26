from django.shortcuts import render, get_object_or_404
from .models import ArticuloAyuda, CategoriaAyuda
from django.contrib.admin.views.decorators import staff_member_required

@staff_member_required
def help_index(request):
    categorias = CategoriaAyuda.objects.prefetch_related('articulos').all()
    return render(request, 'ayuda/help_index.html', {'categorias': categorias})

@staff_member_required
def help_detail(request, slug):
    articulo = get_object_or_404(ArticuloAyuda, slug=slug)
    return render(request, 'ayuda/help_detail.html', {'articulo': articulo})
