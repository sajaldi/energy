from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.db import models
from django.conf import settings
import logging
import json
import requests
import datetime
from .models import Documento, ComentarioDocumento, TipoDocumento, Disciplina, Revision, MetadatoConfig, ComentarioImagen
from django.contrib.contenttypes.models import ContentType

@login_required
def api_get_model_fields(request):
    """
    Retorna una lista de campos disponibles para un ContentType específico.
    Se usa para el selector dinámico en la configuración de metadatos relacionales.
    """
    ct_id = request.GET.get('ct_id')
    if not ct_id:
        return JsonResponse({'fields': []})
    
    try:
        ct = ContentType.objects.get(pk=ct_id)
        model_class = ct.model_class()
        if model_class:
            # Obtener campos simples que no sean relaciones ManyToMany o reversas complejas
            fields = []
            for f in model_class._meta.get_fields():
                # Filtrar campos: queremos campos de base de datos directos o FKs simples
                if not f.is_relation or f.many_to_one or f.one_to_one:
                    if hasattr(f, 'name') and not f.name.startswith('_'):
                        fields.append(f.name)
            
            return JsonResponse({'fields': sorted(list(set(fields)))})
    except Exception as e:
        print(f"Error en api_get_model_fields: {e}")
        
    return JsonResponse({'fields': []})

@login_required
def documento_trazabilidad(request, doc_id):
    """
    Visualizador de trazabilidad de un documento (hacia atrás y hacia adelante).
    Incluye vínculos transversales mediante pines (pines a otros documentos).
    """
    documento = get_object_or_404(Documento, id=doc_id)
    
    # 1. Encontrar la raíz (el primer documento de la cadena)
    root = documento
    visited = {root.id}
    while root.respuesta_a:
        if root.respuesta_a.id in visited:
            break # Evitar bucles infinitos
        root = root.respuesta_a
        visited.add(root.id)
    
    # 2. Recopilar vínculos transversales primero para integrarlos en el árbol
    ids_provisorios = set()
    def get_all_ids(doc):
        ids_provisorios.add(doc.id)
        for hijo in doc.respuestas.all():
            get_all_ids(hijo)
    get_all_ids(root)

    vinc_comments = ComentarioDocumento.objects.filter(
        models.Q(documento_id__in=ids_provisorios) | 
        models.Q(vinculos__documento_id__in=ids_provisorios)
    ).prefetch_related('vinculos__documento', 'vinculos__documento__tipo_documento')

    links_por_doc = {} # doc_id -> list of external docs linked
    pines_vinculados = []
    seen_links = set()
    
    for c in vinc_comments:
        for v in c.vinculos.all():
            link_pair = tuple(sorted([c.id, v.id]))
            if link_pair not in seen_links:
                seen_links.add(link_pair)
                pines_vinculados.append({
                    'from_doc': c.documento.id,
                    'to_doc': v.documento.id,
                    'from_code': c.documento.codigo,
                    'to_code': v.documento.codigo
                })
                
                # Identificar cuál es externo al árbol principal
                d1, d2 = c.documento, v.documento
                if d1.id in ids_provisorios and d2.id not in ids_provisorios:
                    if d1.id not in links_por_doc: links_por_doc[d1.id] = []
                    links_por_doc[d1.id].append(d2)
                elif d2.id in ids_provisorios and d1.id not in ids_provisorios:
                    if d2.id not in links_por_doc: links_por_doc[d2.id] = []
                    links_por_doc[d2.id].append(d1)

    # 3. Función recursiva para construir el árbol e integrar los vínculos
    def build_tree(doc, current_doc_id, is_external=False, parent_date=None):
        # Calcular diferencia de días si existe fecha de padre
        dias_diferencia = None
        if parent_date and doc.fecha_inicio:
            dias_diferencia = (doc.fecha_inicio - parent_date).days
        
        # Prefetch metadatos para evitar N+1
        children = doc.respuestas.all().select_related('tipo_documento', 'ultima_revision')
        metadatos_qs = doc.metadatos_valores.all().select_related('config')
        
        metadatos_list = []
        for mv in metadatos_qs:
            valor = mv.valor
            if mv.objeto_vinculado:
                valor = str(mv.objeto_vinculado)
            
            metadatos_list.append({
                'etiqueta': mv.config.etiqueta,
                'valor': valor
            })

        vinculos_externos = []
        if not is_external and doc.id in links_por_doc:
            for ext in links_por_doc[doc.id]:
                vinculos_externos.append(build_tree(ext, current_doc_id, is_external=True))

        return {
            'id': doc.id,
            'codigo': doc.codigo,
            'titulo': doc.titulo,
            'tipo': doc.tipo_documento.nombre if doc.tipo_documento else "S/T",
            'estado': doc.estado_actual,
            'fecha': doc.fecha_inicio, # Mostrar exclusivamente fecha del documento
            'is_current': doc.id == current_doc_id,
            'is_external': is_external,
            'vinculos_externos': vinculos_externos,
            'metadatos': metadatos_list,
            'dias_diferencia': dias_diferencia,
            'hijos': [build_tree(child, current_doc_id, is_external=is_external, parent_date=doc.fecha_inicio) for child in children]
        }
    
    tree = build_tree(root, documento.id)
    
    from django.contrib.auth.models import User
    context = {
        'documento': documento,
        'tree': tree,
        'root': root,
        'pines_vinculados': pines_vinculados,
        'usuarios': User.objects.filter(is_active=True).order_by('first_name')
    }
    return render(request, 'documentos/documento_trazabilidad.html', context)

@login_required
def documento_visor_pines(request, doc_id):
    """
    Vista exclusiva para colocar y ver pines en el PDF.
    """
    documento = get_object_or_404(Documento, id=doc_id)
    context = {'documento': documento}
    return render(request, 'documentos/visor_comentarios.html', context)


@login_required
def documento_detalle_json(request, doc_id):
    """
    Retorna detalles extendidos de un documento para el panel lateral de trazabilidad.
    """
    try:
        doc = get_object_or_404(Documento, id=doc_id)
        
        # Metadatos dinámicos
        metadatos = []
        for mv in doc.metadatos_valores.all().select_related('config'):
            metadatos.append({
                'id': mv.id,
                'etiqueta': mv.config.etiqueta,
                'valor': mv.valor,
                'tipo_campo': mv.config.tipo_campo
            })
        
        # Comentarios (pines)
        comentarios = []
        for c in doc.comentarios.all().select_related('usuario').order_by('creado_en'):
            comentarios.append({
                'id': c.id,
                'texto': c.texto,
                'usuario': c.usuario.username,
                'fecha': c.creado_en.strftime('%d/%m/%Y %H:%M'),
                'x': c.posicion_x,
                'y': c.posicion_y,
                'ancho': c.ancho,
                'alto': c.alto,
                'tipo': c.tipo,
                'pagina': c.pagina,
                'resuelto': c.resuelto,
                'responsable_id': c.responsable.id if c.responsable else None,
                'responsable_nombre': c.responsable.get_full_name() or c.responsable.username if c.responsable else None,
                'vinculos': [{'id': v.id, 'doc_id': v.documento.id, 'doc_codigo': v.documento.codigo} for v in c.vinculos.all()],
                'imagenes': [request.build_absolute_uri(img.imagen.url) for img in c.imagenes.all()]
            })

        usuarios = list(User.objects.filter(is_active=True).values('id', 'username', 'first_name', 'last_name').order_by('first_name'))

        # Info de archivo
        url_archivo = ""
        url_archivo_proxy = ""
        try:
            if doc.ultima_revision and doc.ultima_revision.archivo:
                # URL firmada (MinIO/S3)
                url_archivo = doc.ultima_revision.archivo.url
                
                # Proxy local (Django)
                from django.urls import reverse
                url_path = reverse('documentos:documento_proxy_pdf', kwargs={'doc_id': doc.id})
                url_archivo_proxy = request.build_absolute_uri(url_path)
            else:
                url_archivo = ""
                url_archivo_proxy = ""
        except Exception as e:
            url_archivo = ""
            url_archivo_proxy = ""
            print(f"Error generando URLs de archivo: {e}")
            
        data = {
            'id': doc.id,
            'codigo': doc.codigo,
            'titulo': doc.titulo,
            'tipo': doc.tipo_documento.nombre if doc.tipo_documento else "S/T",
            'disciplina': doc.disciplina.nombre if doc.disciplina else "N/A",
            'estado': doc.estado_actual,
            'responsable_id': doc.responsable_id,
            'responsable_nombre': doc.responsable.get_full_name() or doc.responsable.username if doc.responsable else "No asignado",
            'fecha_creacion': doc.creado_en.strftime('%d/%m/%Y') if doc.creado_en else "N/A",
            'fecha_documento': doc.fecha_inicio.isoformat() if doc.fecha_inicio else "",
            'url_archivo': url_archivo,
            'url_archivo_proxy': url_archivo_proxy,
            'metadatos': metadatos,
            'comentarios': comentarios,
            'usuarios_disponibles': usuarios,
            'contenido_texto': doc.contenido_texto,
            'traceability': {
                'parent': {
                    'id': doc.respuesta_a.id,
                    'codigo': doc.respuesta_a.codigo,
                    'titulo': doc.respuesta_a.titulo
                } if doc.respuesta_a else None,
                'children': [
                    {
                        'id': r.id,
                        'codigo': r.codigo,
                        'titulo': r.titulo
                    } for r in doc.respuestas.all()
                ]
            }
        }
        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_POST
def test_n8n_ping(request):
    """
    Endpoint simple para probar conectividad con n8n.
    """
    try:
        n8n_url = settings.N8N_EXTRACT_TEXTO_WEBHOOK_URL
        payload = {'test': True, 'message': 'Ping desde Django Local', 'timestamp': str(datetime.datetime.now())}
        
        response = requests.post(n8n_url, json=payload, timeout=5)
        
        return JsonResponse({
            'status': 'ok', 
            'n8n_status': response.status_code,
            'n8n_response': response.text[:200]
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_POST
def trigger_n8n_extraction(request, doc_id):
    """
    Dispara el webhook de n8n para extraer texto del PDF.
    Envía el ID del documento y la URL del archivo.
    """
    try:
        doc = get_object_or_404(Documento, id=doc_id)
        
        if not doc.ultima_revision or not doc.ultima_revision.archivo:
             return JsonResponse({'error': 'El documento no tiene archivo asociado'}, status=400)

        # URL del webhook para extracción de texto
        import os
        webhook_path = 'webhook/process-document' if getattr(settings, 'IS_LOCAL', False) else 'webhook/process-document'
        
        # En producción n8n no es localhost, usualmente es http://energy-n8n:5678 o similar
        # Intentar tomar de variables de entorno de extracción específicas, si no, fallback a N8N_BASE_URL genérico
        n8n_url = os.environ.get(
            'N8N_EXTRACT_TEXTO_WEBHOOK_URL', 
            f"{getattr(settings, 'N8N_BASE_URL', 'http://localhost:5678')}/{webhook_path}"
        )
        
        # Enviar payload a n8n
        payload = {
            'documento_id': doc.id,
            'codigo': doc.codigo, # Mantener el código
            'filepath': doc.ultima_revision.archivo.name, # Para que n8n lo baje de S3/MinIO
            'callback_url': f"{settings.INTERNAL_SITE_URL}/documentos/api/update-texto/{doc.id}/" # Donde n8n responderá
        }
        
        # Opcional: Ejecutar asíncronamente con Celery si tarda mucho, 
        # pero aquí solo disparamos el webhook, debería ser rápido.
        try:
            resp = requests.post(n8n_url, json=payload, timeout=10)
            if resp.status_code >= 400:
                import logging
                logging.getLogger(__name__).error(f"Error HTTP devolviendo de n8n {resp.status_code}: {resp.text}")
                return JsonResponse({'error': f'El servidor n8n devolvió un error {resp.status_code}: {resp.text}'}, status=resp.status_code)
        except Exception as e:
             import logging
             logging.getLogger(__name__).error(f"Error de conexión con n8n en extraccion de texto: {str(e)}")
             return JsonResponse({'error': f"Error conectando con n8n: {str(e)}"}, status=500)

        return JsonResponse({'status': 'ok', 'message': 'Solicitud de extracción enviada'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_POST
def api_analizar_oficios_trazabilidad(request, doc_id):
    """
    Recopila la trazabilidad de un oficio (cadena de respuestas), extrae metadatos
    y texto, y lo envía a n8n para su análisis.
    """
    try:
        documento = get_object_or_404(Documento, id=doc_id)
        
        # 1. Encontrar la raíz
        root = documento
        visited = {root.id}
        while root.respuesta_a:
            if root.respuesta_a.id in visited:
                break
            root = root.respuesta_a
            visited.add(root.id)
            
        # 2. Recopilar cadena
        cadena = []
        def recopilar(doc):
            metadatos_qs = doc.metadatos_valores.all().select_related('config')
            metadatos_dict = {}
            for mv in metadatos_qs:
                valor = str(mv.objeto_vinculado) if mv.objeto_vinculado else mv.valor
                metadatos_dict[mv.config.etiqueta] = valor

            # Limpiar y limitar el texto para no abrumar a la IA (Adaptado para GROQ max 12000 TPM limit)
            texto = doc.contenido_texto or ""
            if texto:
                # Quitar espacios múltiples y saltos de línea excesivos
                import re
                texto = re.sub(r'\s+', ' ', texto).strip()
                # Limitar a ~400 palabras máximo por documento (aprox 500 tokens)
                palabras = texto.split()
                if len(palabras) > 400:
                    texto = " ".join(palabras[:400]) + "... [TEXTO TRUNCADO POR LÍMITE DE TOKENS]"

            cadena.append({
                'codigo': doc.codigo,
                'titulo': doc.titulo,
                'estado': doc.estado_actual,
                'fecha': doc.fecha_inicio.isoformat() if doc.fecha_inicio else None,
                'texto_extraido': texto
            })
            for hijo in doc.respuestas.all().order_by('fecha_inicio'):
                recopilar(hijo)
                
        recopilar(root)
        
        payload = {
            'documento_origen_id': doc_id,
            'cadena_oficios': cadena
        }
        
        # URL del webhook
        webhook_path = 'webhook/analizar-oficios' if getattr(settings, 'IS_LOCAL', False) else 'webhook/analizar-oficios'
        # Usamos N8N_BASE_URL que en local por el script tunneler es apuntado al port 5678
        import os
        n8n_url = os.environ.get('N8N_ANALIZAR_OFICIOS_WEBHOOK_URL', f"{getattr(settings, 'N8N_BASE_URL', 'http://localhost:5678')}/{webhook_path}")
        
        resp = requests.post(n8n_url, json=payload, timeout=90) # Aumentado a 90s para darle tiempo a la IA a pensar
        
        if resp.status_code >= 400:
            import logging
            logging.getLogger(__name__).error(f"Error n8n analizar-oficios {resp.status_code}: {resp.text}")
            return JsonResponse({'error': f'n8n HTTP {resp.status_code}: {resp.text}'}, status=resp.status_code)
            
        try:
            n8n_response = resp.json()
        except:
            n8n_response = resp.text
            
        return JsonResponse({'status': 'ok', 'message': 'Oficios enviados a analizar con éxito.', 'n8n_response': n8n_response})
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error en api_analizar_oficios_trazabilidad: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_POST
def api_analizar_biblioteca_ia(request, bib_id):
    """
    Recopila todos los documentos de una biblioteca y los envía a n8n para
    generar un resumen o historiograma que se guarda en el campo resumen_ia.
    """
    try:
        from .models import Biblioteca
        biblioteca = get_object_or_404(Biblioteca, id=bib_id)
        
        # Recopilar documentos de la biblioteca
        cadena = []
        for doc in biblioteca.documentos.all():
            metadatos_qs = doc.metadatos_valores.all().select_related('config')
            metadatos_dict = {}
            for mv in metadatos_qs:
                valor = str(mv.objeto_vinculado) if mv.objeto_vinculado else mv.valor
                metadatos_dict[mv.config.etiqueta] = valor

            # Limpiar y limitar el texto drásticamente para no exceder los límites
            # de las capas gratuitas (ej. Groq: 12,000 Tokens Por Minuto)
            texto = doc.contenido_texto or ""
            if texto:
                import re
                texto = re.sub(r'\s+', ' ', texto).strip()
                palabras = texto.split()
                # Reducimos de 1500 a 350 palabras (~500 tokens). La IA igual entenderá la idea principal de un oficio común en su primer y segundo párrafo.
                if len(palabras) > 400:
                    texto = " ".join(palabras[:400]) + "... [TRUNCADO PARA AHORRAR TOKENS]"

            # Recopilar trazabilidad (hijos) del documento actua
            respuestas_info = []
            for resp_doc in doc.respuestas.all().order_by('fecha_inicio'):
                respuestas_info.append({
                    'id': resp_doc.id,
                    'codigo': resp_doc.codigo,
                    'estado': resp_doc.estado_actual
                })

            cadena.append({
                'id': doc.id,
                'codigo': doc.codigo,
                'titulo': doc.titulo,
                'fecha': doc.fecha_inicio.isoformat() if doc.fecha_inicio else None,
                'texto_extraido': texto, # Ahora muy corto
                'trazabilidad_hijos': respuestas_info 
            })
            
        # Recopilar comentarios/notas de la biblioteca (Insumo IA)
        comentarios_ia = []
        for com in biblioteca.comentarios.all():
            comentarios_ia.append({
                'titulo': com.titulo,
                'contenido': com.contenido,
                'fecha': com.fecha.strftime('%d/%m/%Y')
            })
            
        payload = {
            'biblioteca_id': biblioteca.id,
            'biblioteca_nombre': biblioteca.nombre,
            'biblioteca_descripcion': biblioteca.descripcion,
            'comentarios_adicionales': comentarios_ia, # Insumo extra solicitado por usuario
            'cadena_oficios': cadena # Se usa la misma estructura para simplificar en n8n
        }
        
        import os
        webhook_path = 'webhook/analizar-biblioteca' if getattr(settings, 'IS_LOCAL', False) else 'webhook/analizar-biblioteca'
        n8n_url = os.environ.get('N8N_ANALIZAR_BIBLIOTECA_WEBHOOK_URL', f"{getattr(settings, 'N8N_BASE_URL', 'http://localhost:5678')}/{webhook_path}")
        
        resp = requests.post(n8n_url, json=payload, timeout=90) # Aumentado a 90s para peticiones largas a Groq/OpenAI
        
        if resp.status_code >= 400:
            import logging
            logging.getLogger(__name__).error(f"Error n8n analizar-biblioteca {resp.status_code}: {resp.text}")
            return JsonResponse({'error': f'n8n HTTP {resp.status_code}: {resp.text}'}, status=resp.status_code)
            
        try:
            n8n_response = resp.json()
            mdText = n8n_response.get('message', '') or n8n_response.get('text', '') or n8n_response.get('texto_redactado', '') or n8n_response
        except:
            mdText = resp.text
            n8n_response = resp.text
            
        # Actualizamos el campo resumen en base de datos
        if mdText and isinstance(mdText, str):
            biblioteca.resumen_ia = mdText
            biblioteca.save(update_fields=['resumen_ia'])
            
        return JsonResponse({'status': 'ok', 'message': 'Biblioteca analizada con éxito.', 'n8n_response': n8n_response, 'resumen_ia': mdText})

    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error en api_analizar_biblioteca_ia: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_POST
def update_documento_texto(request, doc_id):
    """
    API endpoint para que n8n actualice el contenido_texto del documento.
    """
    try:
        doc = get_object_or_404(Documento, id=doc_id)
        data = json.loads(request.body)
        
        texto = data.get('texto')
        if texto:
            doc.contenido_texto = texto
            doc.save()
            
            # Disparar generación de embedding vectorial (pgvector)
            from .tasks import generate_document_embedding
            generate_document_embedding.delay(doc.id)
            
            return JsonResponse({'status': 'ok'})
        
        return JsonResponse({'error': 'No se recibió texto'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_POST
def callback_n8n_procesamiento(request, revision_id):
    """
    Callback para que n8n devuelva los resultados del procesamiento (Conversión PDF + Metadatos IA).
    Actualiza la revisión y el documento maestro.
    """
    try:
        revision = get_object_or_404(Revision, id=revision_id)
        data = json.loads(request.body)
        
        # 1. Actualizar PDF si n8n lo convirtió/optimizó
        # Nota: n8n debería enviar una URL o el contenido base64 si es pequeño, 
        # pero idealmente n8n lo sube directo a S3 y aquí solo recibimos el path.
        pdf_path = data.get('pdf_path')
        if pdf_path:
            revision.archivo.name = pdf_path
        
        # 2. Actualizar Metadatos Extraídos
        metadatos_ia = data.get('metadatos', {})
        if not revision.datos_extraidos:
            revision.datos_extraidos = {}
            
        if metadatos_ia:
            revision.datos_extraidos['ia_metadata'] = metadatos_ia
            
            # Si n8n sugiere un código o título, guardarlos para que el wizard los tome
            if metadatos_ia.get('codigo'):
                revision.datos_extraidos['suggested_code'] = metadatos_ia.get('codigo')
            if metadatos_ia.get('titulo'):
                revision.datos_extraidos['suggested_title'] = metadatos_ia.get('titulo')

        # 3. Actualizar contenido de texto completo
        texto_completo = data.get('texto_completo')
        if texto_completo:
            revision.documento.contenido_texto = texto_completo
            revision.documento.save()
            
            # Guardar también en la revisión para el visor del Wizard
            revision.datos_extraidos['text_preview'] = texto_completo[:5000]
            
            # Disparar generación de embedding vectorial (pgvector)
            from .tasks import generate_document_embedding
            generate_document_embedding.delay(revision.documento.id)

        revision.estado_extraccion = 'COMPLETADO'
        revision.save()
        
        return JsonResponse({'status': 'ok', 'message': 'Resultados procesados correctamente'})
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error en callback_n8n_procesamiento: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_POST
def documento_comentar(request, doc_id):
    """
    Agrega un comentario (pin) a un documento.
    """
    try:
        doc = get_object_or_404(Documento, id=doc_id)
        if request.content_type == 'application/json':
            data = json.loads(request.body)
            texto = data.get('texto')
            pos_x = float(data.get('x', 0))
            pos_y = float(data.get('y', 0))
            pagina = int(data.get('pagina', 1))
            tipo = data.get('tipo', 'PIN')
            ancho = float(data.get('ancho', 0))
            alto = float(data.get('alto', 0))
            responsable_id = data.get('responsable_id')
            vinculo_id = data.get('vinculo_id')
        else:
            # Manejar multipart/form-data
            texto = request.POST.get('texto')
            pos_x = float(request.POST.get('x', 0))
            pos_y = float(request.POST.get('y', 0))
            pagina = int(request.POST.get('pagina', 1))
            tipo = request.POST.get('tipo', 'PIN')
            ancho = float(request.POST.get('ancho', 0))
            alto = float(request.POST.get('alto', 0))
            responsable_id = request.POST.get('responsable_id')
            vinculo_id = request.POST.get('vinculo_id')
        
        if not texto:
            return JsonResponse({'error': 'Comentario vacío'}, status=400)
            
        # Asignar responsable si viene en el request
        responsable = None
        if responsable_id:
             try:
                 from django.contrib.auth.models import User
                 responsable = User.objects.get(id=responsable_id)
             except (User.DoesNotExist, ValueError):
                 pass

        comentario = ComentarioDocumento.objects.create(
            documento=doc,
            revision=doc.ultima_revision,
            usuario=request.user,
            responsable=responsable,
            texto=texto,
            tipo=tipo,
            posicion_x=pos_x,
            posicion_y=pos_y,
            ancho=ancho,
            alto=alto,
            pagina=pagina
        )


        # Procesar imágenes
        imagenes = request.FILES.getlist('imagenes')
        for img in imagenes:
            ComentarioImagen.objects.create(comentario=comentario, imagen=img)
        
        # Procesar vínculos si existen
        if vinculo_id:
            try:
                pin_origen = ComentarioDocumento.objects.get(id=vinculo_id)
                comentario.vinculos.add(pin_origen)
                # Al ser symmetrical=True, se añade automáticamente en el otro lado
            except ComentarioDocumento.DoesNotExist:
                pass
        
        return JsonResponse({
            'status': 'success',
            'comentario': {
                'id': comentario.id,
                'texto': comentario.texto,
                'usuario': comentario.usuario.username,
                'fecha': comentario.creado_en.strftime('%d/%m/%Y %H:%M'),
                'x': comentario.posicion_x,
                'y': comentario.posicion_y,
                'ancho': comentario.ancho,
                'alto': comentario.alto,
                'tipo': comentario.tipo,
                'pagina': comentario.pagina,
                'responsable_id': comentario.responsable.id if comentario.responsable else None,
                'responsable_nombre': comentario.responsable.get_full_name() or comentario.responsable.username if comentario.responsable else None,
                'vinculos': [{'id': v.id, 'doc_id': v.documento.id, 'doc_codigo': v.documento.codigo} for v in comentario.vinculos.all()],
                'imagenes': [request.build_absolute_uri(img.imagen.url) for img in comentario.imagenes.all()]
            }
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_POST
def documento_eliminar_comentario(request, comentario_id):
    """
    Elimina un comentario específico.
    Solo el autor o un superusuario pueden eliminarlo.
    """
    try:
        comentario = get_object_or_404(ComentarioDocumento, id=comentario_id)
        
        # Validar permisos
        if comentario.usuario != request.user and not request.user.is_superuser:
            return JsonResponse({'error': 'No tiene permiso para eliminar este comentario'}, status=403)
            
        comentario.delete()
        
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_POST
def documento_editar_comentario(request, comentario_id):
    """
    Edita el texto o responsable de un comentario existente.
    """
    try:
        comentario = get_object_or_404(ComentarioDocumento, id=comentario_id)
        
        # Validar permisos (autor o superusuario para editar texto, quizás responsable para asignar)
        # Por ahora simple: solo autor o admin
        if comentario.usuario != request.user and not request.user.is_superuser:
             return JsonResponse({'error': 'No tiene permiso para editar este comentario'}, status=403)

        data = json.loads(request.body)
        texto = data.get('texto')
        responsable_id = data.get('responsable_id')
        
        # Actualizar texto
        if texto:
            comentario.texto = texto
            
        # Actualizar responsable (puede ser null/None para desasignar)
        if 'responsable_id' in data: # Solo si viene en el payload explícitamente
            if responsable_id:
                try:
                    from django.contrib.auth.models import User
                    user = User.objects.get(id=responsable_id)
                    comentario.responsable = user
                except User.DoesNotExist:
                     comentario.responsable = None
            else:
                comentario.responsable = None

        comentario.save()
        
        return JsonResponse({
            'status': 'success',
            'comentario': {
                'id': comentario.id,
                'texto': comentario.texto,
                'usuario': comentario.usuario.username,
                'fecha': comentario.creado_en.strftime('%d/%m/%Y %H:%M'),
                'x': comentario.posicion_x,
                'y': comentario.posicion_y,
                'pagina': comentario.pagina,
                'resuelto': comentario.resuelto,
                'responsable_id': comentario.responsable.id if comentario.responsable else None,
                'responsable_nombre': comentario.responsable.get_full_name() or comentario.responsable.username if comentario.responsable else None,
            }
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_POST
def documento_actualizar_estado(request, doc_id):
    """
    Actualiza el estado de un documento.
    """
    try:
        doc = get_object_or_404(Documento, id=doc_id)
        data = json.loads(request.body)
        nuevo_estado = data.get('estado')
        
        valid_states = [s[0] for s in Documento.ESTADOS]
        if nuevo_estado not in valid_states:
            return JsonResponse({'error': 'Estado inválido'}, status=400)
            
        doc.estado_actual = nuevo_estado
        doc.save()
        
        return JsonResponse({'status': 'success', 'nuevo_estado': doc.get_estado_actual_display()})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_POST
def documento_actualizar_responsable(request, doc_id):
    """
    Actualiza el responsable de un documento.
    """
    try:
        doc = get_object_or_404(Documento, id=doc_id)
        data = json.loads(request.body)
        user_id = data.get('responsable_id')
        
        if user_id:
            user = get_object_or_404(User, id=user_id)
            doc.responsable = user
        else:
            doc.responsable = None
            
        doc.save()
        
        nombre = doc.responsable.get_full_name() or doc.responsable.username if doc.responsable else "No asignado"
        return JsonResponse({'status': 'success', 'nuevo_responsable': nombre})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_POST
def documento_actualizar_fecha(request, doc_id):
    """
    Actualiza la fecha de inicio/emisión de un documento.
    """
    try:
        doc = get_object_or_404(Documento, id=doc_id)
        data = json.loads(request.body)
        nueva_fecha_str = data.get('fecha')
        
        if nueva_fecha_str:
            try:
                nueva_fecha = datetime.datetime.strptime(nueva_fecha_str, '%Y-%m-%d').date()
                doc.fecha_inicio = nueva_fecha
            except ValueError:
                return JsonResponse({'error': 'Formato de fecha inválido (YYYY-MM-DD)'}, status=400)
        else:
            doc.fecha_inicio = None
            
        doc.save()
        
        return JsonResponse({
            'status': 'success', 
            'nueva_fecha': doc.fecha_inicio.strftime('%d/%m/%Y') if doc.fecha_inicio else "N/A"
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def documento_buscar(request):
    """
    Busca documentos por código, título o contenido del PDF.
    Usa búsqueda de texto completo para el contenido.
    """
    q = request.GET.get('q', '')
    if len(q) < 3:
        return JsonResponse([], safe=False)
    
    from django.contrib.postgres.search import TrigramSimilarity
    from django.db.models import Q, F
    
    # Búsqueda en código y título (exacta)
    docs_exactos = Documento.objects.filter(
        Q(codigo__icontains=q) | Q(titulo__icontains=q)
    ).values('id', 'codigo', 'titulo')[:10]
    
    # Búsqueda en contenido (si no hay resultados exactos)
    if len(docs_exactos) < 5:
        # Usar trigram similarity para búsqueda fuzzy en contenido
        docs_contenido = Documento.objects.annotate(
            similarity=TrigramSimilarity('contenido_texto', q),
        ).filter(
            similarity__gt=0.1  # Umbral de similitud
        ).order_by('-similarity').values('id', 'codigo', 'titulo')[:5]
        
        # Combinar resultados
        resultados = list(docs_exactos) + [d for d in docs_contenido if d not in docs_exactos]
        return JsonResponse(resultados[:10], safe=False)
    
    return JsonResponse(list(docs_exactos), safe=False)

@login_required
def documento_busqueda_avanzada(request):
    """
    Búsqueda avanzada de documentos con múltiples filtros.
    """
    # Obtener parámetros de búsqueda
    q = request.GET.get('q', '').strip()
    tipo_id = request.GET.get('tipo')
    disciplina_id = request.GET.get('disciplina')
    estado = request.GET.get('estado')
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    buscar_contenido = request.GET.get('buscar_contenido', 'false') == 'true'
    
    from django.contrib.postgres.search import TrigramSimilarity
    from django.db.models import Q
    
    # Iniciar queryset
    docs = Documento.objects.all()
    
    # Filtro por texto (código, título, o contenido)
    if q and len(q) >= 3:
        if buscar_contenido:
            # Búsqueda en contenido: Código, Título o Subcadena en texto
            # Usamos icontains para asegurar que si la palabra existe se encuentre, 
            # y TrigramSimilarity solo para ordenar por relevancia.
            docs = docs.annotate(
                similarity=TrigramSimilarity('contenido_texto', q)
            ).filter(
                Q(codigo__icontains=q) | 
                Q(titulo__icontains=q) | 
                Q(contenido_texto__icontains=q)
            ).order_by('-similarity')
        else:
            # Solo código y título
            docs = docs.filter(
                Q(codigo__icontains=q) | Q(titulo__icontains=q)
            )

    
    # Filtros adicionales
    if tipo_id:
        docs = docs.filter(tipo_documento_id=tipo_id)
    
    if disciplina_id:
        docs = docs.filter(disciplina_id=disciplina_id)
    
    if estado:
        docs = docs.filter(estado_actual=estado)
    
    if fecha_desde:
        docs = docs.filter(creado_en__gte=fecha_desde)
    
    if fecha_hasta:
        docs = docs.filter(creado_en__lte=fecha_hasta)
    
    # Paginación
    from django.core.paginator import Paginator
    paginator = Paginator(docs.select_related('tipo_documento', 'disciplina', 'responsable'), 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Preparar contexto
    context = {
        'page_obj': page_obj,
        'tipos': TipoDocumento.objects.all(),
        'disciplinas': Disciplina.objects.all(),
        'estados': Documento.ESTADOS,
        'query': q,
        'tipo_id': tipo_id,
        'disciplina_id': disciplina_id,
        'estado': estado,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'buscar_contenido': buscar_contenido,
    }
    
    return render(request, 'documentos/busqueda_avanzada.html', context)


@login_required
def documento_proxy_pdf(request, doc_id):
    """
    Proxy para servir el PDF evitando problemas de CORS y expiración de firmas en MinIO.
    Usa el motor de almacenamiento directamente para mayor confiabilidad.
    """
    from django.http import FileResponse, Http404
    import logging
    logger = logging.getLogger(__name__)

    doc = get_object_or_404(Documento, id=doc_id)
    if not doc.ultima_revision or not doc.ultima_revision.archivo:
        logger.warning(f"Intento de acceso a proxy PDF sin archivo: Doc {doc_id}")
        raise Http404("Documento sin archivo")
    
    try:
        # Abrir el archivo usando el driver de almacenamiento (S3/MinIO)
        archivo = doc.ultima_revision.archivo
        
        # Verificar si el archivo existe físicamente en el storage
        if not archivo.storage.exists(archivo.name):
            logger.error(f"Archivo no encontrado en storage: {archivo.name}")
            raise Http404("Archivo no encontrado en el servidor de almacenamiento")

        file_handle = archivo.open('rb')
        
        response = FileResponse(file_handle, content_type='application/pdf')
        # Content-Disposition inline permite ver en el navegador sin descargar forzosamente
        response['Content-Disposition'] = f'inline; filename="{doc.codigo}.pdf"'
        
        # Headers de seguridad y CORS para PDF.js y visores modernos
        response["Access-Control-Allow-Origin"] = "*"
        response["X-Frame-Options"] = "SAMEORIGIN"
        response["Content-Security-Policy"] = "frame-ancestors 'self'"
        
        return response
    except Exception as e:
        logger.error(f"Error crítico en documento_proxy_pdf para doc {doc_id}: {str(e)}", exc_info=True)
        raise Http404(f"Error al servir el PDF: {str(e)}")

@csrf_exempt
@require_POST
def documento_chat_ia(request):
    """
    Proxy para comunicar el chat del frontend con el webhook de n8n interno.
    Inyecta el contenido de texto del documento para que la IA tenga contexto.
    """
    try:
        data = json.loads(request.body)
        
        # Inyectar contenido de texto si tenemos el ID del documento
        doc_id = data.get('documento_id')
        if doc_id:
            try:
                # Buscar documento y obtener contenido
                # Usamos only() para optimizar si el contenido es grande
                doc = Documento.objects.only('contenido_texto').get(id=doc_id)
                
                # Agregar contenido al payload
                # Si contenido_texto es None, enviamos cadena vacía o indicamos que no hay texto
                data['contenido_texto'] = doc.contenido_texto if doc.contenido_texto else ""
                
                print(f"Inyectado texto de documento {doc_id} (longitud: {len(data['contenido_texto'])})")
            except Documento.DoesNotExist:
                print(f"Documento ID {doc_id} no encontrado para inyectar texto")
            except Exception as e:
                print(f"Error al inyectar texto: {str(e)}")

        # Obtener URL desde settings
        n8n_url = settings.N8N_CHAT_WEBHOOK_URL
        
        # LOGGING DE DEBUG (Importante para producción)
        print(f"-------- DEBUG PROXY AI CHAT --------")
        print(f"Target URL: {n8n_url}")
        print(f"Payload keys: {list(data.keys())}")
        
        # Timeout aumentado para dar tiempo a la IA de responder
        # Enviamos 'data' que ahora incluye 'contenido_texto'
        response = requests.post(f"{n8n_url}", json=data, timeout=60)
        
        if response.status_code == 200:
            return JsonResponse(response.json())
        else:
            print(f"Error n8n Status: {response.status_code}")
            print(f"Error n8n Body: {response.text}")
            logger = logging.getLogger(__name__)
            logger.error(f"Error n8n ({response.status_code}): {response.text}")
            return JsonResponse({'error': f'Error en n8n: {response.text}'}, status=response.status_code)
            
    except requests.exceptions.ConnectionError as e:
        print(f"ConnectionError: {str(e)}")
        logger = logging.getLogger(__name__)
        logger.error(f"ConnectionError a n8n: {settings.N8N_CHAT_WEBHOOK_URL} - {str(e)}")
        return JsonResponse({'error': f'No se pudo conectar con n8n. Verifique la URL y que el servicio esté activo. Detalle: {str(e)}'}, status=503)
    except Exception as e:
        print(f"Exception General: {str(e)}")
        logger = logging.getLogger(__name__)
        logger.error(f"Excepcion en chat IA: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)
@login_required
def documento_sync_metadatos(request, doc_id):
    """
    Sincroniza los metadatos de un documento con la configuración actual
    del su TipoDocumento. Crea registros vacíos para campos faltantes.
    """
    from django.contrib import messages
    from django.shortcuts import redirect
    from django.conf import settings
    from .models import MetadatoValor
    import requests
    
    doc = get_object_or_404(Documento, id=doc_id)
    configs = MetadatoConfig.objects.filter(tipo_documento=doc.tipo_documento)
    
    creados = 0
    for config in configs:
        obj, created = MetadatoValor.objects.get_or_create(
            documento=doc,
            config=config,
            defaults={'valor': ''}
        )
        if created:
            creados += 1
            
    # 1. Informar sobre campos creados
    if creados > 0:
        messages.success(request, f"Se generaron {creados} campos de metadatos nuevos.")
    
    # 2. Enviar webhook a n8n para extracción con IA
    webhook_url = getattr(settings, 'N8N_METADATA_SYNC_WEBHOOK', None)
    if webhook_url:
        try:
            # Obtener URL del archivo en S3/MinIO
            file_url = ''
            file_path = ''
            try:
                if doc.ultima_revision and doc.ultima_revision.archivo:
                    file_url = doc.ultima_revision.archivo.url
                    file_path = doc.ultima_revision.archivo.name
            except Exception:
                pass

            payload = {
                'documento_id': doc.id,
                'codigo': doc.codigo,
                'titulo': doc.titulo,
                'tipo_documento': doc.tipo_documento.nombre,
                'campos_nuevos': creados,
                'file_url': file_url,
                'file_path': file_path,
                'metadatos': [
                    {'nombre': mv.config.nombre, 'etiqueta': mv.config.etiqueta, 'valor': mv.valor}
                    for mv in doc.metadatos_valores.select_related('config').all()
                ],
                'url_admin': f"{settings.INTERNAL_SITE_URL}/admin/documentos/documento/{doc.id}/change/"
            }
            resp = requests.post(webhook_url, json=payload, timeout=10)
            import logging
            logging.getLogger(__name__).info(f"Webhook n8n enviado para doc {doc.codigo}: status={resp.status_code}")
            messages.info(request, "🤖 Extracción IA enviada a n8n. Los metadatos se llenarán automáticamente en unos segundos.")
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Error enviando webhook n8n: {str(e)}")
            messages.warning(request, f"⚠️ No se pudo conectar con n8n: {str(e)}")
    else:
        if creados == 0:
            messages.info(request, "Los metadatos ya están sincronizados.")
        
    return redirect(f'/admin/documentos/documento/{doc_id}/change/')
@login_required
def api_bibliotecas_list(request, doc_id):
    """
    Retorna la lista de bibliotecas y si el documento pertenece a ellas.
    """
    from .models import Biblioteca
    documento = get_object_or_404(Documento, id=doc_id)
    bibliotecas = Biblioteca.objects.all().order_by('nombre')
    
    data = []
    for b in bibliotecas:
        data.append({
            'id': b.id,
            'nombre': b.nombre,
            'descripcion': b.descripcion or "",
            'pertenece': b.documentos.filter(id=doc_id).exists(),
            'count': b.documentos.count()
        })
    
    return JsonResponse({'status': 'success', 'bibliotecas': data})

@require_POST
@login_required
def api_biblioteca_toggle(request, doc_id, bib_id):
    """
    Agrega o quita un documento de una biblioteca.
    """
    from .models import Biblioteca
    documento = get_object_or_404(Documento, id=doc_id)
    biblioteca = get_object_or_404(Biblioteca, id=bib_id)
    
    if biblioteca.documentos.filter(id=doc_id).exists():
        biblioteca.documentos.remove(documento)
        accion = 'removido'
    else:
        biblioteca.documentos.add(documento)
        accion = 'agregado'
        
    return JsonResponse({
        'status': 'success', 
        'accion': accion,
        'count': biblioteca.documentos.count()
    })

@login_required
def api_biblioteca_documentos(request, bib_id):
    """
    Lista documentos y marca los que pertenecen a esta biblioteca.
    """
    try:
        from .models import Biblioteca, Documento
        biblioteca = get_object_or_404(Biblioteca, id=bib_id)
        
        query = request.GET.get('q', '')
        documentos = Documento.objects.all()
        if query:
            documentos = documentos.filter(
                models.Q(codigo__icontains=query) | 
                models.Q(titulo__icontains=query)
            )
        
        documentos = documentos.order_by('-actualizado_en')[:100]
        docs_en_bib = set(biblioteca.documentos.values_list('id', flat=True))
        
        data = []
        for d in documentos:
            data.append({
                'id': d.id,
                'codigo': d.codigo,
                'titulo': d.titulo,
                'pertenece': d.id in docs_en_bib,
                'tipo': d.tipo_documento.nombre if d.tipo_documento else ""
            })
        
        return JsonResponse({'status': 'success', 'documentos': data})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
def biblioteca_visualizar(request, bib_id):
    """
    Vista profesional para visualizar todos los documentos de una biblioteca.
    """
    from .models import Biblioteca
    biblioteca = get_object_or_404(Biblioteca, id=bib_id)
    documentos = biblioteca.documentos.all().select_related('tipo_documento', 'respuesta_a').order_by('-actualizado_en')
    
    # Construir listado de trazabilidad jerárquica
    # Encontrar doc "raíces" (los que no responden a ningún otro en esta biblioteca)
    doc_ids_en_bib = set(doc.id for doc in documentos)
    cadenas_trazabilidad = []
    
    # Función recursiva para armar la cadena visual
    def build_chain(doc):
        fecha_str = doc.fecha_inicio.strftime('%d/%m/%Y') if doc.fecha_inicio else 'Sin fecha'
        chain = [{
            'codigo': doc.codigo,
            'fecha': fecha_str,
            'id': doc.id
        }]
        
        # Buscar respuestas inmediatas que también pertenezcan a esta biblioteca
        hijos_en_bib = [h for h in doc.respuestas.all().order_by('fecha_inicio') if h.id in doc_ids_en_bib]
        
        if hijos_en_bib:
             # Por simplicidad en la UI lineal, tomamos el primer hijo directo para la cadena principal
             # Si hay múltiples respuestas se podría ramificar, pero el ejemplo del usuario es lineal: A -> B -> C
             chain.extend(build_chain(hijos_en_bib[0]))
        return chain

    docs_raiz = [d for d in documentos if not d.respuesta_a or d.respuesta_a.id not in doc_ids_en_bib]
    
    for raiz in docs_raiz:
        cadena = build_chain(raiz)
        if len(cadena) > 0:
            cadenas_trazabilidad.append(cadena)

    return render(request, 'documentos/biblioteca_visualizar.html', {
        'biblioteca': biblioteca,
        'documentos': documentos,
        'comentarios': biblioteca.comentarios.all().order_by('-fecha'),
        'cadenas_trazabilidad': cadenas_trazabilidad,
        'estados': Documento.ESTADOS
    })

@require_POST
@login_required
def api_documento_update_status(request, doc_id):
    """
    Actualiza el estado de un documento via AJAX.
    """
    documento = get_object_or_404(Documento, id=doc_id)
    nuevo_estado = request.POST.get('estado')
    
    valid_status = [s[0] for s in Documento.ESTADOS]
    if nuevo_estado in valid_status:
        documento.estado_actual = nuevo_estado
        documento.save()
        return JsonResponse({'status': 'success', 'nuevo_estado': nuevo_estado})
    
    return JsonResponse({'status': 'error', 'message': 'Estado inválido'}, status=400)

@login_required
def api_documento_busqueda_vectorial(request):
    """
    Motor de Búsqueda Híbrido:
    1. Búsqueda por Texto Exacto (Código/Título) -> Alta prioridad
    2. Búsqueda Vectorial (Semántica) en fragmentos vía Gemini -> Cobertura conceptual
    3. Fusión de resultados sin duplicados
    """
    from django.conf import settings
    import google.generativeai as genai
    from pgvector.django import CosineDistance
    from django.db.models import Q
    from .models import DocumentoFragmento, Documento
    
    query = request.GET.get('q', '').strip()
    if not query:
        return JsonResponse({'status': 'success', 'documentos': []})
        
    try:
        resultados_dict = {} # Map ID -> dict con datos fusionados
        
        # --- FASE 1: BÚSQUEDA POR TEXTO (EXACTA/MODO RÁPIDO) ---
        docs_texto = Documento.objects.filter(
            Q(codigo__icontains=query) | Q(titulo__icontains=query)
        )[:10]
        
        for d in docs_texto:
            resultados_dict[d.id] = {
                'id': d.id,
                'codigo': d.codigo,
                'titulo': d.titulo,
                'distancia': 0.01,
                'similitud': 0.99,
                'fragmento_preview': f"Coincidencia directa encontrada en metadatos del documento ({d.codigo})."
            }

        # --- FASE 2: BÚSQUEDA SEMÁNTICA (VECTORIAL VÍA GEMINI) ---
        if settings.GEMINI_API_KEY:
            try:
                genai.configure(api_key=settings.GEMINI_API_KEY)
                # Generar vector para la query
                res = genai.embed_content(
                    model="models/text-embedding-004",
                    content=query,
                    task_type="retrieval_query",
                    output_dimensionality=384
                )
                query_vector = res['embedding']
                
                fragmentos = DocumentoFragmento.objects.select_related('documento').annotate(
                    distance=CosineDistance('embedding', query_vector)
                ).order_by('distance')[:40]

                for f in fragmentos:
                    # Si el documento ya está por texto, no lo pisamos (prioridad a texto)
                    if f.documento_id not in resultados_dict:
                        resultados_dict[f.documento_id] = {
                            'id': f.documento.id,
                            'codigo': f.documento.codigo,
                            'titulo': f.documento.titulo,
                            'distancia': round(float(f.distance), 4),
                            'similitud': round(1 - float(f.distance), 4),
                            'fragmento_preview': f.contenido[:200].strip() + "..."
                        }
            except Exception as ve:
                import logging
                logging.getLogger(__name__).warning(f"Error en fase vectorial Gemini: {str(ve)}")

        # --- FASE 3: ORDENAR Y FORMATEAR ---
        resultados_finales = sorted(resultados_dict.values(), key=lambda x: x['similitud'], reverse=True)
        
        return JsonResponse({'status': 'success', 'documentos': resultados_finales[:15]})
        
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error en busqueda híbrida: {str(e)}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
def api_documento_migrar_embeddings(request):
    """
    Encola tareas de Celery para generar embeddings de todos los documentos
    que tienen texto. Ahora usa la nueva lógica de fragmentos (Chunking).
    """
    if not request.user.is_superuser:
        return JsonResponse({'error': 'No autorizado'}, status=403)
        
    from .tasks import generate_document_embedding
    
    # Procesamos TODOS los documentos con texto para aplicar la nueva arquitectura de fragmentos
    docs_con_texto = Documento.objects.exclude(
        contenido_texto__isnull=True
    ).exclude(contenido_texto='')
    
    count = docs_con_texto.count()
    for d in docs_con_texto:
        generate_document_embedding.delay(d.id)
        
    return JsonResponse({
        'status': 'success', 
        'enqueued': count, 
        'message': f'Se ha iniciado la re-indexación completa de {count} documentos usando la nueva lógica de fragmentos.'
    })

@login_required
def api_documento_vectorize_single(request, doc_id):
    """
    Fuerza la generación de un embedding para un documento específico.
    Útil para probar inmediatamente después de que n8n inserte el texto.
    """
    from .tasks import generate_document_embedding
    doc = get_object_or_404(Documento, id=doc_id)
    
    if not doc.contenido_texto:
        return JsonResponse({'status': 'error', 'message': 'El documento no tiene texto cargado'}, status=400)
        
    generate_document_embedding.delay(doc.id)
    return JsonResponse({'status': 'success', 'message': f'Tarea de vectorización encolada para el documento {doc.id}'})

@login_required
def busqueda_vectorial(request):
    """
    Renderiza la interfaz premium de búsqueda semántica.
    """
    return render(request, 'documentos/busqueda_vectorial.html')
@require_POST
@login_required
def api_actualizar_metadato(request, mv_id):
    """
    Actualiza el valor de un metadato dinámico via AJAX.
    """
    try:
        from .models import MetadatoValor
        import json
        
        mv = get_object_or_404(MetadatoValor, id=mv_id)
        data = json.loads(request.body)
        nuevo_valor = data.get('valor')
        
        # Opcional: Validar según tipo de campo en mv.config
        
        mv.valor = nuevo_valor
        mv.save()
        
        return JsonResponse({
            'status': 'success',
            'nuevo_valor': mv.valor
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@require_POST
@login_required
def api_biblioteca_crear_comentario(request, bib_id):
    """
    Crea un nuevo comentario/nota para una biblioteca via AJAX.
    """
    import json
    from .models import Biblioteca, ComentarioBiblioteca
    try:
        biblioteca = get_object_or_404(Biblioteca, id=bib_id)
        data = json.loads(request.body)
        
        titulo = data.get('titulo', 'Nota sin título')
        contenido = data.get('contenido')
        
        if not contenido:
            return JsonResponse({'status': 'error', 'message': 'El contenido es requerido'}, status=400)
            
        comentario = ComentarioBiblioteca.objects.create(
            biblioteca=biblioteca,
            titulo=titulo,
            contenido=contenido
        )
        
        return JsonResponse({
            'status': 'success',
            'comentario': {
                'id': comentario.id,
                'titulo': comentario.titulo,
                'contenido': comentario.contenido,
                'fecha': comentario.fecha.strftime('%d/%m/%Y %H:%M')
            }
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
