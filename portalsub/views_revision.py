"""
Plataforma de Revisión de Expedientes Mensuales.
Accesible para usuarios staff que revisan los expedientes enviados por subcontratistas.
"""
import calendar
from datetime import date
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from mantenimiento.models import Empresa
from .models import ExpedienteMensual, EntregableContratista, DocumentoEntregable, PerfilContratista


@staff_member_required
def revision_dashboard(request):
    """Dashboard de revisión: muestra empresas con expedientes pendientes de revisión."""
    today = date.today()
    mes_raw = request.GET.get('mes', '').replace(',', '').strip()
    anio_raw = request.GET.get('anio', '').replace(',', '').strip()
    mes = int(mes_raw) if mes_raw else today.month
    anio = int(anio_raw) if anio_raw else today.year

    # Todas las empresas que tienen perfil de contratista activo
    empresas_ids = PerfilContratista.objects.filter(activo=True).values_list('empresa_id', flat=True).distinct()
    empresas = Empresa.objects.filter(id__in=empresas_ids, activo=True).order_by('nombre')

    # Obtener expedientes del mes/año para cada empresa
    expedientes_map = {}
    for exp in ExpedienteMensual.objects.filter(mes=mes, anio=anio, empresa__in=empresas):
        expedientes_map[exp.empresa_id] = exp

    items = []
    for emp in empresas:
        exp = expedientes_map.get(emp.id)
        items.append({
            'empresa': emp,
            'expediente': exp,
            'estado': exp.get_estado_display() if exp else 'Sin expediente',
            'estado_raw': exp.estado if exp else None,
            'fecha_envio': exp.fecha_envio if exp else None,
        })

    # Estadísticas
    total = len(items)
    enviados = sum(1 for i in items if i['estado_raw'] == 'ENVIADO')
    aprobados = sum(1 for i in items if i['estado_raw'] == 'APROBADO')
    rechazados = sum(1 for i in items if i['estado_raw'] == 'RECHAZADO')

    meses_opciones = [(i, calendar.month_name[i].capitalize()) for i in range(1, 13)]

    context = {
        'items': items,
        'mes': mes,
        'anio': anio,
        'mes_nombre': calendar.month_name[mes].capitalize(),
        'meses_opciones': meses_opciones,
        'total': total,
        'enviados': enviados,
        'aprobados': aprobados,
        'rechazados': rechazados,
    }
    return render(request, 'portalsub/revision_dashboard.html', context)


@staff_member_required
def revision_expediente(request, empresa_id, mes, anio):
    """Detalle de un expediente para revisión."""
    empresa = get_object_or_404(Empresa, pk=empresa_id)
    expediente_obj = get_object_or_404(ExpedienteMensual, empresa=empresa, mes=mes, anio=anio)

    configs = EntregableContratista.objects.filter(
        empresa=empresa, activo=True, tipo_entregable__activo=True,
    ).select_related('tipo_entregable').order_by('tipo_entregable__nombre')

    items = []
    for c in configs:
        if mes not in c.get_meses():
            continue
        doc = DocumentoEntregable.objects.filter(
            empresa=empresa, tipo_entregable=c.tipo_entregable, mes=mes, anio=anio
        ).first()
        items.append({
            'config': c,
            'documento': doc,
            'completo': doc is not None and (doc.es_valido or doc.no_aplica),
            'no_aplica': doc.no_aplica if doc else False,
        })

    context = {
        'empresa': empresa,
        'expediente': expediente_obj,
        'items': items,
        'mes': mes,
        'anio': anio,
        'mes_nombre': calendar.month_name[mes].capitalize(),
    }
    return render(request, 'portalsub/revision_expediente.html', context)


@staff_member_required
@require_POST
def revision_aprobar_rechazar(request, empresa_id, mes, anio):
    """Aprobar o rechazar un expediente."""
    import json
    empresa = get_object_or_404(Empresa, pk=empresa_id)
    expediente_obj = get_object_or_404(ExpedienteMensual, empresa=empresa, mes=mes, anio=anio)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        data = request.POST

    accion = data.get('accion')  # 'aprobar' o 'rechazar'
    observaciones = data.get('observaciones', '')

    if accion == 'aprobar':
        expediente_obj.estado = 'APROBADO'
        expediente_obj.fecha_revision = timezone.now()
        expediente_obj.revisado_por = request.user
        expediente_obj.observaciones = observaciones
        expediente_obj.save()
        from .models import HistorialExpediente
        HistorialExpediente.objects.create(
            expediente=expediente_obj, evento='APROBADO', usuario=request.user,
            observaciones=observaciones or 'Expediente aprobado.'
        )
        return JsonResponse({'status': 'success', 'message': f'Expediente de {empresa.nombre} aprobado.'})
    elif accion == 'rechazar':
        expediente_obj.estado = 'RECHAZADO'
        expediente_obj.fecha_revision = timezone.now()
        expediente_obj.revisado_por = request.user
        expediente_obj.observaciones = observaciones
        expediente_obj.save()
        from .models import HistorialExpediente
        HistorialExpediente.objects.create(
            expediente=expediente_obj, evento='RECHAZADO', usuario=request.user,
            observaciones=observaciones
        )
        return JsonResponse({'status': 'success', 'message': f'Expediente de {empresa.nombre} rechazado.'})

    return JsonResponse({'status': 'error', 'message': 'Acción no válida'}, status=400)
