import json
import uuid
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db import transaction
from .models import Documento, TipoDocumento, Disciplina, Revision


@login_required
def documento_carga_masiva(request):
    """
    Vista principal para la carga masiva de documentos mediante drag & drop.
    Paso 1: El usuario arrastra los archivos → se muestra la tabla editable.
    Paso 2: El usuario llena Código y Descripción para cada archivo.
    Paso 3: Se envía el formulario y se suben todos los documentos a MinIO.
    """
    tipos = TipoDocumento.objects.all().order_by('nombre')
    disciplinas = Disciplina.objects.all().order_by('nombre')

    context = {
        'tipos': tipos,
        'disciplinas': disciplinas,
    }
    return render(request, 'documentos/carga_masiva.html', context)


@login_required
@require_POST
def documento_carga_masiva_submit(request):
    """
    Endpoint que recibe los archivos y metadatos de la carga masiva.
    Crea el Documento maestro + Revisión para cada archivo.
    Retorna JSON con el resultado (éxito/error por cada archivo).
    """
    tipo_id = request.POST.get('tipo_id')
    disciplina_id = request.POST.get('disciplina_id') or None

    if not tipo_id:
        return JsonResponse({'error': 'Debe seleccionar un Tipo de Documento.'}, status=400)

    archivos = request.FILES.getlist('archivos')
    codigos = request.POST.getlist('codigos')
    titulos = request.POST.getlist('titulos')

    if not archivos:
        return JsonResponse({'error': 'No se recibieron archivos.'}, status=400)

    resultados = []

    for i, archivo in enumerate(archivos):
        codigo = codigos[i].strip().upper() if i < len(codigos) else ''
        titulo = titulos[i].strip() if i < len(titulos) else ''

        # Código por defecto si no se ingresó
        if not codigo:
            codigo = f"DOC-{uuid.uuid4().hex[:8].upper()}"

        # Título por defecto al nombre del archivo (sin extensión)
        if not titulo:
            titulo = archivo.name.rsplit('.', 1)[0]

        try:
            with transaction.atomic():
                # Verificar si ya existe el código
                if Documento.objects.filter(codigo=codigo).exists():
                    resultados.append({
                        'archivo': archivo.name,
                        'ok': False,
                        'mensaje': f"El código '{codigo}' ya existe en el sistema."
                    })
                    continue

                # Crear documento maestro
                documento = Documento.objects.create(
                    codigo=codigo,
                    titulo=titulo,
                    tipo_documento_id=tipo_id,
                    disciplina_id=disciplina_id,
                    responsable=request.user,
                    estado_actual='RECIBIDO',
                )

                # Crear revisión inicial (sube a MinIO automáticamente)
                revision = Revision.objects.create(
                    documento=documento,
                    revision='0',
                    archivo=archivo,
                    creado_por=request.user,
                    estado_extraccion='PENDIENTE',
                )

                # Disparar extracción asíncrona
                try:
                    from .tasks import extract_document_metadata
                    extract_document_metadata.delay(revision.id)
                except Exception:
                    pass  # No bloquear si Celery no está disponible

                resultados.append({
                    'archivo': archivo.name,
                    'ok': True,
                    'codigo': codigo,
                    'titulo': titulo,
                    'doc_id': documento.id,
                    'mensaje': 'Subido exitosamente.'
                })

        except Exception as e:
            resultados.append({
                'archivo': archivo.name,
                'ok': False,
                'mensaje': str(e)
            })

    total = len(resultados)
    exitosos = sum(1 for r in resultados if r['ok'])

    return JsonResponse({
        'resultados': resultados,
        'total': total,
        'exitosos': exitosos,
        'fallidos': total - exitosos,
    })
