"""
Buscador Inteligente de Mantenimientos con IA (Groq/Google/Cohere).
Permite búsquedas en lenguaje natural sobre órdenes de trabajo, programaciones,
rutinas y avisos, combinando filtrado SQL inteligente + búsqueda vectorial.
"""
import json
import re
from datetime import datetime, date, timedelta
from django.http import JsonResponse
from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q, Count, F
from django.utils import timezone

from ..models import (
    OrdenTrabajo, Programacion, Rutina, Tipo, Aviso,
    CierreOrdenTrabajo, PlanificacionMensual
)


# ─────────────────────────────────────────────────────────────
# Vista: Página del Buscador IA
# ─────────────────────────────────────────────────────────────
@staff_member_required
def buscador_ia_cronograma(request):
    """Renderiza la página del buscador inteligente."""
    return render(request, 'mantenimiento/buscador_ia.html')


# ─────────────────────────────────────────────────────────────
# API: Búsqueda con IA
# ─────────────────────────────────────────────────────────────
@csrf_exempt
@staff_member_required
def api_busqueda_ia(request):
    """
    Endpoint principal de búsqueda inteligente.
    Recibe una pregunta en lenguaje natural y:
    1. Usa IA para interpretar la intención y extraer filtros
    2. Ejecuta búsqueda SQL con los filtros interpretados
    3. Opcionalmente usa búsqueda vectorial si hay embeddings
    4. Genera una respuesta en lenguaje natural con la IA
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST requerido'}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    query = data.get('query', '').strip()
    if not query:
        return JsonResponse({'error': 'La consulta no puede estar vacía'}, status=400)

    # Paso 1: Interpretar la consulta con IA para extraer filtros
    filtros = _interpretar_consulta_ia(query)

    # Paso 2: Ejecutar búsqueda en la BD
    resultados_ots = _buscar_ordenes(query, filtros)
    resultados_programaciones = _buscar_programaciones(query, filtros)
    resultados_planificacion = _buscar_planificacion_mensual(query, filtros)

    # Paso 3: Búsqueda vectorial semántica (si hay embeddings)
    resultados_vectorial = _buscar_vectorial(query)

    # Paso 4: Combinar y deduplicar resultados
    todos_resultados = _combinar_resultados(resultados_ots, resultados_programaciones, resultados_vectorial)
    todos_resultados.extend(resultados_planificacion)

    # Paso 4b: Si no hay resultados y la consulta tiene ubicacion+fecha, reintentar sin estado
    if not todos_resultados and filtros.get('ubicacion') and filtros.get('fecha_desde'):
        filtros_relajados = dict(filtros)
        filtros_relajados['estado'] = None
        filtros_relajados['temporal'] = None
        resultados_ots_fallback = _buscar_ordenes(query, filtros_relajados)
        todos_resultados = resultados_ots_fallback

    # Paso 5: Generar respuesta en lenguaje natural con IA
    respuesta_ia = _generar_respuesta_ia(query, todos_resultados, filtros)

    return JsonResponse({
        'status': 'success',
        'query': query,
        'respuesta_ia': respuesta_ia,
        'filtros_detectados': filtros,
        'resultados': todos_resultados[:50],
        'total': len(todos_resultados),
    })


# ─────────────────────────────────────────────────────────────
# Funciones internas
# ─────────────────────────────────────────────────────────────

def _interpretar_consulta_ia(query):
    """
    Usa la IA para interpretar la consulta del usuario y extraer filtros estructurados.
    Retorna un dict con los filtros extraídos.
    """
    from core.ai_utils import ask_ia

    hoy = date.today()
    inicio_semana = hoy - timedelta(days=hoy.weekday())
    fin_semana = inicio_semana + timedelta(days=6)

    prompt_sistema = (
        "Eres un parser de consultas de mantenimiento industrial. "
        "Tu ÚNICA tarea es extraer filtros de búsqueda de la consulta del usuario. "
        "Responde SOLO con un JSON válido, sin texto adicional, sin markdown, sin explicación.\n\n"
        f"Fecha actual: {hoy.isoformat()} (año={hoy.year}, mes={hoy.month}, día_semana={hoy.strftime('%A')})\n"
        f"Esta semana: {inicio_semana.isoformat()} a {fin_semana.isoformat()}\n\n"
        "IMPORTANTE sobre estados del sistema:\n"
        "- ESPERA = Órdenes programadas para el futuro (pendientes de ejecutar)\n"
        "- PROGRAMADA = Órdenes confirmadas para ejecución pronto\n"
        "- EJECUCION = Órdenes en curso ahora\n"
        "- REALIZADA = Órdenes ya completadas en el pasado\n"
        "- CANCELADA = Órdenes canceladas\n\n"
        "Cuando el usuario dice 'programados', 'pendientes', 'van a hacer', 'hay esta semana' → usa estado=null y temporal='futuro' (NO pongas PROGRAMADA, porque las OTs futuras están en ESPERA).\n"
        "Solo usa estado=REALIZADA cuando pregunte explícitamente por 'realizados', 'hechos', 'completados', 'se hicieron'.\n\n"
        "Extrae estos campos si están presentes en la consulta:\n"
        "- tipo: PREVENTIVA, CORRECTIVA, NO_PROGRAMADA (o null si no se menciona)\n"
        "- estado: REALIZADA, CANCELADA, EJECUCION (o null - preferir null para búsquedas generales)\n"
        "- prioridad: BAJA, MEDIA, ALTA, CRITICA (o null)\n"
        "- fecha_desde: fecha YYYY-MM-DD (o null)\n"
        "- fecha_hasta: fecha YYYY-MM-DD (o null)\n"
        "- ubicacion: texto de ubicación mencionada (o null)\n"
        "- rutina: texto de rutina/actividad mencionada (o null)\n"
        "- activo: nombre de equipo/activo mencionado (o null)\n"
        "- tecnico: nombre de técnico mencionado (o null)\n"
        "- temporal: 'pasado' si pregunta por lo ya realizado, 'futuro' si pregunta por pendientes/próximos, null si no es claro\n"
        "- palabras_clave: array de palabras clave relevantes (máx 3, sin stop words)\n\n"
        "Ejemplos:\n"
        f'- "qué preventivos hay programados esta semana" → {{"tipo":"PREVENTIVA","estado":null,"fecha_desde":"{inicio_semana.isoformat()}","fecha_hasta":"{fin_semana.isoformat()}","temporal":"futuro","palabras_clave":[]}}\n'
        f'- "mantenimientos realizados en enero" → {{"tipo":null,"estado":"REALIZADA","fecha_desde":"{hoy.year}-01-01","fecha_hasta":"{hoy.year}-01-31","temporal":"pasado","palabras_clave":[]}}\n'
        f'- "correctivos pendientes de alta prioridad" → {{"tipo":"CORRECTIVA","estado":null,"prioridad":"ALTA","temporal":"futuro","palabras_clave":[]}}\n'
        f'- "trabajos del compresor" → {{"tipo":null,"estado":null,"activo":"compresor","temporal":null,"palabras_clave":["compresor"]}}\n'
    )

    try:
        respuesta = ask_ia(query, context="", system_prompt=prompt_sistema)
        # Limpiar la respuesta: quitar posibles bloques de código markdown
        respuesta_limpia = respuesta.strip()
        if respuesta_limpia.startswith('```'):
            respuesta_limpia = re.sub(r'^```\w*\n?', '', respuesta_limpia)
            respuesta_limpia = re.sub(r'\n?```$', '', respuesta_limpia)
        
        # Intentar extraer JSON de la respuesta si hay texto adicional
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', respuesta_limpia)
        if json_match:
            respuesta_limpia = json_match.group(0)
        
        filtros = json.loads(respuesta_limpia)
        return filtros
    except (json.JSONDecodeError, Exception) as e:
        print(f"[AI Search] Error interpretando consulta: {e}")
        # Fallback: extraer información básica con regex
        return _fallback_parse(query)


def _fallback_parse(query):
    """Parser de fallback si la IA no puede interpretar la consulta."""
    filtros = {
        'tipo': None, 'estado': None, 'prioridad': None,
        'fecha_desde': None, 'fecha_hasta': None,
        'ubicacion': None, 'rutina': None, 'activo': None,
        'tecnico': None, 'temporal': None, 'palabras_clave': []
    }

    q = query.lower()

    # Detectar tipo
    if 'preventiv' in q:
        filtros['tipo'] = 'PREVENTIVA'
    elif 'correctiv' in q:
        filtros['tipo'] = 'CORRECTIVA'
    elif 'no programad' in q:
        filtros['tipo'] = 'NO_PROGRAMADA'

    # Detectar temporalidad - NO forzar estado PROGRAMADA
    if any(w in q for w in ['hicieron', 'realizaron', 'realizados', 'hizo', 'pasado', 'completad', 'se hicieron']):
        filtros['estado'] = 'REALIZADA'
        filtros['temporal'] = 'pasado'
    elif any(w in q for w in ['cancelad']):
        filtros['estado'] = 'CANCELADA'
        filtros['temporal'] = 'pasado'
    elif any(w in q for w in ['pendiente', 'programad', 'van a hacer', 'próxim', 'futuro', 'esta semana', 'hay']):
        # NO asignar estado - las OTs futuras pueden estar en ESPERA o PROGRAMADA
        filtros['temporal'] = 'futuro'

    # Detectar fechas relativas
    hoy = date.today()
    if 'esta semana' in q or 'semana actual' in q:
        inicio_semana = hoy - timedelta(days=hoy.weekday())
        fin_semana = inicio_semana + timedelta(days=6)
        filtros['fecha_desde'] = inicio_semana.isoformat()
        filtros['fecha_hasta'] = fin_semana.isoformat()
    elif 'próxima semana' in q or 'siguiente semana' in q:
        inicio = hoy + timedelta(days=(7 - hoy.weekday()))
        filtros['fecha_desde'] = inicio.isoformat()
        filtros['fecha_hasta'] = (inicio + timedelta(days=6)).isoformat()
    elif 'este mes' in q or 'mes actual' in q:
        import calendar as cal
        filtros['fecha_desde'] = hoy.replace(day=1).isoformat()
        ultimo_dia = cal.monthrange(hoy.year, hoy.month)[1]
        filtros['fecha_hasta'] = hoy.replace(day=ultimo_dia).isoformat()
    elif 'hoy' in q:
        filtros['fecha_desde'] = hoy.isoformat()
        filtros['fecha_hasta'] = hoy.isoformat()
    elif 'último mes' in q or 'mes pasado' in q:
        import calendar as cal
        if hoy.month == 1:
            mes_ant = 12
            anio_ant = hoy.year - 1
        else:
            mes_ant = hoy.month - 1
            anio_ant = hoy.year
        filtros['fecha_desde'] = date(anio_ant, mes_ant, 1).isoformat()
        ultimo_dia = cal.monthrange(anio_ant, mes_ant)[1]
        filtros['fecha_hasta'] = date(anio_ant, mes_ant, ultimo_dia).isoformat()
    else:
        # Detectar nombres de meses
        import calendar as cal
        meses_map = {
            'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4,
            'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
            'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
        }
        for nombre_mes, num_mes in meses_map.items():
            if nombre_mes in q:
                # Detectar año si está presente
                anio_match = re.search(r'20\d{2}', q)
                anio = int(anio_match.group()) if anio_match else hoy.year
                filtros['fecha_desde'] = date(anio, num_mes, 1).isoformat()
                ultimo_dia = cal.monthrange(anio, num_mes)[1]
                filtros['fecha_hasta'] = date(anio, num_mes, ultimo_dia).isoformat()
                break

    # Detectar prioridad
    if 'urgente' in q or 'crítica' in q or 'critica' in q:
        filtros['prioridad'] = 'CRITICA'
    elif 'alta' in q and ('prioridad' in q or 'urgencia' in q):
        filtros['prioridad'] = 'ALTA'

    # Extraer palabras clave (sin stop words)
    stop_words = {'que', 'se', 'de', 'en', 'la', 'el', 'los', 'las', 'un', 'una', 'por', 'para',
                  'con', 'del', 'al', 'me', 'mi', 'tu', 'su', 'nos', 'les', 'qué', 'cuáles',
                  'como', 'dime', 'muestra', 'busca', 'encuentra', 'cuántos', 'hay', 'hicieron',
                  'van', 'hacer', 'hizo', 'son', 'fue', 'fueron', 'está', 'están', 'tiene', 'o', 'y',
                  'esta', 'semana', 'mes', 'año', 'mantenimiento', 'mantenimientos', 'programados',
                  'programadas', 'pendientes', 'hay', 'qué', 'cuales'}
    palabras = [w for w in re.findall(r'\w+', q) if w not in stop_words and len(w) > 2]
    filtros['palabras_clave'] = palabras[:3]

    return filtros


def _buscar_ordenes(query, filtros):
    """Busca órdenes de trabajo con los filtros interpretados.
    Estrategia: búsqueda progresiva. Si los filtros son muy estrictos y no 
    devuelven resultados, se relajan automáticamente.
    """
    qs = OrdenTrabajo.objects.select_related(
        'rutina', 'rutina__tipo', 'rutina__frecuencia',
        'ubicacion', 'tecnico', 'programacion'
    ).prefetch_related('activos')

    # Aplicar filtros estructurados
    if filtros.get('tipo'):
        qs = qs.filter(tipo=filtros['tipo'])

    # INTELIGENCIA DE ESTADOS:
    # - Si el usuario pregunta por "futuro/pendientes/programados" → incluir ESPERA + PROGRAMADA + EJECUCION
    # - Si el usuario pregunta por "pasado/realizados" → solo REALIZADA
    # - Si especifica un estado exacto → usarlo
    temporal = filtros.get('temporal')
    estado = filtros.get('estado')
    
    if estado == 'REALIZADA':
        qs = qs.filter(estado='REALIZADA')
    elif estado == 'CANCELADA':
        qs = qs.filter(estado='CANCELADA')
    elif estado == 'EJECUCION':
        qs = qs.filter(estado='EJECUCION')
    elif temporal == 'futuro':
        # Las OTs futuras están en ESPERA, PROGRAMADA o EJECUCION
        qs = qs.filter(estado__in=['ESPERA', 'PROGRAMADA', 'EJECUCION'])
    elif temporal == 'pasado':
        qs = qs.filter(estado='REALIZADA')
    # Si temporal es null y no hay estado, no filtrar por estado (buscar en todo)

    if filtros.get('prioridad'):
        qs = qs.filter(prioridad=filtros['prioridad'])

    if filtros.get('fecha_desde'):
        try:
            fd = datetime.strptime(filtros['fecha_desde'], '%Y-%m-%d').date()
            qs = qs.filter(inicio_programado__date__gte=fd)
        except (ValueError, TypeError):
            pass

    if filtros.get('fecha_hasta'):
        try:
            fh = datetime.strptime(filtros['fecha_hasta'], '%Y-%m-%d').date()
            qs = qs.filter(inicio_programado__date__lte=fh)
        except (ValueError, TypeError):
            pass

    if filtros.get('ubicacion'):
        qs = qs.filter(ubicacion__nombre__icontains=filtros['ubicacion'])

    if filtros.get('rutina'):
        qs = qs.filter(
            Q(rutina__nombre__icontains=filtros['rutina']) |
            Q(descripcion_corta__icontains=filtros['rutina'])
        )

    if filtros.get('activo'):
        qs = qs.filter(
            Q(activos__nombre__icontains=filtros['activo']) |
            Q(activos__codigo_interno__icontains=filtros['activo'])
        )

    if filtros.get('tecnico'):
        qs = qs.filter(
            Q(tecnico__first_name__icontains=filtros['tecnico']) |
            Q(tecnico__last_name__icontains=filtros['tecnico']) |
            Q(tecnico__username__icontains=filtros['tecnico'])
        )

    # Búsqueda textual con palabras clave (solo si no hay otros filtros suficientes)
    palabras = filtros.get('palabras_clave', [])
    has_specific_filters = any([
        filtros.get('tipo'), filtros.get('fecha_desde'), filtros.get('fecha_hasta'),
        filtros.get('ubicacion'), filtros.get('rutina'), filtros.get('activo'), filtros.get('tecnico')
    ])
    
    if palabras and not has_specific_filters:
        text_q = Q()
        for palabra in palabras:
            text_q |= (
                Q(descripcion_corta__icontains=palabra) |
                Q(rutina__nombre__icontains=palabra) |
                Q(ubicacion__nombre__icontains=palabra) |
                Q(notas__icontains=palabra) |
                Q(codigo_de_orden__icontains=palabra)
            )
        qs = qs.filter(text_q)

    ots = qs.distinct().order_by('-inicio_programado')[:40]

    resultados = _serializar_ordenes(list(ots))
    return resultados


def _serializar_ordenes(ots):
    """Convierte una lista de OTs en resultados serializables."""
    resultados = []
    for ot in ots:
        activos_list = list(ot.activos.values_list('nombre', flat=True)[:3])
        resultados.append({
            'id': ot.id,
            'type': 'orden_trabajo',
            'codigo': ot.codigo_de_orden or f'OT-{ot.id}',
            'titulo': ot.descripcion_corta or (ot.rutina.nombre if ot.rutina else 'Sin descripción'),
            'tipo': ot.get_tipo_display(),
            'tipo_raw': ot.tipo,
            'estado': ot.get_estado_display(),
            'estado_raw': ot.estado,
            'prioridad': ot.get_prioridad_display(),
            'prioridad_raw': ot.prioridad,
            'ubicacion': ot.ubicacion.nombre if ot.ubicacion else 'Sin ubicación',
            'fecha_programada': ot.inicio_programado.strftime('%d/%m/%Y') if ot.inicio_programado else '',
            'fecha_iso': ot.inicio_programado.isoformat() if ot.inicio_programado else '',
            'tecnico': ot.tecnico.get_full_name() if ot.tecnico else 'Sin asignar',
            'rutina': ot.rutina.nombre if ot.rutina else '',
            'activos': activos_list,
            'url': f'/admin/mantenimiento/ordentrabajo/{ot.id}/change/',
            'relevancia': 'filtro',
        })
    return resultados


def _buscar_planificacion_mensual(query, filtros):
    """
    Busca OTs en el cronograma sin restriccion de estado.
    Encuentra mantenimientos programados (estado ESPERA) que aparecen en la 
    vista de cronograma mensual pero no aparecen con filtro REALIZADA.
    """
    qs = OrdenTrabajo.objects.select_related(
        'rutina', 'rutina__tipo', 'rutina__frecuencia',
        'ubicacion', 'tecnico', 'programacion'
    ).prefetch_related('activos')

    # Solo activar si hay fecha y/o ubicacion
    if not filtros.get('fecha_desde') and not filtros.get('ubicacion'):
        return []

    # No filtrar por estado - buscar TODO lo programado en esa fecha/ubicacion
    if filtros.get('fecha_desde'):
        try:
            fd = datetime.strptime(filtros['fecha_desde'], '%Y-%m-%d').date()
            qs = qs.filter(inicio_programado__date__gte=fd)
        except (ValueError, TypeError):
            pass

    if filtros.get('fecha_hasta'):
        try:
            fh = datetime.strptime(filtros['fecha_hasta'], '%Y-%m-%d').date()
            qs = qs.filter(inicio_programado__date__lte=fh)
        except (ValueError, TypeError):
            pass

    if filtros.get('ubicacion'):
        qs = qs.filter(ubicacion__nombre__icontains=filtros['ubicacion'])

    if filtros.get('tipo'):
        qs = qs.filter(tipo=filtros['tipo'])

    if filtros.get('rutina'):
        qs = qs.filter(
            Q(rutina__nombre__icontains=filtros['rutina']) |
            Q(descripcion_corta__icontains=filtros['rutina'])
        )

    ots = qs.distinct().order_by('-inicio_programado')[:30]
    return _serializar_ordenes(list(ots))


def _buscar_programaciones(query, filtros):
    """Busca programaciones activas que coincidan."""
    qs = Programacion.objects.select_related(
        'rutina', 'rutina__tipo', 'rutina__frecuencia'
    ).prefetch_related('areas', 'horarios')

    # Solo buscar programaciones si la consulta parece ser sobre cronograma/futuro
    temporal = filtros.get('temporal')
    if temporal == 'pasado':
        return []  # Las programaciones son planes futuros

    if filtros.get('rutina'):
        qs = qs.filter(rutina__nombre__icontains=filtros['rutina'])

    if filtros.get('ubicacion'):
        qs = qs.filter(areas__nombre__icontains=filtros['ubicacion'])

    if filtros.get('tipo'):
        qs = qs.filter(rutina__tipo__nombre__icontains=filtros['tipo'])

    palabras = filtros.get('palabras_clave', [])
    if palabras:
        text_q = Q()
        for palabra in palabras:
            text_q |= (
                Q(rutina__nombre__icontains=palabra) |
                Q(areas__nombre__icontains=palabra) |
                Q(rutina__tipo__nombre__icontains=palabra)
            )
        qs = qs.filter(text_q)

    progs = qs.distinct()[:10]

    resultados = []
    for prog in progs:
        areas = list(prog.areas.values_list('nombre', flat=True)[:3])
        horarios = list(prog.horarios.values_list('nombre', flat=True))
        resultados.append({
            'id': prog.id,
            'type': 'programacion',
            'codigo': f'PROG-{prog.id}',
            'titulo': prog.rutina.nombre if prog.rutina else f'Programación #{prog.id}',
            'tipo': prog.rutina.tipo.nombre if prog.rutina and prog.rutina.tipo else 'General',
            'tipo_raw': 'PROGRAMACION',
            'estado': 'Activa' if (not prog.fecha_fin or prog.fecha_fin >= date.today()) else 'Finalizada',
            'estado_raw': 'ACTIVA',
            'prioridad': '',
            'prioridad_raw': '',
            'ubicacion': ', '.join(areas) if areas else 'Sin áreas',
            'fecha_programada': f'{prog.fecha_inicio.strftime("%d/%m/%Y")} → {prog.fecha_fin.strftime("%d/%m/%Y") if prog.fecha_fin else "Indefinido"}',
            'fecha_iso': prog.fecha_inicio.isoformat(),
            'tecnico': '',
            'rutina': prog.rutina.nombre if prog.rutina else '',
            'frecuencia': prog.rutina.frecuencia.nombre if prog.rutina and prog.rutina.frecuencia else '',
            'horarios': horarios,
            'activos': areas,
            'url': f'/mantenimiento/proyeccion/{prog.id}/',
            'relevancia': 'filtro',
        })

    return resultados


def _buscar_vectorial(query):
    """Usa búsqueda vectorial semántica si hay embeddings disponibles."""
    try:
        from core.ai_utils import get_embedding

        # Verificar que haya OTs con embeddings
        tiene_embeddings = OrdenTrabajo.objects.filter(embedding__isnull=False).exists()
        if not tiene_embeddings:
            return []

        query_embedding = get_embedding(query, task_type="retrieval_query", dimensions=768)
        if not query_embedding:
            return []

        ots_semanticas = OrdenTrabajo.buscar_vectorial(query_embedding, limit=10)

        resultados = []
        for ot in ots_semanticas:
            activos_list = list(ot.activos.values_list('nombre', flat=True)[:3])
            resultados.append({
                'id': ot.id,
                'type': 'orden_trabajo',
                'codigo': ot.codigo_de_orden or f'OT-{ot.id}',
                'titulo': ot.descripcion_corta or (ot.rutina.nombre if ot.rutina else 'Sin descripción'),
                'tipo': ot.get_tipo_display(),
                'tipo_raw': ot.tipo,
                'estado': ot.get_estado_display(),
                'estado_raw': ot.estado,
                'prioridad': ot.get_prioridad_display(),
                'prioridad_raw': ot.prioridad,
                'ubicacion': ot.ubicacion.nombre if ot.ubicacion else 'Sin ubicación',
                'fecha_programada': ot.inicio_programado.strftime('%d/%m/%Y') if ot.inicio_programado else '',
                'fecha_iso': ot.inicio_programado.isoformat() if ot.inicio_programado else '',
                'tecnico': ot.tecnico.get_full_name() if ot.tecnico else 'Sin asignar',
                'rutina': ot.rutina.nombre if ot.rutina else '',
                'activos': activos_list,
                'url': f'/admin/mantenimiento/ordentrabajo/{ot.id}/change/',
                'relevancia': 'semantica',
                'distancia': round(ot.distancia, 4) if hasattr(ot, 'distancia') else None,
            })

        return resultados
    except Exception as e:
        print(f"[AI Search] Error búsqueda vectorial: {e}")
        return []


def _combinar_resultados(ots, programaciones, vectorial):
    """Combina y deduplica resultados de las diferentes fuentes."""
    vistos = set()
    combinados = []

    # Primero los de filtro SQL (más precisos)
    for r in ots:
        key = f"{r['type']}_{r['id']}"
        if key not in vistos:
            vistos.add(key)
            combinados.append(r)

    # Luego programaciones
    for r in programaciones:
        key = f"{r['type']}_{r['id']}"
        if key not in vistos:
            vistos.add(key)
            combinados.append(r)

    # Finalmente vectoriales (pueden agregar OTs que no fueron encontradas por filtros)
    for r in vectorial:
        key = f"{r['type']}_{r['id']}"
        if key not in vistos:
            vistos.add(key)
            combinados.append(r)

    return combinados


def _generar_respuesta_ia(query, resultados, filtros):
    """Genera una respuesta en lenguaje natural usando IA."""
    from core.ai_utils import ask_ia

    # Construir contexto con los resultados
    if not resultados:
        context = "No se encontraron resultados para la búsqueda en la base de datos."
    else:
        context_parts = [f"Se encontraron {len(resultados)} resultados:\n"]

        # Resumen por tipo
        ots = [r for r in resultados if r['type'] == 'orden_trabajo']
        progs = [r for r in resultados if r['type'] == 'programacion']

        if ots:
            # Agrupar por estado
            estados = {}
            for ot in ots:
                est = ot['estado']
                estados[est] = estados.get(est, 0) + 1
            context_parts.append(f"Órdenes de Trabajo ({len(ots)}): " + ", ".join(f"{v} {k}" for k, v in estados.items()))

            # Agrupar por ubicación
            ubicaciones = {}
            for ot in ots:
                ub = ot['ubicacion']
                ubicaciones[ub] = ubicaciones.get(ub, 0) + 1
            if len(ubicaciones) <= 10:
                context_parts.append("Por ubicación: " + ", ".join(f"{v} en {k}" for k, v in sorted(ubicaciones.items(), key=lambda x: -x[1])[:8]))

            # Mostrar las primeras 15 detalladas
            context_parts.append("\nDetalle de las primeras órdenes:")
            for ot in ots[:15]:
                activos_str = ', '.join(ot.get('activos', [])) if ot.get('activos') else 'N/A'
                context_parts.append(
                    f"- {ot['codigo']} | {ot['tipo']} | {ot['estado']} | "
                    f"Fecha: {ot['fecha_programada']} | Ubicación: {ot['ubicacion']} | "
                    f"Rutina: {ot['rutina']} | Activos: {activos_str} | "
                    f"Técnico: {ot['tecnico']}"
                )

        if progs:
            context_parts.append(f"\nProgramaciones activas ({len(progs)}):")
            for prog in progs[:5]:
                context_parts.append(
                    f"- {prog['codigo']} | {prog['titulo']} | "
                    f"Áreas: {prog['ubicacion']} | Frecuencia: {prog.get('frecuencia', 'N/A')}"
                )

        context = "\n".join(context_parts)

    system_prompt = (
        "Eres un asistente experto en gestión de mantenimiento industrial (CMMS). "
        "El usuario pregunta sobre mantenimientos (pasados o futuros). "
        "Responde de manera clara, profesional y concisa en español. "
        "REGLAS:\n"
        "1. Resume los resultados de forma útil para un jefe de mantenimiento.\n"
        "2. Si hay muchos resultados, agrúpalos por ubicación o tipo de trabajo.\n"
        "3. Menciona la cantidad total y datos clave como ubicaciones y fechas.\n"
        "4. Si no hay resultados, sugiere cómo reformular la búsqueda.\n"
        "5. Usa formato con viñetas y negritas (markdown) para facilitar la lectura.\n"
        "6. NO inventes datos que no estén en el contexto proporcionado.\n"
        "7. Si detectas patrones interesantes (concentración en un área, muchos de un tipo), menciónalo.\n"
        "8. Nota: El estado 'En Espera de Programación' significa que la OT ya está creada y pendiente de ejecutar.\n"
        "9. Máximo 250 palabras. Sé directo y útil.\n"
    )

    try:
        respuesta = ask_ia(query, context=context, system_prompt=system_prompt)
        return respuesta
    except Exception as e:
        print(f"[AI Search] Error generando respuesta: {e}")
        # Respuesta de fallback sin IA
        if resultados:
            return f"Se encontraron **{len(resultados)} resultados** para tu búsqueda. Revisa la tabla de resultados a continuación."
        return "No se encontraron resultados para tu consulta. Intenta con otros términos."
