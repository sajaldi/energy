# Seed de la página de inicio: descripciones y módulos faltantes.
# Los módulos ya existentes (0027_seed_admin_nav) se actualizan con descripción,
# y se crean las tarjetas de Proyectos, Documentos, Activos, Auditorías,
# Comunicaciones, Seguridad y App Móvil.

from django.db import migrations


DESCRIPCIONES = {
    "Mantenimiento": "Órdenes de trabajo, rutinas preventivas y gestión de avisos técnicos (GMAO).",
    "Costos y Presupuestos": "Requisiciones, ejecución financiera y control presupuestario por departamento.",
    "Inventarios": "Control de existencias, movimientos y solicitudes de material.",
    "Ajustes": "Configuración, importaciones y herramientas de soporte.",
}

NUEVOS_MODULOS = [
    {
        "name": "Gestión de Activos",
        "icon": "fas fa-desktop",
        "color": "#0ea5e9",
        "order": 5,
        "descripcion": "Inventario técnico de la infraestructura, planos interactivos y códigos QR.",
        "columns": [
            {
                "heading": "Catálogo",
                "items": [
                    {"name": "Listado de Activos", "url": "/admin/activos/activo/", "permission": "activos.view_activo", "icon": "fas fa-list"},
                    {"name": "Ubicaciones", "url": "/admin/activos/ubicacion/", "permission": "activos.view_ubicacion", "icon": "fas fa-map-marker-alt"},
                ],
            },
        ],
    },
    {
        "name": "Proyectos",
        "icon": "fas fa-project-diagram",
        "color": "#8b5cf6",
        "order": 6,
        "descripcion": "Control de hitos, cronogramas y documentación técnica vinculada a la ejecución.",
        "columns": [
            {
                "heading": "Gestión",
                "items": [
                    {"name": "Listado de Proyectos", "url": "/admin/proyectos/proyecto/", "permission": "proyectos.view_proyecto", "icon": "fas fa-list"},
                    {"name": "Actividades", "url": "/admin/proyectos/actividad/", "permission": "proyectos.view_actividad", "icon": "fas fa-tasks"},
                ],
            },
        ],
    },
    {
        "name": "Documentos",
        "icon": "fas fa-file-alt",
        "color": "#ef4444",
        "order": 7,
        "descripcion": "Biblioteca global de archivos, gestión de versiones y firmas electrónicas.",
        "columns": [
            {
                "heading": "Documental",
                "items": [
                    {"name": "Listado de Documentos", "url": "/admin/documentos/documento/", "permission": "documentos.view_documento", "icon": "fas fa-list"},
                    {"name": "Biblioteca", "url": "/admin/documentos/biblioteca/", "permission": "documentos.view_biblioteca", "icon": "fas fa-book"},
                ],
            },
        ],
    },
    {
        "name": "Auditorías e Inspección",
        "icon": "fas fa-clipboard-check",
        "color": "#14b8a6",
        "order": 8,
        "descripcion": "Listas de verificación dinámica y reportes de calidad fotográfica.",
        "columns": [
            {
                "heading": "Verificación",
                "items": [
                    {"name": "Listado de Auditorías", "url": "/admin/auditorias/auditoria/", "permission": "auditorias.view_auditoria", "icon": "fas fa-clipboard-list"},
                    {"name": "Inspecciones", "url": "/admin/auditorias/inspeccion/", "permission": "auditorias.view_inspeccion", "icon": "fas fa-search"},
                ],
            },
        ],
    },
    {
        "name": "Comunicaciones",
        "icon": "fas fa-envelope-open-text",
        "color": "#06b6d4",
        "order": 9,
        "descripcion": "Gestión oficial de correspondencia y transmittals de ingeniería.",
        "columns": [
            {
                "heading": "Correspondencia",
                "items": [
                    {"name": "Listado de Comunicados", "url": "/admin/comunicaciones/comunicado/", "permission": "comunicaciones.view_comunicado", "icon": "fas fa-mail-bulk"},
                ],
            },
        ],
    },
    {
        "name": "Seguridad y Riesgos",
        "icon": "fas fa-hard-hat",
        "color": "#f43f5e",
        "order": 10,
        "descripcion": "Reporte de incidentes, actos inseguros y permisos de trabajo.",
        "columns": [
            {
                "heading": "SST",
                "items": [
                    {"name": "Incidentes", "url": "/admin/seguridad/incidente/", "permission": "seguridad.view_incidente", "icon": "fas fa-exclamation-triangle"},
                    {"name": "Inspecciones", "url": "/admin/seguridad/inspeccion/", "permission": "seguridad.view_inspeccion", "icon": "fas fa-clipboard-check"},
                    {"name": "Permisos de Trabajo", "url": "/admin/seguridad/permisotrabajo/", "permission": "seguridad.view_permisotrabajo", "icon": "fas fa-id-card"},
                ],
            },
        ],
    },
    {
        "name": "App Móvil",
        "icon": "fas fa-mobile-alt",
        "color": "#ec4899",
        "order": 11,
        "url": "/app/",
        "descripcion": "Accesos móviles tipo PWA para técnicos en campo: tareas, escáner QR y más.",
        "columns": [
            {
                "heading": "Accesos móviles",
                "items": [
                    {"name": "Dashboard Móvil", "url": "/app/", "permission": "", "icon": "fas fa-mobile-alt"},
                    {"name": "Escáner QR", "url": "/app/scanner/", "permission": "", "icon": "fas fa-qrcode"},
                    {"name": "Portal del Sistema", "url": "/portal/", "permission": "", "icon": "fas fa-th-large"},
                ],
            },
        ],
    },
]


def seed_home_modulos(apps, schema_editor):
    AdminNavMenu = apps.get_model("core", "AdminNavMenu")
    AdminNavColumn = apps.get_model("core", "AdminNavColumn")
    AdminNavItem = apps.get_model("core", "AdminNavItem")

    for name, desc in DESCRIPCIONES.items():
        m = AdminNavMenu.objects.filter(name=name).first()
        if m:
            m.descripcion = desc
            m.save(update_fields=["descripcion"])

    for modulo in NUEVOS_MODULOS:
        m = AdminNavMenu.objects.filter(name=modulo["name"]).first()
        if m:
            continue
        m = AdminNavMenu.objects.create(
            name=modulo["name"],
            icon=modulo["icon"],
            color=modulo["color"],
            descripcion=modulo.get("descripcion", ""),
            url=modulo.get("url", ""),
            order=modulo["order"],
        )
        for col_idx, col in enumerate(modulo.get("columns", []), start=1):
            column = AdminNavColumn.objects.create(
                menu=m, heading=col["heading"], order=col_idx
            )
            for item_idx, item in enumerate(col.get("items", []), start=1):
                AdminNavItem.objects.create(
                    column=column,
                    name=item["name"],
                    url=item["url"],
                    icon=item.get("icon", "fas fa-angle-right"),
                    permission=item.get("permission", ""),
                    order=item_idx,
                )


def unseed_home_modulos(apps, schema_editor):
    AdminNavMenu = apps.get_model("core", "AdminNavMenu")
    AdminNavMenu.objects.filter(name__in=[m["name"] for m in NUEVOS_MODULOS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0031_adminnavmenu_grupos_descripcion_url_adminnavitem_icon"),
    ]

    operations = [
        migrations.RunPython(seed_home_modulos, unseed_home_modulos),
    ]
