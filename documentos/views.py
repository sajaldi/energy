from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Documento

@login_required
def documento_trazabilidad(request, doc_id):
    """
    Visualizador de trazabilidad de un documento (hacia atrás y hacia adelante).
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
    
    from django.contrib.auth.models import User
    context = {
        'documento': documento,
        'tree': tree,
        'root': root,
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

from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import Documento, ComentarioDocumento
import json

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
                'pagina': c.pagina,
                'resuelto': c.resuelto
            })

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
            
        comentario = ComentarioDocumento.objects.create(
            documento=doc,
            revision=doc.ultima_revision,
            usuario=request.user,
            texto=texto,
            posicion_x=pos_x,
            posicion_y=pos_y,
            pagina=pagina
        )
        
        return JsonResponse({
            'status': 'success',
            'comentario': {
                'id': comentario.id,
                'texto': comentario.texto,
                'usuario': comentario.usuario.username,
                'fecha': comentario.creado_en.strftime('%d/%m/%Y %H:%M'),
                'x': comentario.posicion_x,
                'y': comentario.posicion_y,
                'pagina': comentario.pagina
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
