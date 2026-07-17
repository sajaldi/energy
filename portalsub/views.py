import calendar
from datetime import date
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db.models import Count, Q
from mantenimiento.models import Empresa, DocumentoEmpresa, TecnicoPuesto, PuestoTrabajo
from presupuestos.models import OrdenCompra
from notificaciones.utils import crear_notificacion, notificar_a_grupo
from .models import (
    PerfilContratista, ExpedienteMensual, DocumentoOrdenCompra, DocumentoPersonal,
    TipoDocumentoPersonal, TipoEntregable, EntregableContratista, DocumentoEntregable,
    HistorialPersonal,
)
from .decorators import contratista_required, get_empresa


def login_view(request):
    if request.user.is_authenticated:
        if hasattr(request.user, 'perfil_contratista'):
            return redirect('portalsub:dashboard')
        return redirect('admin:index')

    error = None
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            if hasattr(user, 'perfil_contratista') and user.perfil_contratista.activo:
                login(request, user)
                return redirect('portalsub:dashboard')
            error = 'No tienes acceso al portal de subcontratistas.'
        else:
            error = 'Usuario o contraseña incorrectos.'

    return render(request, 'portalsub/login.html', {'error': error})


def logout_view(request):
    logout(request)
    return redirect('portalsub:login')


@contratista_required
def dashboard(request):
    empresa = get_empresa(request)
    today = date.today()

    expediente_actual, _ = ExpedienteMensual.objects.get_or_create(
        empresa=empresa,
        mes=today.month,
        anio=today.year,
        defaults={'estado': 'BORRADOR'}
    )

    docs = DocumentoEmpresa.objects.filter(empresa=empresa)
    tipos_requeridos = ['RTN', 'PLANILLA_IHSS', 'ALTAS_BAJAS', 'EXPEDIENTE_MENSUAL', 'REPORTES']
    docs_completos = docs.filter(es_valido=True).values_list('tipo_documento', flat=True).distinct()

    docs_mes_actual = docs.filter(es_valido=True, mes=today.month, anio=today.year)
    tipos_mes_subidos = set(docs_mes_actual.values_list('tipo_documento', flat=True))
    tipos_mes_requeridos = ['PLANILLA_IHSS', 'ALTAS_BAJAS', 'EXPEDIENTE_MENSUAL', 'REPORTES']
    progreso_mes = int(len(tipos_mes_subidos & set(tipos_mes_requeridos)) / len(tipos_mes_requeridos) * 100) if tipos_mes_requeridos else 0

    total_personal = TecnicoPuesto.objects.filter(empresa=empresa).count()
    vigentes = TecnicoPuesto.objects.filter(empresa=empresa, esta_vigente=True).count()

    meses = ExpedienteMensual.objects.filter(empresa=empresa).order_by('-anio', '-mes')[:12]

    configs = EntregableContratista.objects.filter(
        empresa=empresa, activo=True, tipo_entregable__activo=True
    ).select_related('tipo_entregable')

    docs_entregables = DocumentoEntregable.objects.filter(empresa=empresa, anio=today.year)
    doc_map = {}
    for d in docs_entregables:
        doc_map[(d.tipo_entregable_id, d.mes)] = d

    total_aplican = 0
    total_completos = 0
    for c in configs:
        for m in c.get_meses():
            total_aplican += 1
            doc = doc_map.get((c.tipo_entregable_id, m))
            if doc and doc.es_valido:
                total_completos += 1

    progreso_anual = int(total_completos / total_aplican * 100) if total_aplican else 0

    context = {
        'active_tab': 'dashboard',
        'empresa': empresa,
        'expediente_actual': expediente_actual,
        'progreso_mes': progreso_mes,
        'progreso_anual': progreso_anual,
        'entregables_completos': total_completos,
        'entregables_totales': total_aplican,
        'docs_completos': len(set(docs_completos) & set(tipos_requeridos)),
        'docs_totales': len(tipos_requeridos),
        'total_personal': total_personal,
        'personal_vigente': vigentes,
        'personal_no_vigente': total_personal - vigentes,
        'meses': meses,
        'mes_actual': today.month,
        'anio_actual': today.year,
    }
    return render(request, 'portalsub/dashboard.html', context)


@contratista_required
def expediente(request, mes=None, anio=None):
    empresa = get_empresa(request)
    today = date.today()
    anio = anio or today.year

    if not EntregableContratista.objects.filter(empresa=empresa).exists():
        tipos = TipoEntregable.objects.filter(activo=True)
        EntregableContratista.objects.bulk_create([
            EntregableContratista(empresa=empresa, tipo_entregable=t)
            for t in tipos
        ], ignore_conflicts=True)

    configs = EntregableContratista.objects.filter(
        empresa=empresa, activo=True,
        tipo_entregable__activo=True,
    ).select_related('tipo_entregable').order_by('tipo_entregable__nombre')

    meses_nombre = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']

    docs_subidos = DocumentoEntregable.objects.filter(
        empresa=empresa, anio=anio
    ).select_related('tipo_entregable')

    doc_map = {}
    for d in docs_subidos:
        key = (d.tipo_entregable_id, d.mes)
        doc_map[key] = d

    entregas = []
    for c in configs:
        meses = c.get_meses()
        fila = {'config': c, 'meses': {}}
        for m in range(1, 13):
            aplica = m in meses
            key = (c.tipo_entregable_id, m)
            doc = doc_map.get(key)
            fila['meses'][m] = {
                'aplica': aplica,
                'completo': doc is not None and doc.es_valido,
            }
        entregas.append(fila)

    total_aplican = sum(1 for f in entregas for m in f['meses'].values() if m['aplica'])
    total_completos = sum(1 for f in entregas for m in f['meses'].values() if m['aplica'] and m['completo'])
    progreso = int(total_completos / total_aplican * 100) if total_aplican else 0

    context = {
        'active_tab': 'expediente',
        'empresa': empresa,
        'anio': anio,
        'meses_nombre': meses_nombre,
        'entregas': entregas,
        'progreso': progreso,
        'total_aplican': total_aplican,
        'total_completos': total_completos,
    }
    return render(request, 'portalsub/expediente.html', context)


@contratista_required
def expediente_mes(request, mes, anio):
    empresa = get_empresa(request)
    today = date.today()
    anio = anio or today.year

    expediente_obj, _ = ExpedienteMensual.objects.get_or_create(
        empresa=empresa, mes=mes, anio=anio,
        defaults={'estado': 'BORRADOR'}
    )

    if not EntregableContratista.objects.filter(empresa=empresa).exists():
        tipos = TipoEntregable.objects.filter(activo=True)
        EntregableContratista.objects.bulk_create([
            EntregableContratista(empresa=empresa, tipo_entregable=t)
            for t in tipos
        ], ignore_conflicts=True)

    configs = EntregableContratista.objects.filter(
        empresa=empresa, activo=True,
        tipo_entregable__activo=True,
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
            'completo': doc is not None and doc.es_valido,
        })

    total_count = len(items)
    complete_count = sum(1 for i in items if i['completo'])
    progreso = int(complete_count / total_count * 100) if total_count else 0

    context = {
        'active_tab': 'expediente',
        'empresa': empresa,
        'expediente': expediente_obj,
        'items': items,
        'mes': mes,
        'anio': anio,
        'mes_nombre': calendar.month_name[mes].capitalize(),
        'progreso': progreso,
        'total_count': total_count,
        'complete_count': complete_count,
    }
    return render(request, 'portalsub/expediente_mes.html', context)


@contratista_required
@require_POST
def subir_documento(request, mes, anio):
    empresa = get_empresa(request)
    tipo = request.POST.get('tipo_documento')
    archivo = request.FILES.get('archivo')
    descripcion = request.POST.get('descripcion', '')

    if not tipo or not archivo:
        return JsonResponse({'status': 'error', 'message': 'Faltan datos requeridos.'}, status=400)

    if tipo in dict(DocumentoEmpresa.TIPO_DOC_CHOICES):
        doc, created = DocumentoEmpresa.objects.update_or_create(
            empresa=empresa,
            tipo_documento=tipo,
            mes=mes if tipo in ['PLANILLA_IHSS', 'ALTAS_BAJAS', 'EXPEDIENTE_MENSUAL', 'REPORTES', 'OTRO'] else None,
            anio=anio if tipo in ['PLANILLA_IHSS', 'ALTAS_BAJAS', 'EXPEDIENTE_MENSUAL', 'REPORTES', 'OTRO'] else None,
            defaults={
                'archivo': archivo,
                'es_valido': True,
                'descripcion': descripcion,
            }
        )
        return JsonResponse({
            'status': 'success',
            'message': 'Documento subido correctamente.',
            'documento': {
                'id': doc.id,
                'tipo': doc.tipo_documento,
                'nombre': doc.archivo.name,
                'url': doc.archivo.url,
                'es_valido': doc.es_valido,
            }
        })

    return JsonResponse({'status': 'error', 'message': 'Tipo de documento inválido.'}, status=400)


@contratista_required
@require_POST
def eliminar_documento(request, doc_id):
    empresa = get_empresa(request)
    doc = get_object_or_404(DocumentoEmpresa, id=doc_id, empresa=empresa)
    doc.archivo.delete(save=False)
    doc.delete()
    return JsonResponse({'status': 'success', 'message': 'Documento eliminado.'})


@contratista_required
@require_POST
def subir_entregable(request):
    empresa = get_empresa(request)
    tipo_id = request.POST.get('tipo_entregable_id')
    mes = request.POST.get('mes')
    anio = request.POST.get('anio')
    archivo = request.FILES.get('archivo')

    if not tipo_id or not anio or not archivo:
        return JsonResponse({'status': 'error', 'message': 'Faltan datos requeridos.'}, status=400)

    try:
        anio = int(anio)
    except (ValueError, TypeError):
        return JsonResponse({'status': 'error', 'message': 'Año inválido.'}, status=400)

    tipo = get_object_or_404(TipoEntregable, pk=tipo_id)
    config = get_object_or_404(EntregableContratista, empresa=empresa, tipo_entregable=tipo, activo=True)

    try:
        mes_val = int(mes) if mes else None
    except (ValueError, TypeError):
        mes_val = None

    doc, created = DocumentoEntregable.objects.update_or_create(
        empresa=empresa,
        tipo_entregable=tipo,
        mes=mes_val,
        anio=anio,
        defaults={
            'archivo': archivo,
            'subido_por': request.user,
            'es_valido': True,
        }
    )
    return JsonResponse({
        'status': 'success',
        'message': 'Documento subido correctamente.',
        'documento': {
            'id': doc.id,
            'nombre': doc.archivo.name.split('/')[-1],
            'url': doc.archivo.url,
            'tipo': doc.tipo_entregable.nombre,
            'mes': doc.mes,
        }
    })


@contratista_required
@require_POST
def eliminar_entregable(request, doc_id):
    empresa = get_empresa(request)
    doc = get_object_or_404(DocumentoEntregable, pk=doc_id, empresa=empresa)
    doc.archivo.delete(save=False)
    doc.delete()
    return JsonResponse({'status': 'success', 'message': 'Documento eliminado.'})


@contratista_required
@require_POST
def enviar_expediente(request, mes, anio):
    empresa = get_empresa(request)
    expediente_obj = get_object_or_404(ExpedienteMensual, empresa=empresa, mes=mes, anio=anio)
    if expediente_obj.estado == 'BORRADOR':
        expediente_obj.estado = 'ENVIADO'
        expediente_obj.fecha_envio = timezone.now()
        expediente_obj.save()
        notificar_a_grupo(
            grupo_nombre='Administradores',
            titulo="Expediente Mensual Enviado",
            mensaje=f"{empresa.nombre} ha enviado el expediente de {mes}/{anio} para revisión.",
            tipo='INFO',
            modulo='PORTAL_SUB',
            enlace=f"/admin/portalsub/expedientemensual/",
            icono='document-text-outline',
        )
    return redirect('portalsub:expediente', mes=mes, anio=anio)


@contratista_required
def personal_list(request):
    empresa = get_empresa(request)
    today = date.today()
    personal = TecnicoPuesto.objects.filter(empresa=empresa).order_by('-esta_vigente', 'apellido', 'nombre')

    altas = personal.filter(
        fecha_alta__year=today.year, fecha_alta__month=today.month
    ).order_by('-fecha_alta')

    bajas = HistorialPersonal.objects.filter(
        tecnico__empresa=empresa, tipo='BAJA',
        fecha__year=today.year, fecha__month=today.month
    ).select_related('tecnico').order_by('-fecha')

    return render(request, 'portalsub/personal_list.html', {
        'active_tab': 'personal',
        'empresa': empresa,
        'personal': personal,
        'total': personal.count(),
        'vigentes': personal.filter(esta_vigente=True).count(),
        'altas': altas,
        'bajas': bajas,
        'total_tipos_doc': TipoDocumentoPersonal.objects.filter(activo=True).count(),
    })


@contratista_required
def personal_crear(request):
    empresa = get_empresa(request)
    puestos = PuestoTrabajo.objects.all().order_by('nombre')
    error = None
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        apellido = request.POST.get('apellido', '').strip()
        dni = request.POST.get('dni', '').strip()
        fecha_nacimiento = request.POST.get('fecha_nacimiento') or None
        tipo_sangre = request.POST.get('tipo_sangre', '').strip()
        fecha_alta = request.POST.get('fecha_alta') or None
        telefono = request.POST.get('telefono', '').strip()
        telefono_emergencia = request.POST.get('telefono_emergencia', '').strip()
        puesto_id = request.POST.get('puesto_id')
        foto = request.FILES.get('foto')

        if not nombre or not apellido:
            error = 'Nombre y apellido son obligatorios.'
        else:
            empleado = TecnicoPuesto.objects.create(
                empresa=empresa,
                nombre=nombre,
                apellido=apellido,
                dni=dni or None,
                fecha_nacimiento=fecha_nacimiento,
                tipo_sangre=tipo_sangre or None,
                fecha_alta=fecha_alta,
                telefono=telefono or None,
                telefono_emergencia=telefono_emergencia or None,
                puesto_id=puesto_id or None,
                foto=foto,
                disponible=True,
                esta_vigente=True,
            )
            HistorialPersonal.objects.create(
                tecnico=empleado, tipo='ALTA', usuario=request.user,
                detalle=f'Alta registrada por {request.user.get_full_name() or request.user.username}'
            )
            return redirect('portalsub:personal_detalle', pk=empleado.id)

    return render(request, 'portalsub/personal_form.html', {
        'active_tab': 'personal',
        'empresa': empresa,
        'puestos': puestos,
        'accion': 'Agregar',
        'error': error,
    })


@contratista_required
def personal_editar(request, pk):
    empresa = get_empresa(request)
    empleado = get_object_or_404(TecnicoPuesto, pk=pk, empresa=empresa)
    puestos = PuestoTrabajo.objects.all().order_by('nombre')
    error = None

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        apellido = request.POST.get('apellido', '').strip()
        dni = request.POST.get('dni', '').strip()
        fecha_nacimiento = request.POST.get('fecha_nacimiento') or None
        tipo_sangre = request.POST.get('tipo_sangre', '').strip()
        fecha_alta = request.POST.get('fecha_alta') or None
        telefono = request.POST.get('telefono', '').strip()
        telefono_emergencia = request.POST.get('telefono_emergencia', '').strip()
        puesto_id = request.POST.get('puesto_id')
        foto = request.FILES.get('foto')
        esta_vigente = request.POST.get('esta_vigente') == 'on'

        if not nombre or not apellido:
            error = 'Nombre y apellido son obligatorios.'
        else:
            empleado.nombre = nombre
            empleado.apellido = apellido
            empleado.dni = dni or None
            empleado.fecha_nacimiento = fecha_nacimiento
            empleado.tipo_sangre = tipo_sangre or None
            empleado.fecha_alta = fecha_alta
            empleado.telefono = telefono or None
            empleado.telefono_emergencia = telefono_emergencia or None
            old_vigente = empleado.esta_vigente
            old_puesto = empleado.puesto_id
            empleado.puesto_id = puesto_id or None
            if foto:
                empleado.foto = foto
            empleado.esta_vigente = esta_vigente
            empleado.save()

            if old_vigente != esta_vigente:
                if esta_vigente:
                    HistorialPersonal.objects.create(
                        tecnico=empleado, tipo='REINGRESO', usuario=request.user,
                        detalle='Cambió de No Vigente a Vigente'
                    )
                else:
                    HistorialPersonal.objects.create(
                        tecnico=empleado, tipo='BAJA', usuario=request.user,
                        detalle='Cambió de Vigente a No Vigente'
                    )
            if old_puesto != empleado.puesto_id:
                HistorialPersonal.objects.create(
                    tecnico=empleado, tipo='CAMBIO_PUESTO', usuario=request.user,
                    detalle=f'Puesto anterior ID {old_puesto} → nuevo ID {empleado.puesto_id}'
                )
            return redirect('portalsub:personal_detalle', pk=empleado.id)

    return render(request, 'portalsub/personal_form.html', {
        'active_tab': 'personal',
        'empresa': empresa,
        'empleado': empleado,
        'puestos': puestos,
        'accion': 'Editar',
        'error': error,
    })


@contratista_required
@require_POST
def personal_eliminar(request, pk):
    empresa = get_empresa(request)
    empleado = get_object_or_404(TecnicoPuesto, pk=pk, empresa=empresa)
    HistorialPersonal.objects.create(
        tecnico=empleado, tipo='BAJA', usuario=request.user,
        detalle=f'Eliminado por {request.user.get_full_name() or request.user.username}'
    )
    empleado.delete()
    return JsonResponse({'status': 'success', 'message': 'Empleado eliminado.'})


@contratista_required
def reporte_altas_bajas(request):
    empresa = get_empresa(request)
    today = date.today()
    altas = TecnicoPuesto.objects.filter(
        empresa=empresa, fecha_alta__year=today.year, fecha_alta__month=today.month
    ).order_by('-fecha_alta')
    bajas = HistorialPersonal.objects.filter(
        tecnico__empresa=empresa, tipo='BAJA',
        fecha__year=today.year, fecha__month=today.month
    ).select_related('tecnico').order_by('-fecha')
    return render(request, 'portalsub/reporte_altas_bajas.html', {
        'empresa': empresa,
        'altas': altas,
        'bajas': bajas,
        'today': timezone.now(),
    })


@contratista_required
def personal_detalle(request, pk):
    empresa = get_empresa(request)
    empleado = get_object_or_404(TecnicoPuesto, pk=pk, empresa=empresa)
    documentos = DocumentoPersonal.objects.filter(tecnico=empleado).select_related('tipo')
    tipos_doc = TipoDocumentoPersonal.objects.filter(activo=True)

    docs_status = {}
    for t in tipos_doc:
        docs_status[t.id] = {
            'label': t.nombre,
            'documento': documentos.filter(tipo=t).first(),
        }

    historial = HistorialPersonal.objects.filter(tecnico=empleado)[:20]

    return render(request, 'portalsub/personal_detalle.html', {
        'active_tab': 'personal',
        'empresa': empresa,
        'empleado': empleado,
        'docs_status': docs_status,
        'documentos': documentos,
        'historial': historial,
        'tipos_doc': tipos_doc,
    })


@contratista_required
@require_POST
def subir_documento_personal(request, pk):
    empresa = get_empresa(request)
    empleado = get_object_or_404(TecnicoPuesto, pk=pk, empresa=empresa)
    tipo_id = request.POST.get('tipo')
    archivo = request.FILES.get('archivo')

    if not tipo_id or not archivo:
        return JsonResponse({'status': 'error', 'message': 'Faltan datos requeridos.'}, status=400)

    tipo = get_object_or_404(TipoDocumentoPersonal, pk=tipo_id, activo=True)

    doc, created = DocumentoPersonal.objects.update_or_create(
        tecnico=empleado,
        tipo=tipo,
        defaults={
            'archivo': archivo,
            'subido_por': request.user,
            'es_valido': True,
        }
    )
    accion = 'Subió' if created else 'Reemplazó'
    HistorialPersonal.objects.create(
        tecnico=empleado, tipo='DOCUMENTO', usuario=request.user,
        detalle=f'{accion}: {tipo.nombre}'
    )
    return JsonResponse({
        'status': 'success',
        'message': 'Documento subido correctamente.',
        'documento': {
            'id': doc.id,
            'tipo': tipo.nombre,
            'nombre': doc.archivo.name.split('/')[-1],
            'url': doc.archivo.url,
        }
    })


@contratista_required
@require_POST
def eliminar_documento_personal(request, pk, doc_id):
    empresa = get_empresa(request)
    empleado = get_object_or_404(TecnicoPuesto, pk=pk, empresa=empresa)
    doc = get_object_or_404(DocumentoPersonal, pk=doc_id, tecnico=empleado)
    doc.archivo.delete(save=False)
    doc.delete()
    return JsonResponse({'status': 'success', 'message': 'Documento eliminado.'})


@contratista_required
def ordenes_list(request):
    empresa = get_empresa(request)
    estado = request.GET.get('estado', '')

    ordenes = OrdenCompra.objects.filter(proveedor=empresa).order_by('-fecha_creacion')
    if estado:
        ordenes = ordenes.filter(estado=estado)

    estados_oc = OrdenCompra.ESTADO_OC_CHOICES
    return render(request, 'portalsub/ordenes_list.html', {
        'active_tab': 'ordenes',
        'empresa': empresa,
        'ordenes': ordenes,
        'estados_oc': estados_oc,
        'filtro_estado': estado,
    })


@contratista_required
def orden_detalle(request, oc_id):
    empresa = get_empresa(request)
    oc = get_object_or_404(OrdenCompra, pk=oc_id, proveedor=empresa)
    documentos = DocumentoOrdenCompra.objects.filter(orden_compra=oc).order_by('tipo')
    puede_subir = oc.estado in ('CONFIRMADA', 'RECIBIDA')

    documentos_dict = {doc.tipo: doc for doc in documentos}

    tipos_doc = DocumentoOrdenCompra.TIPO_DOC_CHOICES
    context = {
        'active_tab': 'ordenes',
        'empresa': empresa,
        'oc': oc,
        'documentos': documentos,
        'documentos_dict': documentos_dict,
        'puede_subir': puede_subir,
        'tipos_doc': tipos_doc,
    }
    return render(request, 'portalsub/orden_detalle.html', context)


@contratista_required
@require_POST
def subir_documento_oc(request, oc_id):
    empresa = get_empresa(request)
    oc = get_object_or_404(OrdenCompra, pk=oc_id, proveedor=empresa)

    if oc.estado not in ('CONFIRMADA', 'RECIBIDA'):
        return JsonResponse({'status': 'error', 'message': 'No se pueden subir documentos en este estado.'}, status=400)

    tipo = request.POST.get('tipo')
    archivo = request.FILES.get('archivo')
    descripcion = request.POST.get('descripcion', '')

    if not tipo or not archivo:
        return JsonResponse({'status': 'error', 'message': 'Faltan datos requeridos.'}, status=400)

    if tipo not in dict(DocumentoOrdenCompra.TIPO_DOC_CHOICES):
        return JsonResponse({'status': 'error', 'message': 'Tipo de documento inválido.'}, status=400)

    doc = DocumentoOrdenCompra.objects.create(
        orden_compra=oc,
        tipo=tipo,
        archivo=archivo,
        descripcion=descripcion,
        subido_por=request.user,
        es_valido=True,
    )
    notificar_a_grupo(
        grupo_nombre='Administradores',
        titulo="Documento de OC Subido",
        mensaje=f"{empresa.nombre} subió un documento {doc.get_tipo_display()} a la OC {oc.numero_oc}.",
        tipo='INFO',
        modulo='PORTAL_SUB',
        enlace=f"/presupuestos/ordenes-compra/{oc.id}/detalle/",
        icono='cloud-upload-outline',
    )
    return JsonResponse({
        'status': 'success',
        'message': 'Documento subido correctamente.',
        'documento': {
            'id': doc.id,
            'tipo': doc.get_tipo_display(),
            'nombre': doc.archivo.name.split('/')[-1],
            'url': doc.archivo.url,
            'descripcion': doc.descripcion or '',
            'creado_en': doc.creado_en.strftime('%d/%m/%Y %H:%M'),
        }
    })


@contratista_required
@require_POST
def eliminar_documento_oc(request, oc_id, doc_id):
    empresa = get_empresa(request)
    oc = get_object_or_404(OrdenCompra, pk=oc_id, proveedor=empresa)
    doc = get_object_or_404(DocumentoOrdenCompra, pk=doc_id, orden_compra=oc)
    doc.archivo.delete(save=False)
    doc.delete()
    return JsonResponse({'status': 'success', 'message': 'Documento eliminado.'})
