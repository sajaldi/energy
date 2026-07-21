import time
import os
from django.contrib.admin.views.decorators import staff_member_required
from core.decorators import mobile_permission_required
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.files.storage import default_storage
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from celery.result import AsyncResult
from .tasks import import_requisiciones_task
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.urls import reverse


def _registrar_historial(requisicion, estado_nuevo, usuario=None, descripcion=''):
    from .models import RequisicionHistorial
    estado_anterior = requisicion.estado_requisicion
    if estado_anterior == estado_nuevo:
        return
    RequisicionHistorial.objects.create(
        requisicion=requisicion,
        estado_anterior=estado_anterior,
        estado_nuevo=estado_nuevo,
        usuario=usuario,
        descripcion=descripcion,
    )


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
    estado_anterior_display = requisicion.get_estado_requisicion_display()
    _registrar_historial(requisicion, 'BORRADOR', usuario=request.user)
    requisicion.estado_requisicion = 'BORRADOR'
    requisicion.save()
    
    messages.success(
        request, 
        f"Requisición desbloqueada. Estado cambiado de {estado_anterior_display} a Borrador. "
        f"Deberá solicitar nuevamente la autorización después de editar."
    )
    
    # Redirigir a la vista de edición
    return redirect('presupuestos:requisicion_editar', pk=pk)

@staff_member_required
@login_required
def requisicion_upsert(request, pk=None):
    """Vista para crear o editar requisiciones usando un Wizard"""
    from decimal import Decimal
    from .models import Requisicion
    from .forms import RequisicionForm, ArticuloFormSet, DocumentoFormSet
    from .webhooks import notify_requisicion_finalizada
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
        locked_states = ['PENDIENTE', 'AUTORIZADO', 'VISTO_PROCURA', 'PROCURA_PROCESANDO', 'EN_ORDEN_COMPRA', 'RECHAZADO']
        
        if instance.estado_requisicion in locked_states:
            is_readonly = True
            
            # Solo puede desbloquear si está PENDIENTE (enviada a aprobar pero no decidida)
            if instance.estado_requisicion == 'PENDIENTE':
                can_unlock = True
                messages.info(request, "Esta requisición fue enviada a aprobación y está bloqueada para edición.")
            elif instance.estado_requisicion == 'AUTORIZADO':
                # Auto-marcar como Visto por Procura si el usuario pertenece al grupo PROCURA
                if request.user.groups.filter(name__in=['Procura', 'PROCURA']).exists():
                    _registrar_historial(instance, 'VISTO_PROCURA', usuario=request.user)
                    instance.estado_requisicion = 'VISTO_PROCURA'
                    instance.save(update_fields=['estado_requisicion'])
                    messages.info(request, "Requisición marcada como Visto por Procura.")
                else:
                    messages.warning(request, "Esta requisición ya fue AUTORIZADA y no puede modificarse.")
            elif instance.estado_requisicion == 'VISTO_PROCURA':
                messages.info(request, "Requisición revisada por Procura, pendiente de procesar a Orden de Compra.")
            elif instance.estado_requisicion == 'PROCURA_PROCESANDO':
                messages.info(request, "Requisición está siendo procesada por Procura.")
            elif instance.estado_requisicion == 'EN_ORDEN_COMPRA':
                messages.info(request, "Esta requisición ya fue procesada a Orden de Compra.")
            elif instance.estado_requisicion == 'RECHAZADO':
                can_unlock = True
                messages.warning(request, "Esta requisición fue RECHAZADA. Puede desbloquearla para editarla.")

    if request.method == 'POST':
        if is_readonly:
             messages.error(request, "No se pueden guardar cambios: La requisición está bloqueada para edición.")
             return redirect('presupuestos:requisicion_dashboard')

        # Guardar fecha_probable_entrega manualmente (campo no incluido en el form)
        fpe = request.POST.get('fecha_probable_entrega', '').strip()
        if fpe:
            try:
                from datetime import datetime as dt
                instance.fecha_probable_entrega = dt.strptime(fpe, '%Y-%m-%d').date()
                instance.recepcion_notificada = True
                instance.save(update_fields=['fecha_probable_entrega', 'recepcion_notificada'])
            except ValueError:
                pass

        form = RequisicionForm(request.POST, instance=instance, user=request.user)
        articulo_formset = ArticuloFormSet(request.POST, instance=instance, prefix='articulos')
        documento_formset = DocumentoFormSet(request.POST, request.FILES, instance=instance, prefix='documentos')
        
        target_step = int(request.POST.get('target_step', current_step))
        is_final_save = request.POST.get('final_save') == 'true'

        # Si va hacia atrás, guarda lo que se pueda sin validar y redirige
        going_back = target_step < current_step

        # Lógica de validación y guardado por paso
        success = False
        
        if current_step == 1:
            if (form.is_valid() or going_back):
                instance = form.save()
                success = True
            else:
                pass
        elif current_step == 2:
            if (articulo_formset.is_valid() or going_back):
                articulo_formset.save()
                # Save ISV directly from POST to avoid full form validation
                isv_value = request.POST.get('isv')
                if isv_value is not None:
                    try:
                        instance.isv = Decimal(isv_value.replace(',', ''))
                        instance.save(update_fields=['isv'])
                    except (ValueError, TypeError):
                        pass
                success = True
            else:
                pass
        elif current_step == 3:
            is_valid_and_continue = going_back

            if not going_back:
                documento_formset_is_valid = documento_formset.is_valid()
                has_files = False
                if documento_formset_is_valid:
                    for form in documento_formset:
                        archivo = form.cleaned_data.get('archivo')
                        es_eliminado = form.cleaned_data.get('DELETE', False)
                        tiene_pk = form.instance.pk
                        if (archivo) or (tiene_pk and not es_eliminado):
                            has_files = True
                            break

                if has_files:
                    if documento_formset_is_valid:
                        documento_formset.save()
                    is_valid_and_continue = True
                else:
                    messages.error(request, "Debe cargar al menos un documento para continuar.")

            if is_valid_and_continue:
                success = True

        elif current_step == 4:
            success = True

        if success or going_back:
            if is_final_save and success:
                # Cambiar a estado PENDIENTE si estaba en BORRADOR (lógica de flujo)
                if instance.estado_requisicion == 'BORRADOR':
                    _registrar_historial(instance, 'PENDIENTE', usuario=request.user)
                    instance.estado_requisicion = 'PENDIENTE'
                    instance.save()
                
                # Disparar Webhook
                notify_requisicion_finalizada(instance)
                
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
        form = RequisicionForm(instance=instance, user=request.user)
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
        'historial': instance.historial.all() if instance else [],
        'notas': instance.notas.all()[:10] if instance else [],
    }
    return render(request, 'admin/presupuestos/requisicion/requisicion_form.html', context)

@login_required
def requisicion_qr(request, pk):
    """Genera un código QR para la requisición"""
    import qrcode
    import io
    import base64
    from django.http import HttpResponse
    from django.conf import settings
    from .models import Requisicion

    requisicion = get_object_or_404(Requisicion, pk=pk)

    # URL para el QR — prioriza el host real del proxy (Cloudflare/Traefik)
    # si no, usa SITE_URL de settings
    host = request.META.get('HTTP_X_FORWARDED_HOST', '')
    if not host or 'sslip.io' in host:
        site_url = settings.SITE_URL.rstrip('/')
    else:
        proto = request.META.get('HTTP_X_FORWARDED_PROTO', 'https')
        site_url = f"{proto}://{host.split(',')[0].strip()}"
    relative_url = reverse('presupuestos:requisicion_editar', kwargs={'pk': requisicion.cr8ca_requisicionid})
    qr_data = f"{site_url}{relative_url}"

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
    """Genera un PDF de la requisición usando Playwright"""
    from .models import Requisicion
    from .utils_documentos import render_requisicion_pdf
    from django.http import HttpResponse

    requisicion = get_object_or_404(Requisicion, pk=pk)
    
    # Generar PDF bytes
    pdf_content = render_requisicion_pdf(requisicion)
    
    if not pdf_content:
        return HttpResponse('Error generando el PDF. Verifique con administración.', status=500)

    response = HttpResponse(pdf_content, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="Requisicion_{requisicion.cr8ca_requisicion}.pdf"'
    return response


@login_required
def requisicion_docx(request, pk):
    """Genera un documento Word (.docx) de la requisición"""
    from .models import Requisicion
    from .utils_docx import generate_requisicion_docx
    from django.http import HttpResponse

    requisicion = get_object_or_404(Requisicion, pk=pk)
    
    try:
        docx_content = generate_requisicion_docx(requisicion)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return HttpResponse(f'Error generando el documento Word: {str(e)}', status=500)
        
    response = HttpResponse(docx_content, content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    response['Content-Disposition'] = f'attachment; filename="Requisicion_{requisicion.cr8ca_requisicion}.docx"'
    
    return response



@staff_member_required
@login_required
@mobile_permission_required('finanzas')
def requisicion_dashboard(request):
    """Vista de dashboard para Requisiciones — filtrada por departamento del usuario"""
    from .models import Requisicion
    from django.db.models import Sum, Count, Q
    from django.utils import timezone
    from datetime import timedelta

    search_query = request.GET.get('q', '').strip()
    es_procura = request.user.groups.filter(name__in=['Procura', 'PROCURA']).exists()

    # Departamento del usuario logueado
    dept = None
    if hasattr(request.user, 'perfil'):
        dept = request.user.perfil.departamento

    if es_procura:
        # Procura ve todas las requisiciones sin filtro de departamento,
        # pero excluye Borrador y Pendiente (no les interesa)
        dept_q = Q()
    elif dept:
        dept_user_ids = dept.usuarios.values_list('usuario_id', flat=True)
        dept_q = Q(usuario_solicitante_id__in=dept_user_ids)
    else:
        dept_q = Q(usuario_solicitante=request.user)

    # Base queryset filtrada por departamento
    base_qs = Requisicion.objects.filter(dept_q)
    if es_procura:
        base_qs = base_qs.exclude(estado_requisicion__in=['BORRADOR', 'PENDIENTE'])

    # Métricas (siempre filtradas por departamento)
    total_reqs = base_qs.count()
    total_monto = base_qs.aggregate(total=Sum('cr8ca_totalenarticulos'))['total'] or 0

    hace_30_dias = timezone.now().date() - timedelta(days=30)
    reqs_recientes = base_qs.filter(Q(fecha__gte=hace_30_dias) | Q(createdon__gte=hace_30_dias)).count()

    prioridad_data = base_qs.values('cr8ca_prioridad').annotate(count=Count('cr8ca_prioridad')).order_by('cr8ca_prioridad')

    # Últimas requisiciones con búsqueda
    if search_query:
        # Sin filtro de departamento para que pueda buscar en cualquier área
        query = Requisicion.objects.filter(
            Q(cr8ca_requisicion__icontains=search_query) |
            Q(cr8ca_asunto__icontains=search_query) |
            Q(cr8ca_motivo__icontains=search_query)
        )
        if es_procura:
            query = query.exclude(estado_requisicion__in=['BORRADOR', 'PENDIENTE'])
    else:
        query = base_qs
    ultimas_requisiciones = query.order_by('-fecha', '-createdon')[:20]

    # Estadísticas del departamento (solo el del usuario)
    stats_departamento = base_qs.values('usuario_solicitante__perfil__departamento__nombre') \
        .annotate(total=Sum('cr8ca_totalenarticulos'), count=Count('cr8ca_requisicion')) \
        .order_by('-total')

    # Mis requisiciones (usuario actual)
    mis_requisiciones = base_qs.filter(
        Q(usuario_solicitante=request.user) | Q(usuario_en_nombre_de=request.user)
    ).order_by('-fecha', '-createdon')[:15]

    context = {
        'total_reqs': total_reqs,
        'total_monto': total_monto,
        'reqs_recientes': reqs_recientes,
        'prioridad_data': prioridad_data,
        'ultimas_requisiciones': ultimas_requisiciones,
        'stats_departamento': stats_departamento,
        'mis_requisiciones': mis_requisiciones,
        'search_query': search_query,
        'title': 'Dashboard de Requisiciones',
        'dept': dept,
        'es_procura': es_procura,
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

@login_required
def api_get_partida_items(request, partida_id):
    """Retorna JSON con los ítems de presupuesto de una partida específica."""
    from .models import ItemPresupuesto
    items = ItemPresupuesto.objects.filter(partida_id=partida_id).values('id', 'concepto')
    return JsonResponse({'items': list(items)})

@staff_member_required
def import_requisiciones_json(request):
    """
    Vista para importar requisiciones directamente desde un JSON de Dynamics.
    """
    if request.method == 'POST':
        import json
        import requests
        from .models import Requisicion
        from decimal import Decimal
        
        try:
            use_api = request.POST.get('use_api') == 'true'
            
            if use_api:
                api_token = request.POST.get('api_token', '').strip()
                api_url = request.POST.get('api_url', '').strip().rstrip('/')
                api_filter = request.POST.get('api_filter', '').strip()
                
                # Construir URL de la API
                # Seleccionamos solo los campos necesarios para optimizar
                fields = "cr8ca_requisicionid,cr8ca_requisicion,cr8ca_asunto,cr8ca_motivo,cr8ca_comentarios,_cr8ca_proveedorasignado_value,cr8ca_costo,createdon,cr8ca_prioridad"
                endpoint = f"{api_url}/api/data/v9.2/cr8ca_requisicions?$select={fields}"
                
                if api_filter:
                    # Si el filtro no empieza con &, lo agregamos
                    if not api_filter.startswith('$') and not api_filter.startswith('&'):
                        endpoint += f"&$filter={api_filter}"
                    else:
                        endpoint += f"&{api_filter}" if '&' in api_filter or '$' in api_filter else f"&{api_filter}"
                
                headers = {
                    'Authorization': f'Bearer {api_token}',
                    'Accept': 'application/json',
                    'OData-MaxVersion': '4.0',
                    'OData-Version': '4.0',
                    'Prefer': 'odata.include-annotations="*"'
                }
                
                response = requests.get(endpoint, headers=headers, timeout=30)
                
                if response.status_code != 200:
                    error_data = response.json() if response.content else {'error': 'No content'}
                    msg = error_data.get('error', {}).get('message', response.text)
                    return JsonResponse({'success': False, 'message': f'Error Dynamics ({response.status_code}): {msg}'}, status=400)
                
                data = response.json()
            else:
                raw_data = request.POST.get('json_data', '').strip()
                if not raw_data:
                    return JsonResponse({'success': False, 'message': 'No se proporcionaron datos JSON.'}, status=400)
                
                try:
                    data = json.loads(raw_data)
                except json.JSONDecodeError as je:
                    return JsonResponse({'success': False, 'message': f'JSON Inválido: {str(je)}'}, status=400)
                
            # Soporte para formato Dynamics {"value": [...]} o lista directa
            items = data.get('value', []) if isinstance(data, dict) else data
            
            if not items:
                return JsonResponse({'success': False, 'message': 'No se encontraron registros en el JSON.'}, status=400)
            
            created_count = 0
            updated_count = 0
            linked_providers = 0
            
            # Mapeo de prioridades de Dynamics
            priority_map = {
                380160000: 1, # Baja
                380160001: 2, # Normal
                380160002: 3, # Alta
                380160003: 4, # Urgencia
                380160004: 5, # Emergencia
            }
            
            # Cache de proveedores para evitar queries repetitivas
            proveedores_cache = {}
            
            skipped_count = 0
            for item in items:
                # El ID de Dynamics es vital para el upsert
                req_id = item.get('cr8ca_requisicionid')
                if not req_id:
                    continue
                
                raw_priority = item.get('cr8ca_prioridad')
                priority = priority_map.get(raw_priority, 2)
                
                # Mapeo de Proveedor (GUID de Dynamics)
                proveedor_guid = item.get('_cr8ca_proveedorasignado_value')
                proveedor_obj = None
                
                if proveedor_guid:
                    if proveedor_guid in proveedores_cache:
                        proveedor_obj = proveedores_cache[proveedor_guid]
                    else:
                        from mantenimiento.models import Empresa
                        proveedor_obj = Empresa.objects.filter(dynamics_guid=proveedor_guid).first()
                        if proveedor_obj:
                            proveedores_cache[proveedor_guid] = proveedor_obj
                            linked_providers += 1
                
                # Mapeo de campos (con valores por defecto para evitar errores de integridad)
                defaults = {
                    'cr8ca_requisicion': item.get('cr8ca_requisicion'),
                    'cr8ca_asunto': item.get('cr8ca_asunto') or 'Sin asunto (Importado Dynamics)',
                    'cr8ca_motivo': item.get('cr8ca_motivo') or 'Sin motivo (Importado Dynamics)',
                    'cr8ca_comentarios': item.get('cr8ca_comentarios'),
                    'cr8ca_totalenarticulos': Decimal(str(item.get('cr8ca_costo') or 0)),
                    'cr8ca_prioridad': priority,
                    'createdon': item.get('createdon'),
                    'proveedor': proveedor_obj,
                }
                
                # 1. Intentar buscar por UUID de Dynamics
                if Requisicion.objects.filter(cr8ca_requisicionid=req_id).exists():
                    # El usuario solicitó SOLO jalar los nuevos, así que obviamos los existentes
                    skipped_count += 1
                    continue
                
                # 2. Verificar si el NOMBRE ya existe (aunque no tenga UUID vinculado aún)
                nombre_req = defaults.get('cr8ca_requisicion')
                if Requisicion.objects.filter(cr8ca_requisicion=nombre_req).exists():
                    skipped_count += 1
                    continue
                    
                # 3. Si es totalmente nueva, crear
                obj = Requisicion.objects.create(
                    cr8ca_requisicionid=req_id,
                    **defaults
                )
                obj.usuario_solicitante = request.user
                obj.estado_requisicion = 'BORRADOR'
                obj.save()
                from .models import RequisicionHistorial
                RequisicionHistorial.objects.create(
                    requisicion=obj, estado_anterior=None,
                    estado_nuevo='BORRADOR', usuario=request.user,
                    descripcion="Requisición importada"
                )
                created_count += 1
            
            msg = f'Proceso completado. Se importaron {created_count} nuevas requisiciones.'
            if skipped_count > 0:
                msg += f' Se obviaron {skipped_count} existentes o duplicados.'
            msg += f' Se vincularon {linked_providers} proveedores.'

            return JsonResponse({'success': True, 'message': msg})
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({'success': False, 'message': f'Error en el servidor: {str(e)}'}, status=500)
            
    # GET: Mostrar la interfaz de pegado
    from django.contrib import admin
    context = {
        **admin.site.each_context(request),
        'title': 'Importador Rápido Dynamics (JSON)',
    }
    return render(request, 'admin/presupuestos/requisicion/import_json.html', context)

@staff_member_required
@require_POST
def trigger_power_automate_sync(request):
    """
    Inicia el flujo de Power Automate mediante una petición POST al webhook proporcionado.
    """
    import requests
    
    # URL proporcionada por el usuario para listar y enviar requisiciones
    url = "https://ce675e3ed2704594af019ed8d7d5f6.d7.environment.api.powerplatform.com:443/powerautomate/automations/direct/workflows/c29ebdfe41f5419a8e8b28278bcc08cd/triggers/manual/paths/invoke?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=uKWu_vjHtCHPKML9eoJLx6O8gluP9e0FUU0vOP0YqDA"
    
    try:
        # Hacemos la petición a Power Automate (no esperamos el resultado aquí, 
        # PA enviará los datos de vuelta a nuestro webhook asíncronamente)
        response = requests.post(url, json={
            "triggered_by": request.user.username,
            "callback_url": request.build_absolute_uri('/presupuestos/webhook/dynamics-sync/')
        }, timeout=10)
        
        if response.status_code in [200, 202]:
            return JsonResponse({
                'success': True, 
                'message': 'Sincronización Cloud iniciada. Power Automate está procesando los datos y los enviará a Softcom en unos momentos.'
            })
        else:
            return JsonResponse({
                'success': False, 
                'message': f'Error al disparar Power Automate (Status {response.status_code}): {response.text}'
            })
            
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error de conexión: {str(e)}'}, status=500)


@staff_member_required
@login_required
@require_POST
def notificar_recepcion(request, pk):
    import json
    from datetime import datetime
    from django.contrib.auth.models import Group, User
    from django.utils import timezone
    try:
        from .models import Requisicion
        requisicion = get_object_or_404(Requisicion, pk=pk)

        if requisicion.estado_requisicion not in ['EN_ORDEN_COMPRA', 'AUTORIZADO']:
            return JsonResponse({'success': False, 'message': 'La requisición debe estar procesada a Orden de Compra para notificar recepción.'}, status=400)

        data = json.loads(request.body)
        fecha_entrega_str = data.get('fecha_probable_entrega', '').strip()

        if not fecha_entrega_str:
            return JsonResponse({'success': False, 'message': 'Debe indicar la fecha probable de entrega.'}, status=400)

        try:
            fecha_probable = datetime.strptime(fecha_entrega_str, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({'success': False, 'message': 'Formato de fecha inválido.'}, status=400)

        requisicion.recepcion_notificada = True
        requisicion.fecha_probable_entrega = fecha_probable
        requisicion.save()

        # Notificar a usuarios del grupo Almacenes
        from mantenimiento.models import NotificacionMantenimiento
        almacenes_group = Group.objects.filter(name__in=['Almacenes', 'ALMACEN']).first()
        if almacenes_group:
            mensaje = (
                f"📦 Recepción notificada - {requisicion.cr8ca_requisicion}: {requisicion.cr8ca_asunto[:60]}. "
                f"Fecha probable de entrega: {fecha_probable.strftime('%d/%m/%Y')}."
            )
            for user in almacenes_group.user_set.filter(is_active=True):
                NotificacionMantenimiento.objects.create(
                    user=user,
                    mensaje=mensaje,
                    tipo='INFO'
                )

        return JsonResponse({'success': True, 'message': f'Recepción notificada al personal de Almacenes para {requisicion.cr8ca_requisicion}.'})

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return JsonResponse({'success': False, 'message': f'Error interno: {str(e)}'}, status=500)


@staff_member_required
@login_required
@require_POST
def api_update_fecha_entrega(request, pk):
    import json
    from datetime import datetime
    from .models import Requisicion, NotaRequisicion
    try:
        requisicion = get_object_or_404(Requisicion, pk=pk)
        data = json.loads(request.body)
        fecha_str = data.get('fecha_probable_entrega', '').strip()
        if not fecha_str:
            return JsonResponse({'success': False, 'message': 'Debe indicar una fecha.'}, status=400)
        try:
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({'success': False, 'message': 'Formato de fecha inválido.'}, status=400)
        vieja = requisicion.fecha_probable_entrega
        requisicion.fecha_probable_entrega = fecha
        requisicion.recepcion_notificada = True
        requisicion.save(update_fields=['fecha_probable_entrega', 'recepcion_notificada'])
        NotaRequisicion.objects.create(
            requisicion=requisicion,
            usuario=request.user,
            texto=f"📅 Fecha probable de entrega actualizada: {vieja.isoformat() if vieja else '—'} → {fecha.isoformat()}"
        )
        return JsonResponse({'success': True, 'message': 'Fecha probable de entrega actualizada.'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error: {str(e)}'}, status=500)


@staff_member_required
@login_required
@require_POST
def procesar_requisicion(request, pk):
    try:
        from .models import Requisicion
        import json
        from mantenimiento.models import Empresa
        requisicion = get_object_or_404(Requisicion, pk=pk)

        if not request.user.groups.filter(name__in=['Procura', 'PROCURA']).exists():
            return JsonResponse({'success': False, 'message': 'Solo usuarios del grupo Procura pueden procesar requisiciones.'}, status=403)

        if requisicion.estado_requisicion not in ['AUTORIZADO', 'VISTO_PROCURA', 'PROCURA_PROCESANDO']:
            return JsonResponse({'success': False, 'message': 'La requisición debe estar Autorizada, Visto por Procura o en Procesamiento.'}, status=400)

        _registrar_historial(requisicion, 'PROCURA_PROCESANDO', usuario=request.user)
        requisicion.estado_requisicion = 'PROCURA_PROCESANDO'
        requisicion.save()

        # Armar datos de la requisición para el modal
        articulos_data = []
        for art in requisicion.articulos.all():
            proveedor = art.proveedor
            articulos_data.append({
                'id': str(art.cr8ca_itemderequisicionid),
                'descripcion': art.cr8ca_articulo or '',
                'cantidad': float(art.cr8ca_cantidad or 0),
                'costo_actual': float(art.cr8ca_costoaproximado or 0),
                'subtotal': float(art.subtotal or 0),
                'proveedor_actual': proveedor.nombre if proveedor else '',
                'proveedor_id': proveedor.id if proveedor else None,
            })

        proveedores_data = [
            {'id': p.id, 'nombre': p.nombre}
            for p in Empresa.objects.all().order_by('nombre')
        ]

        documentos_data = []
        for doc in requisicion.documentos.all():
            archivo_nombre = None
            if doc.archivo:
                import os
                archivo_nombre = os.path.basename(doc.archivo.name)
            documentos_data.append({
                'id': doc.id,
                'nombre': doc.nombre or archivo_nombre or f"Documento #{doc.id}",
                'archivo_nombre': archivo_nombre,
                'url': doc.get_proxy_url(),
                'creado_en': doc.creado_en.strftime('%d/%m/%Y %H:%M') if doc.creado_en else '',
            })

        data = {
            'requisicion': {
                'numero': requisicion.cr8ca_requisicion,
                'asunto': requisicion.cr8ca_asunto,
                'motivo': requisicion.cr8ca_motivo or '',
                'total_actual': float(requisicion.cr8ca_totalenarticulos or 0),
                'total_estimado': float(requisicion.total_estimado or 0),
            },
            'articulos': articulos_data,
            'proveedores': proveedores_data,
            'documentos': documentos_data,
        }

        return JsonResponse({'success': True, 'data': data, 'message': 'Procesando requisición...'})

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return JsonResponse({'success': False, 'message': f'Error interno: {str(e)}'}, status=500)


@staff_member_required
@login_required
@require_POST
@csrf_exempt
def finalizar_procesamiento(request, pk):
    try:
        import json
        from .models import Requisicion, OrdenCompra, OrdenCompraArticulo
        from decimal import Decimal
        from mantenimiento.models import Empresa, NotificacionMantenimiento

        requisicion = get_object_or_404(Requisicion, pk=pk)

        if not request.user.groups.filter(name__in=['Procura', 'PROCURA']).exists():
            return JsonResponse({'success': False, 'message': 'Solo usuarios del grupo Procura pueden finalizar procesamiento.'}, status=403)

        if requisicion.estado_requisicion != 'PROCURA_PROCESANDO':
            return JsonResponse({'success': False, 'message': 'La requisición debe estar en estado Procura Procesando.'}, status=400)

        data = json.loads(request.body)
        articulos_data = data.get('articulos', [])
        tipo_documento = data.get('tipo_documento', 'OC')
        if tipo_documento not in ('OC', 'DOIH'):
            tipo_documento = 'OC'

        if not articulos_data:
            return JsonResponse({'success': False, 'message': 'No hay artículos para procesar.'}, status=400)

        # Agrupar artículos por proveedor
        oc_articulos_por_proveedor = {}
        for art_data in articulos_data:
            proveedor_id = art_data.get('proveedor_id')
            if not proveedor_id:
                return JsonResponse({'success': False, 'message': f'Artículo "{art_data.get("descripcion", "")}" no tiene proveedor asignado.'}, status=400)
            proveedor_id = int(proveedor_id)
            if proveedor_id not in oc_articulos_por_proveedor:
                oc_articulos_por_proveedor[proveedor_id] = []
            oc_articulos_por_proveedor[proveedor_id].append(art_data)

        # Crear una Orden de Compra por proveedor
        oc_numbers = []
        for proveedor_id, articulos_prov in oc_articulos_por_proveedor.items():
            proveedor = Empresa.objects.filter(id=proveedor_id).first()
            if not proveedor:
                continue

            subtotal_oc = sum(
                Decimal(str(a.get('cantidad', 0))) * Decimal(str(a.get('costo_unitario', 0)))
                for a in articulos_prov
            )
            impuestos_oc = sum(Decimal(str(a.get('impuestos', 0))) for a in articulos_prov)
            total_oc = subtotal_oc + impuestos_oc

            oc = OrdenCompra.objects.create(
                requisicion=requisicion,
                proveedor=proveedor,
                tipo_documento=tipo_documento,
                subtotal=subtotal_oc,
                impuestos=impuestos_oc,
                total=total_oc,
                creado_por=request.user,
            )
            oc_numbers.append(oc.numero_oc)

            for art_data in articulos_prov:
                from .models import ArticuloRequisicion
                art_req = ArticuloRequisicion.objects.filter(
                    cr8ca_itemderequisicionid=art_data.get('id')
                ).first()

                cantidad = Decimal(str(art_data.get('cantidad', 0)))
                costo = Decimal(str(art_data.get('costo_unitario', 0)))

                OrdenCompraArticulo.objects.create(
                    orden_compra=oc,
                    articulo_requisicion=art_req,
                    descripcion=art_data.get('descripcion', ''),
                    cantidad=cantidad,
                    costo_unitario=costo,
                    subtotal=cantidad * costo,
                )

        # Cambiar estado de la requisición
        _registrar_historial(requisicion, 'EN_ORDEN_COMPRA', usuario=request.user,
                             descripcion=f"OC: {', '.join(oc_numbers)}" if oc_numbers else '')
        requisicion.estado_requisicion = 'EN_ORDEN_COMPRA'
        requisicion.save()

        # Notificar al solicitante
        if requisicion.usuario_solicitante:
            NotificacionMantenimiento.objects.create(
                user=requisicion.usuario_solicitante,
                mensaje=f"✅ Requisición {requisicion.cr8ca_requisicion} procesada a Orden de Compra.",
                tipo='SUCCESS'
            )

        return JsonResponse({
            'success': True,
            'message': f'Requisición {requisicion.cr8ca_requisicion} procesada a Orden de Compra exitosamente.',
            'oc_numbers': oc_numbers,
        })

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return JsonResponse({'success': False, 'message': f'Error interno: {str(e)}'}, status=500)


@login_required
@staff_member_required
@require_POST
def revertir_orden_compra(request, pk):
    try:
        from .models import Requisicion

        if not request.user.groups.filter(name__in=['Procura', 'PROCURA']).exists():
            return JsonResponse({'success': False, 'message': 'Solo usuarios del grupo Procura pueden revertir órdenes de compra.'}, status=403)

        requisicion = get_object_or_404(Requisicion, pk=pk)

        if requisicion.estado_requisicion != 'EN_ORDEN_COMPRA':
            return JsonResponse({'success': False, 'message': 'La requisición debe estar en estado En Orden de Compra.'}, status=400)

        if requisicion.recepcion_notificada:
            return JsonResponse({'success': False, 'message': 'No se puede revertir: ya se notificó recepción a Almacenes.'}, status=400)

        # Eliminar órdenes de compra asociadas
        requisicion.ordenes_compra.all().delete()

        # Revertir estado
        _registrar_historial(requisicion, 'PROCURA_PROCESANDO', usuario=request.user,
                             descripcion="Revertido desde En Orden de Compra")
        requisicion.estado_requisicion = 'PROCURA_PROCESANDO'
        requisicion.save(update_fields=['estado_requisicion'])

        return JsonResponse({
            'success': True,
            'message': f'Requisición {requisicion.cr8ca_requisicion} revertida a Procura Procesando. Las órdenes de compra fueron eliminadas.'
        })

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return JsonResponse({'success': False, 'message': f'Error interno: {str(e)}'}, status=500)


@login_required
@staff_member_required
def detalle_orden_compra(request, pk):
    try:
        from .models import OrdenCompra

        if not request.user.groups.filter(name__in=['Procura', 'PROCURA']).exists():
            return JsonResponse({'success': False, 'message': 'Solo usuarios del grupo Procura pueden ver órdenes de compra.'}, status=403)

        oc = get_object_or_404(OrdenCompra, pk=pk)

        articulos = []
        for art in oc.articulos.all():
            articulos.append({
                'id': art.id,
                'articulo_requisicion_id': str(art.articulo_requisicion_id) if art.articulo_requisicion_id else None,
                'descripcion': art.descripcion,
                'cantidad': float(art.cantidad),
                'costo_unitario': float(art.costo_unitario),
                'subtotal': float(art.subtotal),
            })

        proveedores_list = []
        from mantenimiento.models import Empresa
        for p in Empresa.objects.all().order_by('nombre'):
            proveedores_list.append({'id': p.id, 'nombre': p.nombre})

        centros_list = []
        from .models import CentroCosto
        for cc in CentroCosto.objects.filter(activo=True).order_by('nombre'):
            centros_list.append({'id': cc.id, 'nombre': cc.nombre})

        data = {
            'id': oc.id,
            'numero_oc': oc.numero_oc,
            'tipo_documento': oc.tipo_documento,
            'estado': oc.estado,
            'proveedor_id': oc.proveedor_id,
            'proveedor_nombre': oc.proveedor.nombre if oc.proveedor else '',
            'centro_costo_id': oc.centro_costo_id,
            'centro_costo_nombre': oc.centro_costo.nombre if oc.centro_costo else '',
            'anticipo': oc.anticipo,
            'anticipo_porcentaje': float(oc.anticipo_porcentaje) if oc.anticipo_porcentaje else 0,
            'contraentrega': oc.contraentrega,
            'credito': oc.credito,
            'credito_dias': oc.credito_dias,
            'doc_factura': oc.doc_factura,
            'doc_estimacion': oc.doc_estimacion,
            'doc_respaldo': oc.doc_respaldo,
            'doc_garantia': oc.doc_garantia,
            'subtotal': float(oc.subtotal),
            'impuestos': float(oc.impuestos),
            'total': float(oc.total),
            'fecha_creacion': oc.fecha_creacion.strftime('%d/%m/%Y %H:%M'),
            'fecha_entrega_estimada': oc.fecha_entrega_estimada.strftime('%Y-%m-%d') if oc.fecha_entrega_estimada else '',
            'notas': oc.notas or '',
            'creado_por': oc.creado_por.get_full_name() or str(oc.creado_por) if oc.creado_por else '',
            'requisicion_numero': oc.requisicion.cr8ca_requisicion if oc.requisicion else '',
            'articulos': articulos,
            'proveedores': proveedores_list,
            'centros_costo': centros_list,
        }

        return JsonResponse({'success': True, 'data': data})

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return JsonResponse({'success': False, 'message': f'Error interno: {str(e)}'}, status=500)


@login_required
@staff_member_required
@require_POST
def actualizar_orden_compra(request, pk):
    try:
        import json
        from .models import OrdenCompra, OrdenCompraArticulo
        from decimal import Decimal
        from mantenimiento.models import Empresa

        if not request.user.groups.filter(name__in=['Procura', 'PROCURA']).exists():
            return JsonResponse({'success': False, 'message': 'Solo usuarios del grupo Procura pueden editar órdenes de compra.'}, status=403)

        oc = get_object_or_404(OrdenCompra, pk=pk)
        data = json.loads(request.body)

        # Actualizar campos de cabecera
        oc.estado = data.get('estado', oc.estado)
        if data.get('proveedor_id'):
            oc.proveedor_id = int(data['proveedor_id'])
        oc.impuestos = Decimal(str(data.get('impuestos', oc.impuestos)))
        oc.fecha_entrega_estimada = data.get('fecha_entrega_estimada') or None
        oc.notas = data.get('notas', oc.notas)

        # Centro de costo
        if 'centro_costo_id' in data:
            oc.centro_costo_id = data['centro_costo_id'] or None

        # Condiciones de pago
        if 'anticipo' in data:
            oc.anticipo = bool(data['anticipo'])
        if 'anticipo_porcentaje' in data:
            oc.anticipo_porcentaje = Decimal(str(data['anticipo_porcentaje'])) if data['anticipo_porcentaje'] else None
        if 'contraentrega' in data:
            oc.contraentrega = bool(data['contraentrega'])
        if 'credito' in data:
            oc.credito = bool(data['credito'])
        if 'credito_dias' in data:
            oc.credito_dias = int(data['credito_dias']) if data['credito_dias'] else None

        # Documentación
        if 'doc_factura' in data:
            oc.doc_factura = bool(data['doc_factura'])
        if 'doc_estimacion' in data:
            oc.doc_estimacion = bool(data['doc_estimacion'])
        if 'doc_respaldo' in data:
            oc.doc_respaldo = bool(data['doc_respaldo'])
        if 'doc_garantia' in data:
            oc.doc_garantia = bool(data['doc_garantia'])

        # Actualizar artículos
        for art_data in data.get('articulos', []):
            art_id = art_data.get('id')
            if not art_id:
                continue
            art = oc.articulos.filter(id=art_id).first()
            if not art:
                continue
            art.cantidad = Decimal(str(art_data.get('cantidad', art.cantidad)))
            art.costo_unitario = Decimal(str(art_data.get('costo_unitario', art.costo_unitario)))
            art.save()

        # Recalcular totales
        subtotal = sum(a.subtotal for a in oc.articulos.all())
        oc.subtotal = subtotal
        oc.total = subtotal + oc.impuestos
        oc.save()

        return JsonResponse({
            'success': True,
            'message': f'Orden {oc.numero_oc} actualizada exitosamente.'
        })

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return JsonResponse({'success': False, 'message': f'Error interno: {str(e)}'}, status=500)
