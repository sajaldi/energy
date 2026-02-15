from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.db import models
import json
import requests
from .models import Documento, ComentarioDocumento

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
    
    # 2. Función recursiva para construir el árbol hacia adelante
    def build_tree(doc, current_doc_id):
        children = doc.respuestas.all().select_related('tipo_documento', 'ultima_revision')
        return {
            'id': doc.id,
            'codigo': doc.codigo,
            'titulo': doc.titulo,
            'tipo': doc.tipo_documento.nombre if doc.tipo_documento else "S/T",
            'estado': doc.estado_actual,
            'fecha': doc.creado_en,
            'is_current': doc.id == current_doc_id,
            'hijos': [build_tree(child, current_doc_id) for child in children]
        }
    
    tree = build_tree(root, documento.id)
    
    # 3. Recopilar todos los IDs en el árbol para buscar sus vínculos
    ids_en_arbol = set()
    def collect_ids(node):
        ids_en_arbol.add(node['id'])
        for hijo in node['hijos']:
            collect_ids(hijo)
    collect_ids(tree)
    
    # 4. Buscar vínculos transversales (pines vinculados a otros documentos)
    # Buscamos comentarios de los documentos en el árbol que tengan vinculos
    vinc_comments = ComentarioDocumento.objects.filter(
        models.Q(documento_id__in=ids_en_arbol) | 
        models.Q(vinculos__documento_id__in=ids_en_arbol)
    ).prefetch_related('vinculos__documento', 'vinculos__documento__tipo_documento')
    
    pines_vinculados = []
    docs_externos = {}
    
    seen_links = set()
    for c in vinc_comments:
        for v in c.vinculos.all():
            # Crear par único para evitar duplicados symmetrical
            link_pair = tuple(sorted([c.id, v.id]))
            if link_pair not in seen_links:
                seen_links.add(link_pair)
                pines_vinculados.append({
                    'from_doc': c.documento.id,
                    'to_doc': v.documento.id,
                    'from_code': c.documento.codigo,
                    'to_code': v.documento.codigo
                })
                
                # Si el documento destino no está en el árbol, lo guardamos como externo
                for doc in [c.documento, v.documento]:
                    if doc.id not in ids_en_arbol and doc.id not in docs_externos:
                        docs_externos[doc.id] = {
                            'id': doc.id,
                            'codigo': doc.codigo,
                            'titulo': doc.titulo,
                            'tipo': doc.tipo_documento.nombre if doc.tipo_documento else "S/T",
                            'estado': doc.estado_actual,
                            'fecha': doc.creado_en,
                        }

    from django.contrib.auth.models import User
    context = {
        'documento': documento,
        'tree': tree,
        'root': root,
        'pines_vinculados': pines_vinculados,
        'docs_externos': list(docs_externos.values()),
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
                'etiqueta': mv.config.etiqueta,
                'valor': mv.valor
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
                'vinculos': [{'id': v.id, 'doc_id': v.documento.id, 'doc_codigo': v.documento.codigo} for v in c.vinculos.all()]
            })

        usuarios = list(User.objects.filter(is_active=True).values('id', 'username', 'first_name', 'last_name').order_by('first_name'))

        # Info de archivo
        url_archivo = ""
        try:
            if doc.ultima_revision and doc.ultima_revision.archivo:
                url_archivo = doc.ultima_revision.archivo.url
        except Exception as e:
            url_archivo = f"Error al generar URL: {str(e)}"
            
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
            'url_archivo': url_archivo,
            'metadatos': metadatos,
            'comentarios': comentarios,
            'usuarios_disponibles': usuarios,
        }
        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_POST
def documento_comentar(request, doc_id):
    """
    Agrega un comentario (pin) a un documento.
    """
    try:
        doc = get_object_or_404(Documento, id=doc_id)
        data = json.loads(request.body)
        
        texto = data.get('texto')
        pos_x = float(data.get('x', 0))
        pos_y = float(data.get('y', 0))
        pagina = int(data.get('pagina', 1))
        
        if not texto:
            return JsonResponse({'error': 'Comentario vacío'}, status=400)
            
        # Asignar responsable si viene en el request
        responsable_id = data.get('responsable_id')
        responsable = None
        if responsable_id:
             try:
                 from django.contrib.auth.models import User
                 responsable = User.objects.get(id=responsable_id)
             except User.DoesNotExist:
                 pass

        comentario = ComentarioDocumento.objects.create(
            documento=doc,
            revision=doc.ultima_revision,
            usuario=request.user,
            responsable=responsable,
            texto=texto,
            tipo=data.get('tipo', 'PIN'),
            posicion_x=pos_x,
            posicion_y=pos_y,
            ancho=float(data.get('ancho', 0)),
            alto=float(data.get('alto', 0)),
            pagina=pagina
        )
        
        # Procesar vínculos si existen
        vinculo_id = data.get('vinculo_id')
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
                'vinculos': [{'id': v.id, 'doc_id': v.documento.id, 'doc_codigo': v.documento.codigo} for v in comentario.vinculos.all()]
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
def documento_buscar(request):
    """
    Busca documentos por código o título.
    """
    q = request.GET.get('q', '')
    if len(q) < 3:
        return JsonResponse([], safe=False)
        
    docs = Documento.objects.filter(
        models.Q(codigo__icontains=q) | models.Q(titulo__icontains=q)
    ).values('id', 'codigo', 'titulo')[:10]
    
    return JsonResponse(list(docs), safe=False)

@login_required
def documento_proxy_pdf(request, doc_id):
    """
    Proxy para servir el PDF evitando problemas de CORS con MinIO.
    Usa el motor de almacenamiento directamente para mayor confiabilidad.
    """
    from django.http import FileResponse, Http404

    doc = get_object_or_404(Documento, id=doc_id)
    if not doc.ultima_revision or not doc.ultima_revision.archivo:
        raise Http404("Documento sin archivo")
    
    try:
        # Abrir el archivo usando el driver de almacenamiento (S3/MinIO)
        archivo = doc.ultima_revision.archivo
        file_handle = archivo.open('rb')
        
        response = FileResponse(file_handle, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{doc.codigo}.pdf"'
        # Asegurar headers de seguridad y CORS para PDF.js
        response["Access-Control-Allow-Origin"] = "*"
        response["X-Frame-Options"] = "SAMEORIGIN"
        return response
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error en documento_proxy_pdf para doc {doc_id}: {str(e)}")
        raise Http404(f"Error al abrir el PDF desde el almacenamiento.")

@csrf_exempt
@require_POST
def documento_chat_ia(request):
    """
    Proxy para comunicar el chat del frontend con el webhook de n8n interno.
    """
    try:
        data = json.loads(request.body)
        
        # URL interna del servicio n8n en Coolify (Docker network)
        # Nombre del contenedor: n8n-z8wscww488scgs84oo4os008
        # Puerto interno: 5678
        n8n_url = "http://n8n-z8wscww488scgs84oo4os008:5678/webhook/chat-documento"
        
        # Reenviar la petición a n8n
        response = requests.post(f"{n8n_url}", json=data, timeout=30)
        
        if response.status_code == 200:
            return JsonResponse(response.json())
        else:
            return JsonResponse({'error': f'Error en n8n: {response.text}'}, status=response.status_code)
            
    except requests.exceptions.ConnectionError:
        return JsonResponse({'error': 'No se pudo conectar con el servicio de IA (n8n offline o inalcanzable).'}, status=503)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
