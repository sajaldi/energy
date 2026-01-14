from proyectos.models import Proyecto
from activos.models import Activo, Ubicacion
from documentos.models import Documento
from mantenimiento.models import OrdenTrabajo, Aviso, Rutina
from inventarios.models import Material, StockRecord
from auditorias.models import Auditoria
from comunicaciones.models import Comunicado
from django.db.models import Count, Sum
from django.utils import timezone

def get_projects_summary():
    try:
        projects = Proyecto.objects.all().order_by('-actualizado_en')[:5]
        summary = "PROYECTOS RECIENTES:\n"
        for p in projects:
            summary += f"- {p.codigo}: {p.nombre} (Estado: {p.get_estado_display()}, Avance: {p.porcentaje_avance}%)\n"
        return summary
    except: return "Proyectos: Error al obtener\n"

def get_assets_summary():
    try:
        total_assets = Activo.objects.count()
        assets_by_status = Activo.objects.values('estado').annotate(total=Count('id'))
        summary = f"RESUMEN DE ACTIVOS (Total: {total_assets}):\n"
        for item in assets_by_status:
            summary += f"- {item['estado']}: {item['total']}\n"
        
        recent_assets = Activo.objects.order_by('-creado_en')[:3]
        summary += "Últimos activos:\n"
        for a in recent_assets:
            summary += f"  * {a.codigo_interno or a.id}: {a.nombre} ({a.ubicacion.nombre if a.ubicacion else 'Sin ubicación'})\n"
        return summary
    except: return "Activos: Error al obtener\n"

def get_mantenimiento_summary():
    try:
        total_ots = OrdenTrabajo.objects.count()
        ots_status = OrdenTrabajo.objects.values('estado').annotate(total=Count('id'))
        total_avisos = Aviso.objects.filter(estado='ABIERTO').count()
        
        summary = f"MANTENIMIENTO (OTs: {total_ots}, Avisos Abiertos: {total_avisos}):\n"
        for item in ots_status:
            summary += f"- {item['estado']}: {item['total']}\n"
        
        recent_ots = OrdenTrabajo.objects.order_by('-creado_en')[:3]
        summary += "Últimas OTs:\n"
        for ot in recent_ots:
            summary += f"  * OT-{ot.id}: {ot.rutina.nombre if ot.rutina else 'Correctiva'} ({ot.get_estado_display()})\n"
        return summary
    except: return "Mantenimiento: Error al obtener\n"

def get_inventarios_summary():
    try:
        total_materials = Material.objects.count()
        summary = f"INVENTARIOS (Items: {total_materials}):\n"
        # Simplificamos consulta de stock bajo para evitar lentitud
        low = Material.objects.filter(sku__isnull=False)[:5] 
        summary += "- Repuestos principales en sistema.\n"
        return summary
    except: return "Inventarios: Error al obtener\n"

def get_documents_summary():
    try:
        total_docs = Documento.objects.count()
        summary = f"DOCUMENTOS (Total: {total_docs})\n"
        return summary
    except: return "Documentos: Error al obtener\n"

def get_comunicaciones_summary():
    try:
        total_com = Comunicado.objects.count()
        summary = f"COMUNICACIONES (Totales: {total_com})\n"
        return summary
    except: return "Comunicaciones: Error al obtener\n"

def get_dynamic_context():
    try:
        context = "ESTADO ACTUAL DEL SISTEMA (DATO EN VIVO DE LA BD):\n\n"
        context += get_projects_summary() + "\n"
        context += get_assets_summary() + "\n"
        context += get_mantenimiento_summary() + "\n"
        context += get_inventarios_summary() + "\n"
        context += get_documents_summary() + "\n"
        context += get_comunicaciones_summary() + "\n"
        return context
    except Exception as e:
        return f"Error general de contexto: {str(e)}"
