import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from .models import Documento, TipoDocumento, Disciplina, Revision, MetadatoConfig, MetadatoValor
from django.db import transaction
from .utils_extraer import extract_metadata_from_file

@login_required
def documento_reprocesar_verificacion(request, doc_id):
    """
    Toma un documento existente, extrae su información y lo lleva
    al paso 3 del wizard para corregir/confirmar metadatos.
    """
    documento = get_object_or_404(Documento, id=doc_id)
    # Intentar obtener la revisión 0 o la última disponible
    revision = documento.revisiones.filter(revision='0').first() or documento.ultima_revision
    
    if not revision or not revision.archivo:
        messages.error(request, "Este documento no tiene un archivo cargado para procesar.")
        return redirect(f'/admin/documentos/documento/{doc_id}/change/')

    try:
        # Limpiar datos previos de sesión para este flujo
        if 'doc_wizard_data' in request.session:
            del request.session['doc_wizard_data']
            
        # Cambiar estado a PENDIENTE para disparar la animación de espera en la UI
        revision.estado_extraccion = 'PENDIENTE'
        revision.save()
        
        # Disparar tarea Celery
        from .tasks import extract_document_metadata
        extract_document_metadata.delay(revision.id)
            
        messages.info(request, "Análisis reiniciado. Por favor, espere a que se complete.")
        return redirect(f'/documentos/nuevo/?step=2.5&doc_id={doc_id}')
        
    except Exception as e:
        messages.error(request, f"Error al iniciar re-procesamiento: {str(e)}")
        return redirect(f'/admin/documentos/documento/{doc_id}/change/')

@login_required
def documento_wizard(request):
    """
    Wizard Refactorizado Core:
    Paso 1: Metadatos básicos (Tipo requerido, Título/Código opcionales)
    Paso 2: Carga y Extracción Inteligente
    Paso 3: Verificación sugiriendo Código y Título extraídos
    """
    step = float(request.GET.get('step', 1))
    doc_id = request.GET.get('doc_id')
    
    titles = {
        1: 'Identificación del Documento',
        2: 'Carga y Análisis',
        2.5: 'Procesando Análisis',
        3: 'Verificación y Metadatos'
    }
    
    context = {
        'step': step,
        'doc_id': doc_id,
        'title': titles.get(step, '')
    }

    if step == 1:
        context['tipos'] = TipoDocumento.objects.all().order_by('nombre')
        context['disciplinas'] = Disciplina.objects.all().order_by('nombre')
        
        # Cargar datos: Prioridad Sesión > Documento Existente
        saved_data = request.session.get('doc_wizard_data', {})
        if doc_id and not saved_data:
            doc = get_object_or_404(Documento, id=doc_id)
            saved_data = {
                'tipo_id': str(doc.tipo_documento_id),
                'titulo': doc.titulo,
                'codigo': doc.codigo,
                'disciplina_id': str(doc.disciplina_id or ''),
            }
        
        # Pre-marcar selección para evitar errores de sintaxis en template (etiquetas partidas)
        for t in context['tipos']:
            t.is_checked = str(t.id) == str(saved_data.get('tipo_id', ''))
        for d in context['disciplinas']:
            d.is_selected = str(d.id) == str(saved_data.get('disciplina_id', ''))

        context['saved_data'] = saved_data

        if request.method == 'POST':
            tipo_id = request.POST.get('tipo_id')
            titulo = request.POST.get('titulo', '')
            codigo = request.POST.get('codigo', '')
            disciplina_id = request.POST.get('disciplina_id')
            
            if not tipo_id:
                messages.error(request, "Debe seleccionar el tipo de documento.")
                return render(request, 'documentos/documento_wizard.html', context)
            
            # Validar código si fue ingresado (excepto si estamos editando el mismo doc)
            if codigo and Documento.objects.filter(codigo=codigo).exclude(id=doc_id if doc_id else -1).exists():
                messages.error(request, f"El código '{codigo}' ya está en uso.")
                return render(request, 'documentos/documento_wizard.html', context)

            request.session['doc_wizard_data'] = {
                'tipo_id': tipo_id,
                'titulo': titulo or 'Documento sin título (Wizard)',
                'codigo': codigo,
                'disciplina_id': disciplina_id,
            }
            url = '/documentos/nuevo/?step=2'
            if doc_id: url += f'&doc_id={doc_id}'
            return redirect(url)

    elif step == 2:
        if 'doc_wizard_data' not in request.session:
            return redirect('/documentos/nuevo/?step=1')
            
        if request.method == 'POST':
            archivo = request.FILES.get('archivo')
            if not archivo:
                messages.error(request, "Archivo requerido para el análisis.")
                return render(request, 'documentos/documento_wizard.html', context)
            
            data = request.session['doc_wizard_data']
            try:
                with transaction.atomic():
                    # Generar código temporal si no se proporcionó uno
                    final_codigo = data['codigo']
                    if not final_codigo:
                        import uuid
                        final_codigo = f"TMP-{uuid.uuid4().hex[:8].upper()}"

                    if doc_id:
                        documento = get_object_or_404(Documento, id=doc_id)
                        documento.codigo = final_codigo
                        documento.titulo = data['titulo']
                        documento.tipo_documento_id = data['tipo_id']
                        documento.disciplina_id = data.get('disciplina_id') or None
                        documento.save()
                    else:
                        documento = Documento.objects.create(
                            codigo=final_codigo,
                            titulo=data['titulo'],
                            tipo_documento_id=data['tipo_id'],
                            disciplina_id=data.get('disciplina_id') or None
                        )
                    
                    # Guardar revisión y disparar extracción ASÍNCRONA
                    revision, created = Revision.objects.update_or_create(
                        documento=documento,
                        revision='0',
                        defaults={
                            'archivo': archivo,
                            'creado_por': request.user,
                            'estado_extraccion': 'PENDIENTE'
                        }
                    )
                    
                    # Disparar tarea Celery
                    from .tasks import extract_document_metadata
                    extract_document_metadata.delay(revision.id)
                    
                    # 4. Procesamiento de Metadatos
                    # La tarea maneje la extracción y análisis de contenido
                    
                messages.info(request, "Archivo cargado. Procesando análisis inteligente...")
                return redirect(f'/documentos/nuevo/?step=2.5&doc_id={documento.id}')
            except Exception as e:
                import traceback
                print(traceback.format_exc())
                messages.error(request, f"Error en carga: {str(e)}")
                return render(request, 'documentos/documento_wizard.html', context)

    elif step == 2.5: # NUEVO PASO: Espera de Procesamiento
        if not doc_id:
            return redirect('/documentos/nuevo/?step=1')
            
        documento = get_object_or_404(Documento, id=doc_id)
        revision = documento.revisiones.filter(revision='0').first() or documento.ultima_revision
        
        if revision.estado_extraccion == 'COMPLETADO':
            return redirect(f'/documentos/nuevo/?step=3&doc_id={doc_id}')
        elif revision.estado_extraccion == 'ERROR':
            messages.error(request, f"Error en análisis: {revision.datos_extraidos.get('error', 'Error desconocido')}")
            return redirect(f'/documentos/nuevo/?step=2&doc_id={doc_id}')
            
        context.update({'documento': documento, 'revision': revision})
        return render(request, 'documentos/documento_wizard_waiting.html', context)

    elif step == 3:
        if not doc_id:
            return redirect('/documentos/nuevo/?step=1')
            
        documento = get_object_or_404(Documento, id=doc_id)
        revision = documento.revisiones.filter(revision='0').first() or documento.ultima_revision
        
        # Parche de seguridad: Si no hay revisión, volver al paso 2
        if not revision:
            messages.warning(request, "No se encontró el archivo del documento. Por favor súbelo nuevamente.")
            return redirect(f'/documentos/nuevo/?step=2&doc_id={doc_id}')

        documentos_link = Documento.objects.exclude(id=doc_id).order_by('-creado_en')[:50]
        
        for dl in documentos_link:
            dl.is_selected = str(dl.id) == str(documento.respuesta_a_id)

        context.update({
            'documento': documento, 
            'revision': revision,
            'documentos_link': documentos_link
        })
        
        # Sugerencia inteligente de Código y Título
        import re
        datos_ext = revision.datos_extraidos or {}
        text = datos_ext.get('text_preview', '')
        
        # Prioridad a sugerencias de IA (n8n)
        suggested_code = datos_ext.get('suggested_code')
        suggested_title = datos_ext.get('suggested_title')

        # 1. Fallback Búsqueda Código (si no hay IA o es TMP)
        if not suggested_code and 'TMP-' in documento.codigo:
            patterns = [
                r'[A-Z]{2,5}-[A-Z0-9]-[A-Z0-9]{2,5}-[A-Z0-9]{2,5}-\d{2}-\d{2}', 
                r'[A-Z]{2,4}-\d{3,6}-[A-Z0-9-]{3,10}',
                r'[A-Z]{2,4}-\d{4,8}', 
                r'(?i)Código[:\s]+([A-Z0-9-]{5,25})',
            ]
            for pat in patterns:
                m = re.search(pat, text)
                if m:
                    suggested_code = m.group(1) if '(' in pat else m.group(0)
                    break
        context['suggested_code'] = suggested_code
        
        # 2. Fallback Búsqueda Título
        if not suggested_title and documento.titulo == 'Documento sin título (Wizard)':
            lines = [l.strip() for l in text.split('\n') if len(l.strip()) > 10]
            if lines:
                for line in lines[:5]:
                    if not re.search(r'\d{5,}', line) and not '@' in line:
                        documento.titulo = line[:255]
                        break
        elif suggested_title:
            documento.titulo = suggested_title
        
        # Preparar metadatos dinámicos pre-llenados
        metadatos_config = MetadatoConfig.objects.filter(tipo_documento=documento.tipo_documento)
        metadatos_prefilled = []
        ia_metadata = datos_ext.get('ia_metadata', {})

        for config in metadatos_config:
            # Prioridad 1: IA n8n, Prioridad 2: Regex local
            suggested_value = ia_metadata.get(config.nombre, "")
            
            if not suggested_value:
                if config.tipo_campo == 'FECHA':
                    m = re.search(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', text)
                    if m:
                        raw_date = m.group(0).replace('/', '-')
                        parts = raw_date.split('-')
                        if len(parts) == 3:
                            if len(parts[2]) == 4: # DD-MM-YYYY
                                suggested_value = f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
                            elif len(parts[0]) == 4: # YYYY-MM-DD
                                suggested_value = raw_date
                elif config.tipo_campo == 'EMAIL':
                    m = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
                    if m: suggested_value = m.group(0)
                
            metadatos_prefilled.append({
                'config': config, 
                'suggested_value': suggested_value,
                'required_attr': 'required' if config.requerido else '',
                'required_mark': '*' if config.requerido else '',
                'is_date': config.tipo_campo == 'FECHA',
                'is_number': config.tipo_campo == 'NUMERO',
                'is_email': config.tipo_campo == 'EMAIL',
                'is_text': config.tipo_campo not in ['FECHA', 'NUMERO', 'EMAIL']
            })
        
        if request.method == 'POST':
            with transaction.atomic():
                documento.codigo = request.POST.get('codigo', documento.codigo)
                documento.titulo = request.POST.get('titulo', documento.titulo)
                documento.respuesta_a_id = request.POST.get('respuesta_a') or None
                documento.estado_actual = 'RECIBIDO'
                documento.save()
                
                for config in metadatos_config:
                    val = request.POST.get(f'meta_{config.id}')
                    if val:
                        MetadatoValor.objects.update_or_create(
                            documento=documento, config=config, defaults={'valor': val}
                        )
            
            # --- Automatización n8n ---
            try:
                from .utils_n8n import notify_n8n_document_created
                notify_n8n_document_created(documento)
            except Exception as e_n8n:
                print(f"Error disparando automatización n8n: {e_n8n}")

            messages.success(request, f"Documento {documento.codigo} registrado exitosamente.")
            if 'doc_wizard_data' in request.session: del request.session['doc_wizard_data']
            return redirect('admin:documentos_documento_changelist')

    return render(request, 'documentos/documento_wizard.html', context)

@login_required
def documento_wizard_status(request, doc_id):
    """
    Endpoint JSON para consultar el estado de extracción de la revisión
    """
    documento = get_object_or_404(Documento, id=doc_id)
    revision = documento.revisiones.filter(revision='0').first() or documento.ultima_revision
    
    return JsonResponse({
        'id': documento.id,
        'estado': revision.estado_extraccion if revision else 'PENDIENTE',
        'datos': revision.datos_extraidos if revision else {}
    })
