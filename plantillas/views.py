from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponse, JsonResponse
from django.apps import apps
from django.contrib import messages
import json

from .models import PlantillaWord
from .utils import generar_plantilla_en_blanco, poblar_plantilla


@staff_member_required
def lista_modelos(request):
    """
    Vista JSON: retorna todos los modelos registrados en el proyecto
    para que el usuario pueda seleccionar uno y generar su plantilla.
    """
    modelos = []
    for ct in ContentType.objects.all().order_by('app_label', 'model'):
        try:
            model_class = ct.model_class()
            if model_class is None:
                continue
            modelos.append({
                'id': ct.id,
                'app': ct.app_label,
                'modelo': ct.model,
                'nombre': model_class._meta.verbose_name.title(),
                'nombre_plural': model_class._meta.verbose_name_plural.title(),
            })
        except Exception:
            continue

    return JsonResponse({'modelos': modelos})


@staff_member_required
def generar_plantilla_view(request, content_type_id):
    """
    Descarga un .docx en blanco con todos los marcadores {{ campo }}
    para el modelo especificado por su ContentType ID.
    """
    ct = get_object_or_404(ContentType, pk=content_type_id)
    model_class = ct.model_class()

    if model_class is None:
        return HttpResponse("Modelo no encontrado.", status=404)

    buffer, campos = generar_plantilla_en_blanco(model_class)

    filename = f"plantilla_{ct.app_label}_{ct.model}.docx"
    response = HttpResponse(
        buffer.read(),
        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@staff_member_required
def campos_modelo_json(request, content_type_id):
    """
    API JSON: retorna los campos del modelo para previsualización.
    """
    from .utils import _get_campos_modelo
    ct = get_object_or_404(ContentType, pk=content_type_id)
    model_class = ct.model_class()
    if model_class is None:
        return JsonResponse({'error': 'Modelo no encontrado'}, status=404)

    campos = _get_campos_modelo(model_class)
    return JsonResponse({'campos': campos, 'modelo': ct.model, 'app': ct.app_label})


@staff_member_required
def poblar_plantilla_view(request, plantilla_id, app_label, model_name, registro_pk):
    """
    Descarga el .docx de la plantilla `plantilla_id` poblado con los datos
    del registro `registro_pk` del modelo `app_label.model_name`.
    """
    plantilla = get_object_or_404(PlantillaWord, pk=plantilla_id, activa=True)

    try:
        model_class = apps.get_model(app_label, model_name)
    except LookupError:
        return HttpResponse(f"Modelo '{app_label}.{model_name}' no encontrado.", status=404)

    registro = get_object_or_404(model_class, pk=registro_pk)

    try:
        buffer = poblar_plantilla(plantilla, registro)
    except Exception as e:
        return HttpResponse(f"Error al generar documento: {e}", status=500)

    nombre_registro = str(registro).replace('/', '-').replace(' ', '_')[:50]
    filename = f"{plantilla.nombre}_{nombre_registro}.docx"

    response = HttpResponse(
        buffer.read(),
        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@staff_member_required
def selector_plantilla_view(request):
    """
    Vista HTML: Selector interactivo de modelo → descarga plantilla en blanco.
    """
    from django.contrib.admin import site as admin_site
    context = {
        'title': 'Generador de Plantillas Word',
        **admin_site.each_context(request),
    }
    return render(request, 'plantillas/selector.html', context)
