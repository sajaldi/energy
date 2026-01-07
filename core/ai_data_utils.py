from proyectos.models import Proyecto
from activos.models import Activo, Ubicacion
from documentos.models import Documento
from django.db.models import Count

def get_projects_summary():
    projects = Proyecto.objects.all()[:10] # Limit to most recent 10 for context window
    summary = "PROYECTOS RECIENTES:\n"
    for p in projects:
        summary += f"- {p.codigo}: {p.nombre} (Estado: {p.get_estado_display()}, Avance: {p.porcentaje_avance}%)\n"
    return summary

def get_assets_summary():
    total_assets = Activo.objects.count()
    assets_by_status = Activo.objects.values('estado').annotate(total=Count('id'))
    
    summary = f"RESUMEN DE ACTIVOS (Total: {total_assets}):\n"
    for item in assets_by_status:
        summary += f"- {item['estado']}: {item['total']}\n"
    
    # List a few recently created assets
    recent_assets = Activo.objects.order_by('-creado_en')[:5]
    summary += "Últimos activos registrados:\n"
    for a in recent_assets:
        summary += f"  * {a.codigo_interno or a.id}: {a.modelo.nombre if a.modelo else 'Sin modelo'} ({a.ubicacion.nombre if a.ubicacion else 'Sin ubicación'})\n"
    
    return summary

def get_documents_summary():
    total_docs = Documento.objects.count()
    docs_by_status = Documento.objects.values('estado_actual').annotate(total=Count('id'))
    
    summary = f"RESUMEN DE DOCUMENTOS (Total: {total_docs}):\n"
    for item in docs_by_status:
        summary += f"- {item['estado_actual']}: {item['total']}\n"
    
    recent_docs = Documento.objects.order_by('-creado_en')[:5]
    summary += "Documentos recientes:\n"
    for d in recent_docs:
        summary += f"  * {d.codigo}: {d.titulo} (Estado: {d.get_estado_actual_display()})\n"
    
    return summary

def get_dynamic_context():
    try:
        context = "DATOS ACTUALES DEL SISTEMA (BASE DE DATOS):\n\n"
        context += get_projects_summary() + "\n"
        context += get_assets_summary() + "\n"
        context += get_documents_summary() + "\n"
        return context
    except Exception as e:
        return f"Error al extraer datos de la BD: {str(e)}"
