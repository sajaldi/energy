import json
import logging
import time
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.http import require_POST
from .models import Consulta, MensajeConsulta

logger = logging.getLogger(__name__)


@login_required
def lista_consultas(request):
    """Lista todas las consultas subidas."""
    consultas = Consulta.objects.all()
    return render(request, 'consultas/lista.html', {'consultas': consultas})


@login_required
def subir_consulta(request):
    """Sube y procesa un archivo TXT de chat."""
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        archivo = request.FILES.get('archivo')

        if not nombre:
            messages.error(request, 'El nombre es requerido.')
            return render(request, 'consultas/subir.html')

        if not archivo:
            messages.error(request, 'Debe seleccionar un archivo.')
            return render(request, 'consultas/subir.html')

        if not archivo.name.endswith('.txt'):
            messages.error(request, 'Solo se permiten archivos .txt')
            return render(request, 'consultas/subir.html')

        consulta = Consulta.objects.create(
            nombre=nombre,
            archivo=archivo,
            subido_por=request.user,
        )

        try:
            total = consulta.procesar_archivo()
            messages.success(request, f'✅ Archivo procesado: {total} mensajes extraídos.')
        except Exception as e:
            logger.exception("Error procesando consulta")
            messages.error(request, f'Error procesando el archivo: {e}')

        return redirect('consultas:detalle', consulta_id=consulta.id)

    return render(request, 'consultas/subir.html')


@login_required
def detalle_consulta(request, consulta_id):
    """Muestra los mensajes de una consulta con filtros."""
    consulta = get_object_or_404(Consulta, id=consulta_id)
    mensajes = consulta.mensajes.all()

    # Filtros opcionales
    remitente = request.GET.get('remitente', '')
    texto_buscar = request.GET.get('q', '')

    if remitente:
        mensajes = mensajes.filter(remitente__icontains=remitente)
    if texto_buscar:
        mensajes = mensajes.filter(texto__icontains=texto_buscar)

    # Obtener lista de remitentes únicos para el filtro
    remitentes = consulta.mensajes.values_list('remitente', flat=True).distinct().order_by('remitente')

    # Contar mensajes con embedding
    total_con_embedding = consulta.mensajes.exclude(embedding__isnull=True).count()

    return render(request, 'consultas/detalle.html', {
        'consulta': consulta,
        'mensajes': mensajes[:500],
        'remitentes': remitentes,
        'remitente_actual': remitente,
        'texto_buscar': texto_buscar,
        'total_mensajes': consulta.total_mensajes,
        'total_con_embedding': total_con_embedding,
    })


@login_required
def buscar_mensajes(request, consulta_id):
    """
    Búsqueda semántica + respuesta con IA (RAG).
    1. Genera embedding de la query
    2. Busca los mensajes más similares vectorialmente
    3. Usa los fragmentos como contexto para que la IA responda con citas clickeables
    """
    consulta = get_object_or_404(Consulta, id=consulta_id)
    query = request.GET.get('q', '').strip()
    resultados = []
    respuesta_ia = None
    error = None

    if query:
        try:
            embedding = _generar_embedding_query(query)
            if embedding:
                resultados_qs = MensajeConsulta.buscar_vectorial(
                    query_embedding=embedding,
                    consulta=consulta,
                    limit=30
                )
                resultados = []
                contexto_fragmentos = []
                for msg in resultados_qs:
                    similitud = round((1 - msg.distancia) * 100, 1)
                    resultados.append({
                        'mensaje': msg,
                        'similitud': similitud,
                    })
                    # Top 20 como contexto para IA, ordenados cronológicamente
                    if len(contexto_fragmentos) < 20:
                        contexto_fragmentos.append({
                            'id': msg.id,
                            'fecha_str': msg.fecha_str,
                            'hora_str': msg.hora_str,
                            'remitente': msg.remitente,
                            'texto': msg.texto,
                        })

                # Ordenar cronológicamente antes de enviarlo a la IA
                def _parse_fecha_sort(item):
                    """Intenta parsear fecha para ordenar cronológicamente."""
                    try:
                        from datetime import datetime
                        fecha = item['fecha_str']
                        hora = item['hora_str'].replace('a. m.', 'AM').replace('p. m.', 'PM')
                        # Intentar parsear formatos comunes
                        for fmt in ['%d/%m/%y %I:%M %p', '%d/%m/%Y %I:%M %p']:
                            try:
                                return datetime.strptime(f"{fecha} {hora}", fmt)
                            except ValueError:
                                continue
                        return datetime.min
                    except Exception:
                        return datetime.min

                contexto_fragmentos.sort(key=_parse_fecha_sort)

                # Construir texto de contexto ordenado
                contexto_lines = []
                for frag in contexto_fragmentos:
                    contexto_lines.append(
                        f"[MSG_ID:{frag['id']}][{frag['fecha_str']} {frag['hora_str']}] {frag['remitente']}: {frag['texto']}"
                    )

                # Generar respuesta con IA
                if contexto_fragmentos:
                    from core.ai_utils import ask_ia
                    from .models import NotaContexto
                    contexto_parts_ia = []

                    # Inyectar notas de contexto guardadas
                    notas = list(NotaContexto.obtener_todas(consulta))
                    if notas:
                        notas_text = "\n".join([f"• {n}" for n in notas])
                        contexto_parts_ia.append(f"INFORMACIÓN DE CONTEXTO (el usuario ya explicó esto, SIEMPRE úsala):\n{notas_text}")

                    contexto_parts_ia.append("MENSAJES DEL CHAT (ordenados cronológicamente):\n" + "\n---\n".join(contexto_lines))
                    contexto = "\n\n".join(contexto_parts_ia)
                    system_prompt = (
                        "Eres un asistente experto que analiza conversaciones de chat de WhatsApp "
                        "relacionadas con mantenimiento, operaciones y gestión de edificios. "
                        "Se te proporcionan los mensajes más relevantes extraídos de un chat grupal, "
                        "ORDENADOS CRONOLÓGICAMENTE (del más antiguo al más reciente).\n\n"
                        "REGLAS:\n"
                        "1. Responde la pregunta del usuario basándote ÚNICAMENTE en los mensajes proporcionados.\n"
                        "2. Si la información no está en los mensajes, dilo claramente.\n"
                        "3. **CITAS OBLIGATORIAS**: Cuando cites un mensaje, usa EXACTAMENTE este formato: "
                        "[[MSG_ID:123|fecha hora]] donde 123 es el ID del mensaje y fecha/hora son los datos reales. "
                        "Ejemplo: [[MSG_ID:456|3/9/23 2:12 p. m.]]\n"
                        "4. Usa formato Markdown para estructurar tu respuesta (negritas, listas, encabezados).\n"
                        "5. **CRONOLOGÍA**: Presenta los eventos en orden cronológico. Los mensajes ya están ordenados por fecha.\n"
                        "6. Sé conciso pero completo. Resume la información relevante.\n"
                        "7. Responde en español.\n"
                        "8. Cada mensaje tiene un ID al inicio en formato [MSG_ID:X]. Úsalo para las citas.\n"
                        "9. Si detectas una secuencia de solicitud → acción → resultado, preséntala claramente."
                    )
                    try:
                        respuesta_ia = ask_ia(
                            question=query,
                            context=contexto,
                            system_prompt=system_prompt
                        )
                    except Exception as e:
                        logger.warning(f"Error generando respuesta IA: {e}")
                        respuesta_ia = None
            else:
                error = "No se pudo generar el embedding para la búsqueda. Verifica la configuración de API keys."
        except Exception as e:
            logger.exception("Error en búsqueda vectorial")
            error = f"Error en la búsqueda: {e}"

    # Preparar datos de mensajes para el modal (JSON) con contexto (1 arriba, 3 abajo)
    mensajes_json = {}
    msg_ids_resultado = [r['mensaje'].id for r in resultados]
    
    for r in resultados:
        msg = r['mensaje']
        # Obtener 1 mensaje anterior y 3 posteriores del mismo chat
        vecinos_antes = list(
            MensajeConsulta.objects.filter(
                consulta=consulta, id__lt=msg.id
            ).order_by('-id')[:1]
        )
        vecinos_despues = list(
            MensajeConsulta.objects.filter(
                consulta=consulta, id__gt=msg.id
            ).order_by('id')[:3]
        )
        
        # Construir contexto del modal
        contexto_modal = []
        for v in reversed(vecinos_antes):
            contexto_modal.append({
                'id': v.id,
                'remitente': v.remitente,
                'fecha': v.fecha_str,
                'hora': v.hora_str,
                'texto': v.texto,
                'tipo': 'antes',
            })
        contexto_modal.append({
            'id': msg.id,
            'remitente': msg.remitente,
            'fecha': msg.fecha_str,
            'hora': msg.hora_str,
            'texto': msg.texto,
            'tipo': 'principal',
        })
        for v in vecinos_despues:
            contexto_modal.append({
                'id': v.id,
                'remitente': v.remitente,
                'fecha': v.fecha_str,
                'hora': v.hora_str,
                'texto': v.texto,
                'tipo': 'despues',
            })

        mensajes_json[str(msg.id)] = {
            'remitente': msg.remitente,
            'fecha': msg.fecha_str,
            'hora': msg.hora_str,
            'texto': msg.texto,
            'contexto': contexto_modal,
        }

    return render(request, 'consultas/buscar.html', {
        'consulta': consulta,
        'query': query,
        'resultados': resultados,
        'respuesta_ia': respuesta_ia,
        'mensajes_json': json.dumps(mensajes_json, ensure_ascii=False),
        'error': error,
    })


@login_required
def generar_embeddings_stream(request, consulta_id):
    """
    Server-Sent Events (SSE) endpoint que genera embeddings y envía progreso en tiempo real.
    Solo procesa mensajes que NO tengan embedding (resume donde quedó).
    Usa rotación de keys de Gemini para evitar rate limits.
    """
    from .tasks import _generar_embeddings_batch
    
    consulta = get_object_or_404(Consulta, id=consulta_id)

    def event_stream():
        try:
            # Total de mensajes elegibles (excluyendo multimedia)
            total_elegibles = consulta.mensajes.exclude(texto='<Multimedia omitido>').count()
            # Ya procesados previamente
            ya_procesados = consulta.mensajes.exclude(embedding__isnull=True).count()
            
            # Solo los pendientes
            mensajes = list(
                consulta.mensajes.filter(embedding__isnull=True).exclude(
                    texto='<Multimedia omitido>'
                )
            )
            pendientes = len(mensajes)

            if pendientes == 0:
                percent = 100 if total_elegibles > 0 else 0
                yield _sse_msg({
                    'current': ya_procesados, 'total': total_elegibles,
                    'percent': percent, 'state': 'SUCCESS',
                    'status': f'✅ Todos los mensajes ya tienen embedding ({ya_procesados}/{total_elegibles}).'
                })
                return

            # Mostrar progreso inicial con lo ya procesado
            percent_inicial = int((ya_procesados / total_elegibles) * 100) if total_elegibles > 0 else 0
            yield _sse_msg({
                'current': ya_procesados, 'total': total_elegibles,
                'percent': percent_inicial, 'state': 'PROGRESS',
                'status': f'Reanudando... {pendientes} mensajes pendientes ({ya_procesados} ya procesados)'
            })

            batch_size = 100  # Ollama local soporta batches grandes
            nuevos_procesados = 0
            errores = 0

            for i in range(0, pendientes, batch_size):
                batch_mensajes = mensajes[i:i + batch_size]
                textos = [f"{m.remitente}: {m.texto}" for m in batch_mensajes]

                try:
                    embeddings = _generar_embeddings_batch(textos, batch_size=len(textos))

                    if embeddings:
                        for msg, emb in zip(batch_mensajes, embeddings):
                            msg.embedding = emb
                        MensajeConsulta.objects.bulk_update(batch_mensajes, ['embedding'], batch_size=100)
                        nuevos_procesados += len(batch_mensajes)
                    else:
                        errores += len(batch_mensajes)
                        nuevos_procesados += len(batch_mensajes)
                except Exception as e:
                    logger.warning(f"Error en batch {i}: {e}")
                    errores += len(batch_mensajes)
                    nuevos_procesados += len(batch_mensajes)

                total_actual = ya_procesados + nuevos_procesados
                percent = int((total_actual / total_elegibles) * 100)
                yield _sse_msg({
                    'current': total_actual,
                    'total': total_elegibles,
                    'percent': percent,
                    'state': 'PROGRESS',
                    'status': f'Procesados {total_actual}/{total_elegibles} ({percent}%)'
                })

            # Final
            total_final = ya_procesados + nuevos_procesados - errores
            status_final = f'✅ Completado: {total_final}/{total_elegibles} embeddings.'
            if errores:
                status_final += f' ({errores} con error)'

            yield _sse_msg({
                'current': total_final,
                'total': total_elegibles,
                'percent': 100,
                'state': 'SUCCESS',
                'status': status_final
            })

        except Exception as e:
            logger.exception("Error en generación de embeddings SSE")
            yield _sse_msg({
                'current': 0, 'total': 0, 'percent': 0,
                'state': 'FAILURE',
                'status': f'❌ Error: {str(e)}'
            })

    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response


def _sse_msg(data):
    """Formatea un mensaje SSE."""
    return f"data: {json.dumps(data)}\n\n"


def _generar_embedding_query(texto):
    """
    Genera un embedding para una query de búsqueda.
    Usa Ollama local primero (rápido, sin limits).
    Fallback a Gemini REST API si Ollama no está disponible.
    """
    import requests
    import time

    # Intentar Ollama local primero
    try:
        r = requests.post(
            'http://localhost:11434/api/embed',
            json={'model': 'nomic-embed-text', 'input': [texto]},
            timeout=10
        )
        if r.status_code == 200:
            return r.json()['embeddings'][0]
    except Exception as e:
        logger.info(f"Ollama no disponible para query: {e}")

    # Fallback: Gemini REST API
    from consultas.tasks import _get_gemini_keys
    keys = _get_gemini_keys()
    if not keys:
        logger.error("No hay proveedor de embeddings disponible.")
        return None

    for attempt in range(len(keys) * 2):
        key = keys[attempt % len(keys)]
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent?key={key}"

        try:
            response = requests.post(url, json={
                "model": "models/gemini-embedding-001",
                "content": {"parts": [{"text": texto}]},
                "outputDimensionality": 768,
                "taskType": "RETRIEVAL_QUERY"
            }, timeout=15)

            if response.status_code == 200:
                return response.json()['embedding']['values']
            elif response.status_code == 429:
                if (attempt + 1) % len(keys) == 0:
                    time.sleep(35)
                continue
            else:
                logger.warning(f"Error Gemini ({response.status_code})")
                return None
        except Exception as e:
            logger.warning(f"Error embedding query: {e}")
            return None

    return None


@login_required
@require_POST
def chat_ia(request, consulta_id):
    """
    Endpoint AJAX para preguntas de seguimiento en la conversación.
    - Detecta si el usuario está dando información (notas de contexto) o preguntando
    - Busca mensajes relevantes + notas guardadas + conversaciones previas
    - Genera respuesta con IA
    - Guarda la interacción con embedding para enriquecer futuras búsquedas
    """
    import uuid
    from .models import ConversacionIA, NotaContexto

    consulta = get_object_or_404(Consulta, id=consulta_id)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    pregunta = body.get('pregunta', '').strip()
    session_id = body.get('session_id', '')

    if not pregunta:
        return JsonResponse({'error': 'Pregunta vacía'}, status=400)

    if not session_id:
        session_id = str(uuid.uuid4())[:16]

    # --- Detectar si es una nota de contexto (el usuario da información) ---
    es_nota = _detectar_nota_contexto(pregunta)
    if es_nota:
        # Guardar como nota de contexto
        nota = NotaContexto.objects.create(
            consulta=consulta,
            usuario=request.user,
            contenido=pregunta,
            categoria=es_nota,
        )
        # Vectorizar la nota
        try:
            emb = _generar_embedding_query(pregunta)
            if emb:
                nota.embedding = emb
                nota.save(update_fields=['embedding'])
        except Exception:
            pass

        return JsonResponse({
            'respuesta': f'✅ **Nota guardada.** Recordaré esto:\n\n> {pregunta}\n\nA partir de ahora usaré esta información en mis respuestas.',
            'session_id': session_id,
            'mensajes': {},
            'conversacion_id': None,
            'nota_guardada': True,
        })

    # --- Flujo normal: búsqueda + respuesta IA ---

    # 1. Generar embedding de la pregunta
    embedding = _generar_embedding_query(pregunta)
    if not embedding:
        return JsonResponse({'error': 'No se pudo generar embedding. Verifica Ollama/API keys.'}, status=500)

    # 2. Buscar mensajes relevantes del chat
    resultados_qs = MensajeConsulta.buscar_vectorial(
        query_embedding=embedding,
        consulta=consulta,
        limit=20
    )

    contexto_msgs = []
    mensajes_data = {}
    for msg in resultados_qs:
        contexto_msgs.append(
            f"[MSG_ID:{msg.id}][{msg.fecha_str} {msg.hora_str}] {msg.remitente}: {msg.texto}"
        )
        mensajes_data[str(msg.id)] = {
            'remitente': msg.remitente,
            'fecha': msg.fecha_str,
            'hora': msg.hora_str,
            'texto': msg.texto,
        }

    # 3. Buscar TICKETS relacionados (SolicitudTicket)
    contexto_tickets = []
    try:
        from callcenter.models import SolicitudTicket
        tickets_qs = SolicitudTicket.buscar_vectorial_local(
            query_embedding=embedding, limit=5
        )
        for ticket in tickets_qs:
            if ticket.distancia < 0.5:  # Solo los muy relevantes
                partes_t = []
                if ticket.folio:
                    partes_t.append(f"Folio: {ticket.folio}")
                if ticket.solicitud_descripcion:
                    partes_t.append(f"Descripción: {ticket.solicitud_descripcion[:200]}")
                if ticket.diagnostico:
                    partes_t.append(f"Diagnóstico: {ticket.diagnostico[:200]}")
                if ticket.fecha_solicitud:
                    partes_t.append(f"Fecha: {ticket.fecha_solicitud.strftime('%d/%m/%Y')}")
                if ticket.servicio:
                    partes_t.append(f"Servicio: {ticket.servicio}")
                if ticket.solicitante:
                    partes_t.append(f"Solicitante: {ticket.solicitante}")
                contexto_tickets.append(" | ".join(partes_t))
    except Exception as e:
        logger.warning(f"Error buscando tickets relacionados: {e}")

    # 3. Obtener NOTAS DE CONTEXTO (conocimiento proporcionado por el usuario)
    notas_todas = list(NotaContexto.obtener_todas(consulta))
    
    # 4. Buscar conversaciones previas relevantes
    conversaciones_previas = ConversacionIA.buscar_contexto_previo(
        query_embedding=embedding,
        consulta=consulta,
        session_id=session_id,
        limit=3
    )
    contexto_conv = []
    for conv in conversaciones_previas:
        contexto_conv.append(f"[Pregunta anterior]: {conv.pregunta}\n[Respuesta anterior]: {conv.respuesta[:300]}")

    # 5. Historial de la sesión actual
    historial_session = list(
        ConversacionIA.objects.filter(
            consulta=consulta, session_id=session_id
        ).order_by('-creado_en')[:5]
    )
    historial_session.reverse()
    historial_ia = []
    for h in historial_session:
        historial_ia.append({'role': 'user', 'content': h.pregunta})
        historial_ia.append({'role': 'assistant', 'content': h.respuesta[:500]})

    # 6. Construir contexto completo
    contexto_parts = []

    # Notas de contexto primero (conocimiento base)
    if notas_todas:
        notas_text = "\n".join([f"• {n}" for n in notas_todas])
        contexto_parts.append(f"INFORMACIÓN DE CONTEXTO (proporcionada por el usuario, SIEMPRE considérala):\n{notas_text}")

    # Tickets del sistema de call center relacionados
    if contexto_tickets:
        tickets_text = "\n".join([f"• {t}" for t in contexto_tickets])
        contexto_parts.append(f"TICKETS DE SERVICIO RELACIONADOS (sistema call center, menciona folios si son relevantes):\n{tickets_text}")

    if contexto_conv:
        contexto_parts.append("CONVERSACIONES PREVIAS RELEVANTES:\n" + "\n---\n".join(contexto_conv))

    contexto_parts.append("MENSAJES DEL CHAT:\n" + "\n---\n".join(contexto_msgs))
    contexto = "\n\n".join(contexto_parts)

    # 7. Llamar a la IA
    from core.ai_utils import ask_ia
    system_prompt = (
        "Eres un asistente experto que analiza conversaciones de chat de WhatsApp "
        "relacionadas con mantenimiento, operaciones y gestión de edificios.\n\n"
        "IMPORTANTE: Tienes acceso a:\n"
        "- INFORMACIÓN DE CONTEXTO: datos que el usuario ya te explicó (personas, acrónimos, etc.)\n"
        "- TICKETS DE SERVICIO: del sistema de call center, relacionados con la pregunta\n"
        "- MENSAJES DEL CHAT: del grupo de WhatsApp\n\n"
        "REGLAS:\n"
        "1. Responde basándote en TODOS los datos disponibles.\n"
        "2. **CITAS**: Usa [[MSG_ID:123|fecha hora]] para citar mensajes del chat.\n"
        "3. Si hay tickets de servicio relacionados, menciona su folio y descripción.\n"
        "4. Relaciona cronológicamente: misma fecha, ubicación o persona = relación.\n"
        "5. Usa Markdown para formatear.\n"
        "6. Si no tienes info suficiente, PREGUNTA al usuario.\n"
        "7. Responde en español. Sé conciso pero completo."
    )

    try:
        respuesta = ask_ia(
            question=pregunta,
            context=contexto,
            system_prompt=system_prompt,
            historial=historial_ia
        )
    except Exception as e:
        logger.exception("Error en chat IA")
        return JsonResponse({'error': f'Error generando respuesta: {str(e)}'}, status=500)

    # 8. Guardar la conversación
    conv = ConversacionIA.objects.create(
        consulta=consulta,
        session_id=session_id,
        usuario=request.user,
        pregunta=pregunta,
        respuesta=respuesta,
    )

    # 9. Vectorizar la conversación
    try:
        texto_emb = conv.texto_para_embedding()
        emb = _generar_embedding_query(texto_emb)
        if emb:
            conv.embedding = emb
            conv.save(update_fields=['embedding'])
    except Exception as e:
        logger.warning(f"Error vectorizando conversación: {e}")

    return JsonResponse({
        'respuesta': respuesta,
        'session_id': session_id,
        'mensajes': mensajes_data,
        'conversacion_id': conv.id,
    })


def _detectar_nota_contexto(texto):
    """
    Detecta si el usuario está proporcionando información en vez de preguntar.
    Retorna la categoría si es nota, None si es pregunta.
    """
    texto_lower = texto.lower().strip()

    # Patrones que indican que el usuario da información
    patrones_persona = [
        'es el ', 'es la ', 'es un ', 'es una ',
        'se llama ', 'su nombre es ', 'trabaja como ',
        'es técnico', 'es operador', 'es supervisor',
        'es ingeniero', 'es el encargado', 'es la encargada',
    ]
    patrones_lugar = [
        'es el edificio', 'es el nivel', 'es la torre',
        'queda en ', 'está en el ', 'se refiere a ',
    ]
    patrones_termino = [
        'significa ', 'quiere decir ', 'se refiere a ',
        'es la abreviatura', 'es el acrónimo',
    ]
    patrones_general = [
        'recuerda que ', 'ten en cuenta que ', 'nota: ',
        'para tu información', 'fyi:', 'importante: ',
        'te informo que ', 'te cuento que ',
    ]

    # No es nota si es claramente una pregunta
    if texto_lower.startswith(('¿', 'quien ', 'quién ', 'qué ', 'que ', 'cuándo', 'cuando',
                               'dónde', 'donde', 'cómo', 'como ', 'por qué', 'cuál', 'cual')):
        # Excepto si dice "quién es X es el técnico..."
        if ' es el ' not in texto_lower and ' es la ' not in texto_lower:
            return None

    for p in patrones_persona:
        if p in texto_lower:
            return 'PERSONA'
    for p in patrones_lugar:
        if p in texto_lower:
            return 'LUGAR'
    for p in patrones_termino:
        if p in texto_lower:
            return 'TERMINO'
    for p in patrones_general:
        if texto_lower.startswith(p) or p in texto_lower:
            return 'OTRO'

    return None
