import time
import os
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.files.storage import default_storage
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from celery.result import AsyncResult
from .tasks import import_requisiciones_task
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.urls import reverse

@staff_member_required
def import_requisiciones_background(request):
    """Renders the upload form for background import."""
    from django.contrib import admin
    context = {
        **admin.site.each_context(request),
        'title': 'Importación masiva de Requisiciones (Background)',
    }
    return render(request, 'admin/presupuestos/requisicion/import_background.html', context)

@staff_member_required
@csrf_exempt
def import_requisiciones_process(request):
    """Triggers the Celery task for importing requisitions."""
    import sys
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    is_confirm = request.POST.get('confirm', '').lower() in ['true', 'on', '1']
    existing_path = request.POST.get('file_path')
    import_file = request.FILES.get('import_file')

    # Si NO es confirmación, necesitamos un archivo nuevo obligatoriamente
    if not is_confirm:
        if not import_file:
            return JsonResponse({'error': 'No se subió ningún archivo'}, status=400)
            
        file_ext = import_file.name.split('.')[-1].lower()
        temp_name = f'tmp/import_requisiciones_{request.user.id}_{int(time.time())}.{file_ext}'
        
        try:
            path = default_storage.save(temp_name, import_file)
        except Exception as e:
            return JsonResponse({'error': f'Error al guardar archivo: {str(e)}'}, status=500)
    else:
        # ES UNA CONFIRMACIÓN: Usar el archivo que ya está en el servidor
        if not existing_path:
            return JsonResponse({'error': 'Falta la ruta del archivo para confirmar'}, status=400)
        path = existing_path
        file_ext = path.split('.')[-1].lower()
    
    # Limpiar cache de progreso anterior
    cache_key = f"import_requisiciones_progress_{request.user.id}"
    cache.delete(cache_key)
    
    # Trigger Celery task
    v_val = request.POST.get('verification_mode', '').lower()
    verification_mode = v_val in ['true', 'on', '1']
    
    # Lógica de Dry Run: SOLO si no es verificación y no es confirmación final
    dry_run = (not verification_mode) and (not is_confirm)
    
    task = import_requisiciones_task.delay(
        path, 
        file_ext, 
        user_id=request.user.id,
        verification_mode=verification_mode,
        dry_run=dry_run
    )
    
    return JsonResponse({
        'status': 'started', 
        'task_id': task.id,
        'dry_run': dry_run,
        'verification_mode': verification_mode
    })

@staff_member_required
def import_requisiciones_progress(request):
    """API to poll progress for requisition import."""
    task_id = request.GET.get('task_id')
    if not task_id:
        return JsonResponse({'error': 'Falta task_id'}, status=400)
        
    cache_key = f"import_requisiciones_progress_{request.user.id}"
    progress = cache.get(cache_key, {'status': 'pending', 'percent': 0})
    
    res = AsyncResult(task_id)
    if res.state == 'SUCCESS':
        if isinstance(res.result, dict):
            progress.update(res.result)
        progress['state'] = 'COMPLETED'
        progress['percent'] = 100
    elif res.state == 'FAILURE':
        progress['error'] = str(res.result)
        progress['state'] = 'FAILURE'
    elif res.state == 'PROGRESS':
        if isinstance(res.info, dict):
            progress.update(res.info)
        progress['state'] = 'PROGRESS'
    else:
        progress['state'] = res.state if res else 'PENDING'
        
    return JsonResponse(progress)

@staff_member_required
@login_required
def requisicion_unlock_edit(request, pk):
    """
    Desbloquea una requisición para edición.
    Cambia el estado de PENDIENTE/RECHAZADO a BORRADOR.
    Solo funciona si la requisición está en esos estados.
    """
    from .models import Requisicion
    from django.urls import reverse
    
    requisicion = get_object_or_404(Requisicion, pk=pk)
    
    # Validar que puede desbloquearse
    if requisicion.estado_requisicion not in ['PENDIENTE', 'RECHAZADO']:
        messages.error(request, f"No se puede desbloquear. Estado actual: {requisicion.get_estado_requisicion_display()}")
        return redirect('presupuestos:requisicion_editar', pk=pk)
    
    # Cambiar a BORRADOR para permitir edición
    estado_anterior = requisicion.get_estado_requisicion_display()
    requisicion.estado_requisicion = 'BORRADOR'
    requisicion.save()
    
    messages.success(
        request, 
        f"Requisición desbloqueada. Estado cambiado de {estado_anterior} a Borrador. "
        f"Deberá solicitar nuevamente la autorización después de editar."
    )
    
    # Redirigir a la vista de edición
    return redirect('presupuestos:requisicion_editar', pk=pk)

@staff_member_required
@login_required
def requisicion_upsert(request, pk=None):
    """Vista para crear o editar requisiciones usando un Wizard"""
    from .models import Requisicion
    from .forms import RequisicionForm, ArticuloFormSet, DocumentoFormSet
    from django.urls import reverse

    instance = get_object_or_404(Requisicion, pk=pk) if pk else None

    # Si es nueva, la creamos y redirigimos a la vista de edición para evitar duplicados en POST y conflictos de unicidad
    if not instance:
        instance = Requisicion(usuario_solicitante=request.user)
        instance.save()  # Guardar para obtener PK
        return redirect(reverse('presupuestos:requisicion_editar', kwargs={'pk': instance.pk}))
    
    # Si no tiene solicitante, asignar el usuario actual
    if not instance.usuario_solicitante:
        instance.usuario_solicitante = request.user
        instance.save(update_fields=['usuario_solicitante'])

    # Determinamos el paso actual
    # Prioridad: Parámetro GET > wizard_step guardado > Default 1
    current_step = int(request.GET.get('step', instance.wizard_step if instance else 1))

    # Bloquear edición si ya está enviada a aprobar o en estado final
    is_readonly = False
    can_unlock = False
    
    if instance and instance.pk:
        # Estados que bloquean la edición
        locked_states = ['PENDIENTE', 'AUTORIZADO', 'RECHAZADO']
        
        if instance.estado_requisicion in locked_states:
            is_readonly = True
            
            # Solo puede desbloquear si está PENDIENTE (enviada a aprobar pero no decidida)
            if instance.estado_requisicion == 'PENDIENTE':
                can_unlock = True
                messages.info(request, "Esta requisición fue enviada a aprobación y está bloqueada para edición.")
            elif instance.estado_requisicion == 'AUTORIZADO':
                messages.warning(request, "Esta requisición ya fue AUTORIZADA y no puede modificarse.")
            elif instance.estado_requisicion == 'RECHAZADO':
                can_unlock = True
                messages.warning(request, "Esta requisición fue RECHAZADA. Puede desbloquearla para editarla.")

    if request.method == 'POST':
        if is_readonly:
             messages.error(request, "No se pueden guardar cambios: La requisición está bloqueada para edición.")
             return redirect('presupuestos:requisicion_dashboard')

        form = RequisicionForm(request.POST, instance=instance)
        articulo_formset = ArticuloFormSet(request.POST, instance=instance, prefix='articulos')
        documento_formset = DocumentoFormSet(request.POST, request.FILES, instance=instance, prefix='documentos')
        
        target_step = int(request.POST.get('target_step', current_step))
        is_final_save = request.POST.get('final_save') == 'true'

        # Lógica de validación y guardado por paso
        success = False
        
        if current_step == 1:
            if form.is_valid():
                instance = form.save()
                success = True
            else:
                pass
        elif current_step == 2:
            if articulo_formset.is_valid():
                articulo_formset.save()
                success = True
            else:
                pass
        elif current_step == 3:
            # Validar que haya al menos un documento cargado (ya sea nuevo o existente)
            documento_formset_is_valid = documento_formset.is_valid()

            has_files = False
            if documento_formset_is_valid:
                # Formset válido - verificar si hay documentos
                for form in documento_formset:
                    archivo = form.cleaned_data.get('archivo')
                    es_eliminado = form.cleaned_data.get('DELETE', False)
                    tiene_pk = form.instance.pk

                    # Contar si: tiene archivo nuevo O tiene documento existente (pk) Y no está marcado para eliminar
                    if (archivo) or (tiene_pk and not es_eliminado):
                        has_files = True
                        break

            if not has_files:
                messages.error(request, "Debe cargar al menos un documento para continuar.")
                success = False
            else:
                # Tiene documentos - guardar y continuar
                if documento_formset_is_valid:
                    documento_formset.save()
                success = True
        elif current_step == 4:
            success = True

        if success:
            if is_final_save:
                messages.success(request, f"Requisición {instance.cr8ca_requisicion} finalizada correctamente.")
                return redirect('presupuestos:requisicion_dashboard')
            
            # Actualizar el wizard_step si avanzamos más allá de lo guardado
            if instance and target_step > instance.wizard_step:
                instance.wizard_step = target_step
                instance.save()
                
            # Redirigir al siguiente paso
            url = reverse('presupuestos:requisicion_editar', kwargs={'pk': instance.pk})
            return redirect(f"{url}?step={target_step}")
        else:
            # Mostrar errores específicos
            error_messages = []
            if current_step == 1 and not form.is_valid():
                for field, errors in form.errors.items():
                    field_label = form.fields[field].label if field in form.fields else field
                    error_messages.append(f"{field_label}: {', '.join(errors)}")
            elif current_step == 2 and not articulo_formset.is_valid():
                for i, form_errors in enumerate(articulo_formset.errors):
                    if form_errors:
                        error_messages.append(f"Artículo {i+1}: {', '.join([f'{k}: {v[0]}' for k, v in form_errors.items()])}")
                if articulo_formset.non_form_errors():
                    error_messages.extend(articulo_formset.non_form_errors())
            elif current_step == 3 and not documento_formset.is_valid():
                for i, form_errors in enumerate(documento_formset.errors):
                    if form_errors:
                        error_messages.append(f"Documento {i+1}: {', '.join([f'{k}: {v[0]}' for k, v in form_errors.items()])}")
                if documento_formset.non_form_errors():
                    error_messages.extend(documento_formset.non_form_errors())
            
            if error_messages:
                for error_msg in error_messages:
                    messages.error(request, error_msg)
            else:
                messages.error(request, "Por favor corrige los errores para continuar.")

    else:
        form = RequisicionForm(instance=instance)
        articulo_formset = ArticuloFormSet(instance=instance, prefix='articulos')
        documento_formset = DocumentoFormSet(instance=instance, prefix='documentos')

    context = {
        'form': form,
        'articulo_formset': articulo_formset,
        'documento_formset': documento_formset,
        'instance': instance,
        'title': f"Editar Requisición {instance.cr8ca_requisicion}" if instance else "Nueva Requisición",
        'current_step': current_step,
        'is_readonly': is_readonly,
        'can_unlock': can_unlock,
    }
    return render(request, 'admin/presupuestos/requisicion/requisicion_form.html', context)

@login_required
def requisicion_qr(request, pk):
    """Genera un código QR para la requisición"""
    import qrcode
    import io
    import base64
    from django.http import HttpResponse
    from .models import Requisicion

    requisicion = get_object_or_404(Requisicion, pk=pk)

    # URL que will contain the QR code
    relative_url = reverse('presupuestos:requisicion_editar', kwargs={'pk': requisicion.cr8ca_requisicionid})
    qr_data = request.build_absolute_uri(relative_url)

    # Generate QR code
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(qr_data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    # Convert to binary to display in img src
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    return HttpResponse(buffer.getvalue(), content_type="image/png")

@login_required
def requisicion_pdf(request, pk):
    """Genera un PDF de la requisición"""
    from django.template.loader import get_template
    from xhtml2pdf import pisa
    from .models import Requisicion, ArticuloRequisicion, DocumentoRequisicion
    import io
    import qrcode
    import base64
    from django.http import HttpResponse

    requisicion = get_object_or_404(Requisicion, pk=pk)

    # Generar QR code
    relative_url = reverse('presupuestos:requisicion_editar', kwargs={'pk': requisicion.cr8ca_requisicionid})
    qr_data = request.build_absolute_uri(relative_url)
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(qr_data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    qr_base64 = base64.b64encode(buffer.getvalue()).decode()

    # Obtener artículos y documentos
    articulos = requisicion.articulos.all()
    documentos = requisicion.documentos.all()

    context = {
        'requisicion': requisicion,
        'articulos': articulos,
        'documentos': documentos,
        'qr_code': qr_base64,
    }

    template = get_template('admin/presupuestos/requisicion/requisicion_pdf.html')
    html = template.render(context)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Requisicion_{requisicion.cr8ca_requisicion}.pdf"'

    pisa_status = pisa.CreatePDF(html, dest=response)

    if pisa_status.err:
        return HttpResponse('Error creating PDF', status=500)

    return response


@staff_member_required
@login_required
def requisicion_dashboard(request):
    """Vista de dashboard  para Requisiciones"""
    from .models import Requisicion
    from django.db.models import Sum, Count, Q
    from django.utils import timezone
    from datetime import timedelta

    # Obtener parámetro de búsqueda
    search_query = request.GET.get('q', '').strip()

    # Métricas básicas
    total_reqs = Requisicion.objects.count()
    total_monto = Requisicion.objects.aggregate(total=Sum('cr8ca_totalenarticulos'))['total'] or 0
    
    # Requisiciones recientes (últimos 30 días)
    hace_30_dias = timezone.now().date() - timedelta(days=30)
    reqs_recientes = Requisicion.objects.filter(Q(fecha__gte=hace_30_dias) | Q(createdon__gte=hace_30_dias)).count()
    
    # Desglose por prioridad
    prioridad_data = Requisicion.objects.values('cr8ca_prioridad').annotate(count=Count('cr8ca_prioridad')).order_by('cr8ca_prioridad')
    
    # Últimas requisiciones con búsqueda y ordenamiento por fecha (más nuevas primero)
    requisiciones_query = Requisicion.objects.all()
    
    # Aplicar búsqueda si existe
    if search_query:
        requisiciones_query = requisiciones_query.filter(
            Q(cr8ca_requisicion__icontains=search_query) |
            Q(cr8ca_asunto__icontains=search_query) |
            Q(cr8ca_motivo__icontains=search_query)
        )
    
    # Ordenar por fecha de solicitud (más nuevas primero)
    # Usar fecha si existe, sino createdon
    ultimas_requisiciones = requisiciones_query.order_by('-fecha', '-createdon')[:20]

    context = {
        'total_reqs': total_reqs,
        'total_monto': total_monto,
        'reqs_recientes': reqs_recientes,
        'prioridad_data': prioridad_data,
        'ultimas_requisiciones': ultimas_requisiciones,
        'search_query': search_query,
        'title': 'Dashboard de Requisiciones'
    }
    return render(request, 'admin/presupuestos/requisicion/dashboard.html', context)

def download_template(request):
    """Generates an Excel file with headers and a sample row for Requisitions."""
    from .resources import RequisicionResource
    from django.http import HttpResponse
    from .models import Requisicion
    import tablib
    
    resource = RequisicionResource()
    # Obtenemos las cabeceras del recurso
    headers = resource.get_export_headers()
    dataset = tablib.Dataset(headers=headers)
    
    # Creamos una fila de ejemplo
    # Nota: Los nombres de las columnas deben coincidir con los definidos en RequisicionResource.fields
    sample_row = {
        'cr8ca_requisicion': 'REQ-00001-2026',
        'fecha': '2026-02-05',
        'cr8ca_asunto': 'Compra de Material Eléctrico',
        'cr8ca_motivo': 'Reparación de subestación',
        'cr8ca_comentarios': 'Urgente para mantenimiento preventivo',
        'cr8ca_totalenarticulos': '57168.80',
        'costo': '57168.80',
        'cr8ca_prioridad': '2',
        'cr8ca_id_oc': 'OC-99999',
    }
    
    # Rellenar el resto de campos con vacío para evitar errores de desajuste
    row_data = []
    for h in headers:
        row_data.append(sample_row.get(h, ''))
    
    dataset.append(row_data)
    
    response = HttpResponse(dataset.xlsx, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="formato_importacion_requisiciones.xlsx"'
    return response
