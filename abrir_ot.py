"""CLI para buscar y abrir Ordenes de Trabajo (OT) del sistema.

Modo menu interactivo (recomendado):
    python abrir_ot.py                        # Abre el menu de busquedas y filtros

Modo directo por argumentos:
    python abrir_ot.py OT-000000011           # Abre una OT por codigo o ID
    python abrir_ot.py --query "compresor"    # Busca por texto
    python abrir_ot.py --estado EJECUCION     # Filtra por estado
    python abrir_ot.py --tipo CORRECTIVA      # Filtra por tipo
    python abrir_ot.py --prioridad ALTA       # Filtra por prioridad
    python abrir_ot.py --desde 2026-01-01     # Filtro por fecha inicial
    python abrir_ot.py --hasta 2026-06-30     # Filtro por fecha final
    python abrir_ot.py --listar               # Abre la lista completa de OTs
    python abrir_ot.py --url http://127.0.0.1:8000
    python abrir_ot.py --no-browser           # Solo imprime la URL
"""

import argparse
import os
import sys
import webbrowser
from datetime import date, datetime, timedelta

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

from django.db.models import Count  # noqa: E402
from django.urls import reverse  # noqa: E402

from activos.models import Categoria  # noqa: E402
from mantenimiento.models import OrdenTrabajo, Tipo  # noqa: E402

ESTADOS = dict(OrdenTrabajo.ESTADO_CHOICES)
TIPOS = dict(OrdenTrabajo.TIPO_CHOICES)
PRIORIDADES = dict(OrdenTrabajo.PRIORIDAD_CHOICES)

ADMIN_CHANGE_URL = reverse('admin:mantenimiento_ordentrabajo_change', args=[0]).replace('/0/', '/{id}/')
ADMIN_CHANGELIST_URL = reverse('admin:mantenimiento_ordentrabajo_changelist')

DEFAULT_LIMITE = 60


# ---------------------------------------------------------------------------
# Filtros
# ---------------------------------------------------------------------------
def filtros_vacios():
    return {
        'texto': None,
        'estado': None,
        'tipo_ot': None,
        'prioridad': None,
        'tipo_mtto': None,        # id de Tipo (rutina__tipo, arbol)
        'categoria_activo': None, # id de Categoria (rutina__categoria_activo)
        'desde': None,
        'hasta': None,
    }


def resumen_filtros(f):
    partes = []
    if f['texto']:
        partes.append(f"texto='{f['texto']}'")
    if f['estado']:
        partes.append(f"estado={f['estado']}")
    if f['tipo_ot']:
        partes.append(f"tipo={f['tipo_ot']}")
    if f['prioridad']:
        partes.append(f"prioridad={f['prioridad']}")
    if f['tipo_mtto']:
        try:
            t = Tipo.objects.get(id=f['tipo_mtto'])
            partes.append(f"cat. mantenimiento='{t.get_ruta_completa()}'")
        except Tipo.DoesNotExist:
            f['tipo_mtto'] = None
    if f['categoria_activo']:
        try:
            c = Categoria.objects.get(id=f['categoria_activo'])
            partes.append(f"cat. activo='{c.nombre}'")
        except Categoria.DoesNotExist:
            f['categoria_activo'] = None
    if f['desde'] or f['hasta']:
        partes.append(f"fechas [{f['desde'] or 'inicio'} -> {f['hasta'] or 'hoy'}]")
    return ", ".join(partes) if partes else "ninguno"


def construir_queryset(f, limite=DEFAULT_LIMITE):
    qs = OrdenTrabajo.objects.all().select_related('rutina', 'aviso', 'ubicacion', 'tecnico')

    if f['estado']:
        qs = qs.filter(estado=f['estado'])
    if f['tipo_ot']:
        qs = qs.filter(tipo=f['tipo_ot'])
    if f['prioridad']:
        qs = qs.filter(prioridad=f['prioridad'])
    if f['tipo_mtto']:
        tids = list(Tipo.objects.get(id=f['tipo_mtto']).get_descendants().values_list('id', flat=True))
        qs = qs.filter(rutina__tipo__id__in=tids)
    if f['categoria_activo']:
        qs = qs.filter(rutina__categoria_activo_id=f['categoria_activo'])
    if f['desde']:
        qs = qs.filter(inicio_programado__date__gte=f['desde'])
    if f['hasta']:
        qs = qs.filter(inicio_programado__date__lte=f['hasta'])
    if f['texto']:
        texto = f['texto'].strip()
        if texto.isdigit():
            qs = qs.filter(
                django.db.models.Q(id=texto) | django.db.models.Q(codigo_de_orden__icontains=texto)
            )
        else:
            qs = qs.filter(
                django.db.models.Q(codigo_de_orden__icontains=texto)
                | django.db.models.Q(descripcion_corta__icontains=texto)
                | django.db.models.Q(descripcion_detallada__icontains=texto)
                | django.db.models.Q(rutina__nombre__icontains=texto)
                | django.db.models.Q(aviso__descripcion__icontains=texto)
                | django.db.models.Q(ubicacion__nombre__icontains=texto)
            )

    return qs.order_by('-inicio_programado')[:limite]


# ---------------------------------------------------------------------------
# Formato y apertura
# ---------------------------------------------------------------------------
def formatear(ot, idx=0):
    nombre = (
        ot.rutina.nombre if ot.rutina
        else (ot.aviso.descripcion[:40] if ot.aviso else ot.descripcion_corta or '')
    )
    if not nombre:
        nombre = 'OT Correctiva'
    lugar = ot.ubicacion.nombre if ot.ubicacion else 'S/U'
    fecha = ot.inicio_programado.date().isoformat() if ot.inicio_programado else 'S/F'
    estado = ESTADOS.get(ot.estado, ot.estado)
    prio = ot.get_prioridad_display() if ot.prioridad else '-'
    codigo = ot.codigo_de_orden or f'(#{ot.id})'
    indice = f"[{idx:>3}] " if idx else ""
    return (
        f"{indice}{codigo:<18} {ot.get_tipo_display():<12} {estado:<24} "
        f"{prio:<8} {fecha} | {nombre} - {lugar}"
    )


def url_de_ot(ot_id, base_url):
    return f"{base_url.rstrip('/')}{ADMIN_CHANGE_URL.format(id=ot_id)}"


def abrir(url, con_navegador):
    print(f"\n  URL: {url}")
    if con_navegador:
        webbrowser.open(url, new=0)
    else:
        print("  (no-browser activo, no se abrio el navegador)")


# ---------------------------------------------------------------------------
# Interaccion
# ---------------------------------------------------------------------------
def preguntar(prompt):
    try:
        return input(prompt).strip()
    except (KeyboardInterrupt, EOFError):
        print("\n  (salir)")
        return None


def menu_opciones(titulo, opciones, cerrar_texto="Volver"):
    """Muestra opciones numeradas y devuelve el indice elegido (None=volver).
    opciones: lista de (texto, valor)."""
    print(f"\n  {titulo}\n")
    for i, (texto, _) in enumerate(opciones, start=1):
        print(f"    {i:>3}. {texto}")
    print(f"      0. {cerrar_texto}")
    print()
    while True:
        r = preguntar("  Elige: ")
        if r is None:
            return None
        if not r:
            return None
        if r.isdigit():
            n = int(r)
            if n == 0:
                return None
            if 1 <= n <= len(opciones):
                return opciones[n - 1][1]
        print(f"    Entrada no valida (1-{len(opciones)} o 0).")


def parsear_fecha(texto):
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'):
        try:
            return datetime.strptime(texto, fmt).date()
        except ValueError:
            continue
    return None


def menu_tipos_mtto(f):
    """Menu de categorias de mantenimiento (arbol de Tipo)."""
    roots = list(
        Tipo.objects.filter(padre__isnull=True)
        .annotate(n=Count('rutinas__ordenes'))
        .filter(n__gt=0)
        .order_by('-n')
    )
    if not roots:
        print("\n  No hay categorias de mantenimiento con OTs.")
        return

    opciones = [(f"{t.nombre}  ({t.n} OTs)", t.id) for t in roots]
    elegido = menu_opciones("CATEGORIA DE MANTENIMIENTO (disponibles con OTs):", opciones)
    if elegido is not None:
        f['tipo_mtto'] = elegido
        print(f"\n  Filtro aplicado: {resumen_filtros(f)}")


def menu_categorias_activo(f):
    cats = list(
        Categoria.objects.annotate(n=Count('rutinas_categoria__ordenes'))
        .filter(n__gt=0)
        .order_by('-n')
    )
    if not cats:
        print("\n  No hay categorias de activo con OTs.")
        return

    opciones = [(f"{c.nombre}  ({c.n} OTs)", c.id) for c in cats]
    elegido = menu_opciones("CATEGORIA DE ACTIVO (disponibles con OTs):", opciones)
    if elegido is not None:
        f['categoria_activo'] = elegido
        print(f"\n  Filtro aplicado: {resumen_filtros(f)}")


def menu_fechas(f):
    hoy = date.today()
    presets = [
        (f"Hoy ({hoy.isoformat()})", (hoy, hoy)),
        ("Ultimos 7 dias", (hoy - timedelta(days=6), hoy)),
        ("Ultimos 30 dias", (hoy - timedelta(days=29), hoy)),
        ("Este mes", (hoy.replace(day=1), hoy)),
        ("Este anio", (hoy.replace(month=1, day=1), hoy)),
        ("Todo el historial", (None, None)),
    ]
    opciones = [(txt, val) for txt, val in presets]
    eleccion = menu_opciones("RANGO DE FECHAS (por fecha programada):", opciones)
    if eleccion is None:
        return
    f['desde'], f['hasta'] = eleccion
    print(f"\n  Filtro aplicado: {resumen_filtros(f)}")


def menu_estado(f):
    opciones = [(f"{k} - {v}", k) for k, v in ESTADOS.items()]
    elegido = menu_opciones("ESTADO:", opciones)
    if elegido is not None:
        f['estado'] = elegido
        print(f"\n  Filtro aplicado: {resumen_filtros(f)}")


def menu_tipo_ot(f):
    opciones = [(v, k) for k, v in TIPOS.items()]
    elegido = menu_opciones("TIPO DE OT:", opciones)
    if elegido is not None:
        f['tipo_ot'] = elegido
        print(f"\n  Filtro aplicado: {resumen_filtros(f)}")


def menu_prioridad(f):
    opciones = [(v, k) for k, v in PRIORIDADES.items()]
    elegido = menu_opciones("PRIORIDAD:", opciones)
    if elegido is not None:
        f['prioridad'] = elegido
        print(f"\n  Filtro aplicado: {resumen_filtros(f)}")


def menu_texto(f):
    r = preguntar("\n  Texto a buscar (codigo, descripcion, ubicacion, rutina; Enter=limpiar): ")
    if r is None:
        return
    f['texto'] = r or None
    print(f"\n  Filtro aplicado: {resumen_filtros(f)}")


def menu_limpiar(f):
    f.update(filtros_vacios())
    print("\n  Filtros limpiados.")


def _abrir_lista(elegidas, base_url, con_navegador):
    print()
    for ot in elegidas:
        url = url_de_ot(ot.id, base_url)
        print(f"  Abriendo {ot.codigo_de_orden or ot.id} -> {url}")
        abrir(url, con_navegador)


def _numeros_validos(texto, maximo):
    numeros = []
    for parte in texto.replace(',', ' ').split():
        if not parte.isdigit():
            return None
        numeros.append(int(parte))
    if not numeros:
        return None
    if any(n < 1 or n > maximo for n in numeros):
        return None
    return list(dict.fromkeys(numeros))


def _confirmar_eliminacion(ots):
    """Pide confirmacion explicita antes de eliminar. Devuelve True si se procede."""
    print("\n" + "-" * 115)
    print("  ADVERTENCIA: Se eliminar\u00e1n definitivamente las siguientes OT:")
    print("-" * 115)
    for i, ot in enumerate(ots, start=1):
        print(f"  {i:>3}. {ot.codigo_de_orden or ot.id}  [{ESTADOS.get(ot.estado, ot.estado)}]  {ot.descripcion_corta or ''}")
    print("-" * 115)
    r = preguntar(f"  Confirmar eliminacion de {len(ots)} OT(s)? Escribe SI para confirmar (Enter=cancelar): ")
    return r is not None and r.strip().upper() == 'SI'


def _borrar_ots(ots):
    """Elimina las OTs. Respeta la misma restriccion que la API web (no elimina REALIZADA/CANCELADA)."""
    eliminables = [ot for ot in ots if ot.estado in ('ESPERA', 'PROGRAMADA', 'EJECUCION')]
    bloqueadas = [ot for ot in ots if ot.estado not in ('ESPERA', 'PROGRAMADA', 'EJECUCION')]

    if bloqueadas:
        print("\n  OTs NO eliminadas (estado no permitido):")
        for ot in bloqueadas:
            print(f"    - {ot.codigo_de_orden or ot.id}  [{ESTADOS.get(ot.estado, ot.estado)}]")

    if not eliminables:
        print("\n  Ninguna OT eliminable (solo ESPERA, PROGRAMADA o EJECUCION).")
        return

    if not _confirmar_eliminacion(eliminables):
        print("\n  Eliminacion cancelada.")
        return

    for ot in eliminables:
        try:
            ot.delete()
            print(f"  Eliminada {ot.codigo_de_orden or ot.id}")
        except Exception as e:
            print(f"  Error eliminando {ot.codigo_de_orden or ot.id}: {e}")
    print(f"\n  {len(eliminables)} OT(s) eliminadas.")


def _mostrar_resultados(resultados, marcadas):
    print("\n" + "-" * 115)
    for i, ot in enumerate(resultados, start=1):
        marca = "X" if i in marcadas else " "
        print(f" [{marca}] " + formatear(ot, i))
    print("-" * 115)


def interactuar_resultados(resultados, base_url, con_navegador):
    """Permite abrir y/o marcar y eliminar OTs de la lista."""
    if not resultados:
        return

    if len(resultados) == 1:
        _mostrar_resultados(resultados, set())
        print("  [1] Unica OT encontrada.")
        r = preguntar("  Accion: Enter=abrir | d=eliminar | x=volver: ")
        if r is None or r == '':
            _abrir_lista(resultados, base_url, con_navegador)
        elif r.strip().lower() == 'd':
            _borrar_ots(resultados)
        return

    marcadas = set()
    print(f"\n  {len(resultados)} OT(s). Uso:\n"
          "    1,3,5         abrir esas OT\n"
          "    a             abrir todas\n"
          "    m 1,3,5       marcar/desmarcar para eliminar\n"
          "    ma            marcar todas\n"
          "    s             mostrar seleccion\n"
          "    d             eliminar OT marcadas\n"
          "    Enter         volver")
    _mostrar_resultados(resultados, marcadas)

    while True:
        r = preguntar("  Comando: ")
        if r is None or r == '':
            return
        cmd = r.strip().lower()
        if not cmd:
            return

        if cmd == 'a':
            _abrir_lista(resultados, base_url, con_navegador)
            return
        if cmd == 'ma':
            marcadas = set(range(1, len(resultados) + 1))
            _mostrar_resultados(resultados, marcadas)
            continue
        if cmd == 's':
            if marcadas:
                print("\n  Seleccionadas para eliminar:")
                for i in sorted(marcadas):
                    ot = resultados[i - 1]
                    print(f"    {i:>3}. {ot.codigo_de_orden or ot.id}  [{ESTADOS.get(ot.estado, ot.estado)}]")
            else:
                print("\n  (sin seleccion)")
            continue
        if cmd == 'd':
            if not marcadas:
                print("  Marca primero con 'm 1,3,5' o 'ma'.")
                continue
            ots = [resultados[i - 1] for i in sorted(marcadas)]
            _borrar_ots(ots)
            marcadas = set()
            continue

        if cmd.startswith('m '):
            nums = _numeros_validos(cmd[2:], len(resultados))
            if nums is None:
                print("    N\u00fameros no validos.")
                continue
            for n in nums:
                if n in marcadas:
                    marcadas.discard(n)
                else:
                    marcadas.add(n)
            _mostrar_resultados(resultados, marcadas)
            continue

        nums = _numeros_validos(cmd, len(resultados))
        if nums is None:
            print("    Entrada no valida. Ayuda: 1,3,5 | a | m 1,3,5 | ma | s | d | Enter")
            continue
        _abrir_lista([resultados[n - 1] for n in nums], base_url, con_navegador)
        return


def listar_y_abrir(f, base_url, con_navegador):
    qs = construir_queryset(f)
    total = qs.count()
    print(f"\n  Resultados con filtros [{resumen_filtros(f)}]: {total} OT(s).")
    if total == 0:
        print("\n  No se encontraron OTs con esos criterios.")
        return

    resultados = list(qs)
    interactuar_resultados(resultados, base_url, con_navegador)


def menu_principal(base_url, con_navegador):
    f = filtros_vacios()
    while True:
        print("\n" + "=" * 115)
        print("  MENU OT - BUSQUEDA Y APERTURA DE ORDENES DE TRABAJO")
        print("=" * 115)
        print(f"\n  Filtros actuales: {resumen_filtros(f)}")
        opciones = [
            ("Buscar por texto", 'texto'),
            ("Categoria de mantenimiento (Tipo)", 'tipo_mtto'),
            ("Categoria de activo", 'categoria_activo'),
            ("Rango de fechas", 'fechas'),
            ("Estado", 'estado'),
            ("Tipo de OT", 'tipo_ot'),
            ("Prioridad", 'prioridad'),
            ("Limpiar filtros", 'limpiar'),
            ("Listar y abrir OT(s)", 'listar'),
            ("Abrir lista completa en navegador", 'changelist'),
            ("Salir", 'salir'),
        ]
        for i, (texto, _) in enumerate(opciones, start=1):
            print(f"    {i:>3}. {texto}")
        print()
        r = preguntar("  Elige opcion: ")
        if r is None:
            return
        if not r.isdigit() or not (1 <= len(opciones)):
            print("    Entrada no valida.")
            continue
        n = int(r)
        if not (1 <= n <= len(opciones)):
            print("    Entrada no valida.")
            continue
        clave = opciones[n - 1][1]
        if clave == 'texto':
            menu_texto(f)
        elif clave == 'tipo_mtto':
            menu_tipos_mtto(f)
        elif clave == 'categoria_activo':
            menu_categorias_activo(f)
        elif clave == 'fechas':
            menu_fechas(f)
        elif clave == 'estado':
            menu_estado(f)
        elif clave == 'tipo_ot':
            menu_tipo_ot(f)
        elif clave == 'prioridad':
            menu_prioridad(f)
        elif clave == 'limpiar':
            menu_limpiar(f)
        elif clave == 'listar':
            listar_y_abrir(f, base_url, con_navegador)
        elif clave == 'changelist':
            url = f"{base_url.rstrip('/')}{ADMIN_CHANGELIST_URL}"
            print(f"\n  Abriendo lista completa de OTs...")
            abrir(url, con_navegador)
        elif clave == 'salir':
            print("\n  Adios!")
            return


# ---------------------------------------------------------------------------
# Modo directo (argumentos)
# ---------------------------------------------------------------------------
def main_directo(args):
    base_url = args.url or os.environ.get('SITE_URL') or 'http://127.0.0.1:8000'
    con_navegador = not args.no_browser

    if args.listar:
        url = f"{base_url.rstrip('/')}{ADMIN_CHANGELIST_URL}"
        print("Abriendo lista de OTs...")
        abrir(url, con_navegador)
        return

    f = filtros_vacios()
    f['texto'] = args.termino
    f['estado'] = args.estado
    f['tipo_ot'] = args.tipo
    f['prioridad'] = args.prioridad
    if args.desde:
        d = parsear_fecha(args.desde)
        if not d:
            print(f"  Fecha 'desde' no valida: {args.desde} (use YYYY-MM-DD)")
            return
        f['desde'] = d
    if args.hasta:
        d = parsear_fecha(args.hasta)
        if not d:
            print(f"  Fecha 'hasta' no valida: {args.hasta} (use YYYY-MM-DD)")
            return
        f['hasta'] = d

    qs = construir_queryset(f, limite=args.limite)
    total = qs.count()
    print(f"\n  Buscando OT... (filtros: {resumen_filtros(f)})")
    print(f"  {total} resultado(s).")
    if total == 0:
        print("\n  No se encontraron OTs con esos criterios.")
        return

    resultados = list(qs)

    if args.eliminar:
        _borrar_ots(resultados)
        return

    interactuar_resultados(resultados, base_url, con_navegador)


def main():
    parser = argparse.ArgumentParser(description='Buscar y abrir Ordenes de Trabajo (OT).')
    parser.add_argument('termino', nargs='?', help='Codigo de OT, ID o texto a buscar')
    parser.add_argument('--query', dest='termino', help='Alias de "termino"')
    parser.add_argument('--estado', choices=ESTADOS.keys(), help='Filtro por estado')
    parser.add_argument('--tipo', choices=TIPOS.keys(), help='Filtro por tipo de OT')
    parser.add_argument('--prioridad', choices=PRIORIDADES.keys(), help='Filtro por prioridad')
    parser.add_argument('--desde', help='Fecha inicial (YYYY-MM-DD)')
    parser.add_argument('--hasta', help='Fecha final (YYYY-MM-DD)')
    parser.add_argument('--limite', type=int, default=DEFAULT_LIMITE, help='Max. de resultados')
    parser.add_argument('--listar', action='store_true', help='Abrir la lista (changelist) de OTs')
    parser.add_argument('--eliminar', action='store_true', help='Eliminar los resultados encontrados (pide confirmacion)')
    parser.add_argument('--menu', action='store_true', help='Forzar el menu interactivo')
    parser.add_argument('--url', default=None, help='URL base del sistema')
    parser.add_argument('--no-browser', action='store_true', help='No abrir el navegador, solo imprimir URL')
    args = parser.parse_args()

    uso_directo = any([
        args.termino, args.estado, args.tipo, args.prioridad,
        args.desde, args.hasta, args.listar, args.eliminar,
    ])

    if args.menu or not uso_directo:
        menu_principal(args.url or os.environ.get('SITE_URL') or 'http://127.0.0.1:8000', not args.no_browser)
    else:
        main_directo(args)


if __name__ == '__main__':
    main()
