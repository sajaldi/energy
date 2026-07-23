import os
import requests
import json
from django.conf import settings
from .ai_data_utils import get_dynamic_context

# Intentar obtener la API Key de settings o variables de entorno
API_KEY = getattr(settings, "GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))

# Actualizar modelos a versiones estables y existentes
MODEL = "gemini-1.5-flash" 
MODEL_REQUESTED = "gemini-1.5-flash"
FALLBACK_MODEL = "gemini-1.5-flash"

KNOWLEDGE_BASE_PATH = os.path.join(os.path.dirname(__file__), 'ai_knowledge', 'knowledge.txt')

def get_knowledge_base():
    try:
        if os.path.exists(KNOWLEDGE_BASE_PATH):
            with open(KNOWLEDGE_BASE_PATH, 'r', encoding='utf-8') as f:
                return f.read()
        return ""
    except Exception as e:
        print(f"Error reading knowledge base: {e}")
        return ""

def get_embedding(text, task_type="retrieval_document", dimensions=None):
    """Obtiene embedding usando Cohere (primario) o Gemini (fallback)."""
    if dimensions is None:
        dimensions = getattr(settings, "VECTOR_DIMENSIONS", 768)

    # --- Intento 1: Cohere embed-multilingual-v3.0 ---
    cohere_key = getattr(settings, "COHERE_API_KEY", "")
    if cohere_key:
        try:
            # Mapear task_type de Gemini a input_type de Cohere
            input_type_map = {
                "retrieval_document": "search_document",
                "retrieval_query": "search_query",
                "semantic_similarity": "search_query",
                "classification": "classification",
                "clustering": "clustering",
            }
            input_type = input_type_map.get(task_type, "search_document")

            response = requests.post(
                "https://api.cohere.com/v1/embed",
                headers={
                    "Authorization": f"Bearer {cohere_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "texts": [text],
                    "model": "embed-multilingual-v3.0",
                    "input_type": input_type,
                    "truncate": "END",
                },
                timeout=15
            )
            response.raise_for_status()
            data = response.json()
            embedding = data['embeddings'][0]

            # Truncar a las dimensiones solicitadas (Cohere devuelve 1024)
            if dimensions and len(embedding) > dimensions:
                embedding = embedding[:dimensions]

            return embedding
        except Exception as e:
            print(f"Error Cohere embedding: {e}")

    # --- Intento 2: Gemini text-embedding-004 ---
    if API_KEY:
        import google.generativeai as genai
        genai.configure(api_key=API_KEY)
        try:
            result = genai.embed_content(
                model="models/text-embedding-004",
                content=text,
                task_type=task_type,
                output_dimensionality=dimensions
            )
            return result['embedding']
        except Exception as e:
            print(f"Error Gemini embedding: {e}")

    print("[ERROR] No hay COHERE_API_KEY ni GEMINI_API_KEY configuradas para embeddings.")
    return None

def ask_ia(question, context="", system_prompt=None, historial=None):
    """Interfaz unificada: rota entre todas las API Keys activas según proveedor."""
    if not system_prompt:
        system_prompt = "Eres un asistente experto en el sistema CMMS."

    # Obtener todas las keys activas ordenadas
    try:
        from documentos.models import GroqApiKey
    except Exception:
        return "Error: No se pudo acceder al modelo de API Keys."
    
    claves = list(GroqApiKey.objects.filter(is_active=True).order_by('orden', 'created_at'))
    if not claves:
        return "Error: No hay API Keys activas. Agréguelas en /admin/documentos/groqapikey/"

    # Intentar cada key en orden hasta que una funcione
    last_error = ""
    for clave in claves:
        try:
            if clave.proveedor == 'groq':
                result = _call_groq(clave, question, context, system_prompt, historial)
            elif clave.proveedor == 'google':
                result = _call_google(clave, question, context, system_prompt, historial)
            elif clave.proveedor == 'cohere':
                result = _call_cohere(clave, question, context, system_prompt, historial)
            elif clave.proveedor == 'openrouter':
                result = _call_openrouter(clave, question, context, system_prompt, historial)
            else:
                continue
            
            if result:
                return result
        except Exception as e:
            last_error = f"{clave.alias} ({clave.proveedor}): {type(e).__name__}: {str(e)[:100]}"
            print(f"Error IA [{clave.alias}]: {last_error}")
            continue

    return f"Error: Todas las API Keys fallaron. Último error: {last_error}"


def _call_groq(clave, question, context, system_prompt, historial):
    """Llama a Groq API via requests (sin depender del SDK)."""
    messages = [{"role": "system", "content": f"{system_prompt}\n\nContexto del sistema:\n{context}"}]
    if historial:
        for msg in historial[-10:]:
            if msg.get('role') in ('user', 'assistant') and msg.get('content'):
                messages.append({"role": msg['role'], "content": msg['content']})
    messages.append({"role": "user", "content": question})

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {clave.api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": clave.modelo,
            "messages": messages,
            "temperature": 0.4,
            "max_tokens": 1500,
        },
        timeout=15
    )
    response.raise_for_status()
    data = response.json()
    return data['choices'][0]['message']['content']


def _call_google(clave, question, context, system_prompt, historial):
    """Llama a Google Gemini API."""
    prompt_parts = [f"{system_prompt}\n\nContexto:\n{context}\n\n"]
    if historial:
        for msg in historial[-8:]:
            role_label = "Usuario" if msg.get('role') == 'user' else "Asistente"
            if msg.get('content'):
                prompt_parts.append(f"{role_label}: {msg['content']}\n")
    prompt_parts.append(f"\nUsuario: {question}")
    prompt = "".join(prompt_parts)

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{clave.modelo}:generateContent?key={clave.api_key}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()
    data = response.json()
    if 'candidates' in data and data['candidates']:
        return data['candidates'][0]['content']['parts'][0]['text']
    return None


def _call_cohere(clave, question, context, system_prompt, historial):
    """Llama a Cohere Chat API via requests (sin depender del SDK)."""
    chat_history = []
    if historial:
        for msg in historial[-6:]:
            cohere_role = "USER" if msg.get('role') == 'user' else "CHATBOT"
            if msg.get('content'):
                chat_history.append({"role": cohere_role, "message": msg['content']})

    payload = {
        "model": clave.modelo,
        "message": question,
        "preamble": f"{system_prompt}\n\nContexto:\n{context[:6000]}",
        "chat_history": chat_history,
        "temperature": 0.4,
    }

    response = requests.post(
        "https://api.cohere.com/v1/chat",
        headers={
            "Authorization": f"Bearer {clave.api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=25
    )
    response.raise_for_status()
    data = response.json()
    return data.get('text', '')


def _call_openrouter(clave, question, context, system_prompt, historial):
    """Llama a OpenRouter API (compatible OpenAI)."""
    messages = [{"role": "system", "content": f"{system_prompt}\n\nContexto del sistema:\n{context}"}]
    if historial:
        for msg in historial[-10:]:
            if msg.get('role') in ('user', 'assistant') and msg.get('content'):
                messages.append({"role": msg['role'], "content": msg['content']})
    messages.append({"role": "user", "content": question})

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {clave.api_key}"},
        json={"model": clave.modelo, "messages": messages, "max_tokens": 1500},
        timeout=30
    )
    response.raise_for_status()
    data = response.json()
    return data['choices'][0]['message']['content']

def _buscar_documento_por_codigo(question):
    """
    Detecta si la pregunta menciona un código de documento y lo busca directamente en la BD.
    Retorna información detallada del documento incluyendo su contenido y estado de vectorización.
    """
    import re
    from documentos.models import Documento, DocumentoFragmento
    from django.db.models import Q, Count
    
    # Patrones comunes de códigos de documento (ajustar según convención del proyecto)
    # Ejemplos: AH-CCG-165-2026, CCG-I-T1-IAA-07-02, DOC-001, etc.
    patron_codigo = re.findall(
        r'[A-Za-z]{2,}[-/][A-Za-z0-9]{2,}[-/][\w\-]+',
        question
    )
    
    if not patron_codigo:
        return "", []
    
    resultados = []
    context_parts = []
    
    for posible_codigo in patron_codigo:
        codigo_upper = posible_codigo.upper().strip()
        
        # Búsqueda exacta y parcial por código
        docs = Documento.objects.select_related(
            'tipo_documento', 'disciplina', 'responsable', 'carpeta'
        ).filter(
            Q(codigo__iexact=codigo_upper) | Q(codigo__icontains=codigo_upper)
        ).annotate(
            num_fragmentos=Count('fragmentos')
        )[:5]
        
        for doc in docs:
            # Verificar estado de vectorización
            tiene_texto = bool(doc.contenido_texto and doc.contenido_texto.strip())
            tiene_embedding = doc.embedding is not None
            num_fragmentos = doc.num_fragmentos
            fue_vectorizado = tiene_embedding or num_fragmentos > 0
            
            # Preparar resumen del contenido
            contenido_preview = ""
            if tiene_texto:
                contenido_preview = doc.contenido_texto[:1500]
            
            # Construir ficha del documento
            ficha = (
                f"📄 DOCUMENTO ENCONTRADO POR CÓDIGO:\n"
                f"  Código: {doc.codigo}\n"
                f"  Título: {doc.titulo}\n"
                f"  ID: {doc.id}\n"
                f"  Tipo: {doc.tipo_documento.nombre if doc.tipo_documento else 'N/A'}\n"
                f"  Estado: {doc.estado_actual}\n"
                f"  Disciplina: {doc.disciplina.nombre if doc.disciplina else 'N/A'}\n"
                f"  Responsable: {doc.responsable.get_full_name() if doc.responsable else 'N/A'}\n"
                f"  Carpeta: {doc.carpeta.nombre if doc.carpeta else 'Sin carpeta'}\n"
                f"  Fecha emisión: {doc.fecha_inicio or 'N/A'}\n"
                f"  Fecha vencimiento: {doc.fecha_vencimiento or 'N/A'}\n"
                f"  ---\n"
                f"  Tiene contenido texto: {'SÍ' if tiene_texto else 'NO'}\n"
                f"  Fue vectorizado (IA): {'SÍ' if fue_vectorizado else 'NO'}\n"
                f"  Fragmentos vectorizados: {num_fragmentos}\n"
                f"  Embedding resumen: {'SÍ' if tiene_embedding else 'NO'}\n"
            )
            
            if contenido_preview:
                ficha += f"  ---\n  CONTENIDO DEL DOCUMENTO (extracto):\n  {contenido_preview}\n"
            else:
                ficha += f"  ---\n  ⚠️ Este documento NO tiene texto extraído (campo contenido_texto vacío).\n"
            
            context_parts.append(ficha)
            resultados.append({
                'id': doc.id,
                'codigo': doc.codigo,
                'titulo': doc.titulo,
            })
    
    if context_parts:
        return "\n\n".join(context_parts), resultados
    
    # Si no encontró nada, informar al LLM
    codigos_buscados = ", ".join(patron_codigo)
    return f"⚠️ BÚSQUEDA DIRECTA: No se encontró ningún documento con código similar a: {codigos_buscados}", []


def _get_rag_context(question, max_chunks=10):
    """Busca fragmentos de documentos y KPIs relevantes usando búsqueda vectorial."""
    try:
        from documentos.models import DocumentoFragmento
        from pgvector.django import CosineDistance
        
        context_parts = []
        sources = []
        seen_docs = set()
        
        # --- RAG de Documentos (768 dimensiones) ---
        if DocumentoFragmento.objects.filter(embedding__isnull=False).exists():
            query_vector_768 = get_embedding(question, task_type="retrieval_query", dimensions=768)
            if query_vector_768:
                fragmentos = DocumentoFragmento.objects.select_related('documento').filter(
                    embedding__isnull=False
                ).annotate(
                    distance=CosineDistance('embedding', query_vector_768)
                ).filter(distance__lt=0.45).order_by('distance')[:max_chunks]
                
                for f in fragmentos:
                    if f.documento_id not in seen_docs:
                        seen_docs.add(f.documento_id)
                        sources.append({
                            'id': f.documento.id,
                            'codigo': f.documento.codigo,
                            'titulo': f.documento.titulo,
                            'tipo': 'documento',
                        })
                    preview = f.contenido[:400] if f.contenido else ''
                    context_parts.append(f"[DOC: {f.documento.codigo} | ID:{f.documento.id}] {preview}")
        
        # --- RAG de KPIs de Servicios (384 dimensiones) ---
        try:
            from servicios.models import KPIFragmento
            
            if KPIFragmento.objects.filter(embedding__isnull=False).exists():
                query_vector_384 = get_embedding(question, task_type="retrieval_query", dimensions=384)
                if query_vector_384:
                    kpi_fragmentos = KPIFragmento.objects.select_related('kpi', 'kpi__servicio').filter(
                        embedding__isnull=False
                    ).annotate(
                        distance=CosineDistance('embedding', query_vector_384)
                    ).filter(distance__lt=0.45).order_by('distance')[:max_chunks]
                    
                    seen_kpis = set()
                    for f in kpi_fragmentos:
                        if f.kpi_id not in seen_kpis:
                            seen_kpis.add(f.kpi_id)
                            sources.append({
                                'id': f.kpi.id,
                                'codigo': f"KPI-{f.kpi.id}",
                                'titulo': f"{f.kpi.servicio.nombre} - {f.kpi.nombre or f.kpi.categoria}",
                                'tipo': 'kpi',
                            })
                        preview = f.contenido[:400] if f.contenido else ''
                        context_parts.append(f"[KPI: {f.kpi.servicio.nombre} | ID:{f.kpi.id} | {f.kpi.categoria}] {preview}")
        except Exception as e:
            print(f"Error en búsqueda vectorial KPIs: {e}")
        
        if not context_parts:
            return "", []
        
        rag_context = "\n---\n".join(context_parts)
        return rag_context, sources
    except Exception as e:
        print(f"Error en búsqueda vectorial: {e}")
        return "", []


def ask_gemini(question, context_limit=8000, historial=None):
    """Chatbot con contexto de BD + búsqueda directa por código + búsqueda vectorial RAG."""
    db_context = get_dynamic_context()
    
    # 1. Búsqueda directa por código de documento (prioridad alta)
    doc_directo_context, doc_directo_sources = _buscar_documento_por_codigo(question)
    
    # 2. Búsqueda vectorial para enriquecer con contenido de documentos (semántica)
    rag_context, rag_sources = _get_rag_context(question)
    
    # Combinar fuentes sin duplicados
    all_sources = list(doc_directo_sources)
    seen_ids = {s['id'] for s in all_sources}
    for s in rag_sources:
        if s['id'] not in seen_ids:
            all_sources.append(s)
            seen_ids.add(s['id'])
    
    # Combinar contextos
    context_parts = [db_context[:context_limit]]
    if doc_directo_context:
        context_parts.append(f"\n\nBÚSQUEDA DIRECTA POR CÓDIGO DE DOCUMENTO:\n{doc_directo_context}")
    if rag_context:
        context_parts.append(f"\nCONTENIDO RELEVANTE DE DOCUMENTOS (búsqueda semántica):\n{rag_context}")
    
    context = "\n".join(context_parts)
    
    # Construir info de fuentes con links para el prompt
    sources_info = ""
    if all_sources:
        sources_info = "\n\nFUENTES ENCONTRADAS (incluye estos links en tu respuesta usando formato Markdown [texto](url)):\n"
        for s in all_sources:
            if s.get('tipo') == 'kpi':
                sources_info += f"- KPI {s['codigo']}: {s['titulo']} → Link: /servicios/kpis/{s['id']}/\n"
            else:
                sources_info += f"- {s['codigo']}: {s['titulo']} → Link: /documentos/trazabilidad/{s['id']}/\n"
    
    # System prompt
    system_prompt = (
        "Eres un asistente experto del sistema CMMS de gestión de mantenimiento. "
        "Tienes acceso al estado actual de la base de datos, contenido de documentos vectorizados, y KPIs de Servicios. "
        "REGLAS:\n"
        "1. Cuando el usuario pregunte por un documento específico (código), usa la BÚSQUEDA DIRECTA POR CÓDIGO para responder con datos reales.\n"
        "2. Si el documento fue encontrado, informa: su título, tipo, estado, si tiene contenido de texto extraído, y si fue vectorizado.\n"
        "3. Si tiene contenido de texto, resume brevemente de qué trata el documento basándote en el extracto proporcionado.\n"
        "4. Si fue vectorizado, explica que el documento participa en la búsqueda semántica del sistema.\n"
        "5. Cuando menciones un documento, incluye un link Markdown: [CÓDIGO](/documentos/trazabilidad/ID/)\n"
        "6. Cuando menciones un KPI, incluye un link Markdown: [KPI-ID](/servicios/kpis/ID/)\n"
        "7. Para consultas sobre KPIs, usa la info de KPIs DE SERVICIOS y los fragmentos semánticos encontrados.\n"
        "8. Si NO se encontró el documento o KPI, dilo claramente y sugiere verificar.\n"
        "9. Responde en español, claro y profesional."
        f"{sources_info}"
    )
    
    respuesta = ask_ia(question, context=context, system_prompt=system_prompt, historial=historial)
    
    # Post-procesamiento: agregar links de fuentes si el bot no los incluyó
    if all_sources and '/documentos/trazabilidad/' not in respuesta and '/servicios/kpis/' not in respuesta:
        respuesta += "\n\n📎 **Fuentes relacionadas:**\n"
        for s in all_sources:
            if s.get('tipo') == 'kpi':
                respuesta += f"- [KPI-{s['id']}](/servicios/kpis/{s['id']}/) - {s['titulo']}\n"
            else:
                respuesta += f"- [{s['codigo']}](/documentos/trazabilidad/{s['id']}/) - {s['titulo']}\n"
    
    return respuesta
