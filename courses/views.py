import os
import re
import zipfile
import xml.etree.ElementTree as ET
from io import BytesIO
from pathlib import Path

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User, Group
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.db import models
from django.utils import timezone
from django.contrib import messages
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from .models import Curso, AsignacionCurso, ProgresoSeccion, Seccion, Pagina, RegistroTiempo
from .forms import CursoForm, SeccionFormSet


@login_required
def lista_cursos(request):
    asignaciones_qs = AsignacionCurso.objects.filter(
        models.Q(usuario=request.user) | models.Q(grupo__user=request.user)
    ).select_related('curso')
    vistos = set()
    asignaciones = []
    for a in asignaciones_qs:
        if a.curso_id not in vistos:
            vistos.add(a.curso_id)
            asignaciones.append(a)

    completados = []
    en_curso = []
    pensum_data = {}
    for a in asignaciones:
        total = a.curso.total_secciones()
        completadas = ProgresoSeccion.objects.filter(
            asignacion=a, usuario=request.user, completado=True
        ).count()
        pct = int((completadas / total * 100)) if total else 0
        item = {
            'asignacion': a,
            'progreso': pct,
            'completadas': completadas,
            'total': total,
        }
        padre = a.curso.padre
        if padre:
            if padre.pk not in pensum_data:
                pensum_data[padre.pk] = {
                    'curso': padre,
                    'hijos_en_curso': [],
                    'hijos_completados': [],
                    'hijos_disponibles': [],
                }
            if a.completado:
                pensum_data[padre.pk]['hijos_completados'].append(item)
            else:
                pensum_data[padre.pk]['hijos_en_curso'].append(item)
        else:
            if a.completado:
                completados.append(item)
            else:
                en_curso.append(item)

    # Cursos disponibles para todos (sin asignación)
    disponibles_qs = Curso.objects.filter(
        activo=True, disponible_para_todos=True
    ).exclude(
        pk__in=[a.curso_id for a in asignaciones]
    )
    disponibles = []
    pensum_disponibles = {}
    for c in disponibles_qs:
        item = c
        padre = c.padre
        if padre:
            if padre.pk not in pensum_disponibles:
                pensum_disponibles[padre.pk] = {
                    'curso': padre,
                    'hijos': [],
                }
            pensum_disponibles[padre.pk]['hijos'].append(item)
        else:
            disponibles.append(item)

    # Merge pensum data
    todos_pensum = {}
    for pk, data in pensum_data.items():
        todos_pensum[pk] = data
    for pk, data in pensum_disponibles.items():
        if pk in todos_pensum:
            todos_pensum[pk].setdefault('hijos_disponibles', []).extend(data['hijos'])
        else:
            todos_pensum[pk] = data

    # Calcular estadísticas de tiempo
    tiempos = RegistroTiempo.objects.filter(usuario=request.user)
    tiempo_total_segundos = tiempos.aggregate(total=models.Sum('duracion_segundos'))['total'] or 0

    def fmt_seg(s):
        s = int(s or 0)
        if s >= 3600:
            return f"{s // 3600}h {(s % 3600) // 60}m"
        if s >= 60:
            return f"{s // 60}m {s % 60}s"
        return f"{s}s"

    tiempo_por_curso = {}
    for t in tiempos.values('curso__titulo', 'curso_id').annotate(
        total=models.Sum('duracion_segundos')
    ):
        segs = t['total'] or 0
        tiempo_por_curso[t['curso_id']] = {
            'titulo': t['curso__titulo'],
            'segundos': segs,
            'formateado': fmt_seg(segs),
        }

    total_formateado = fmt_seg(tiempo_total_segundos)
    total_asignados = len(completados) + len(en_curso) + sum(
        len(d.get('hijos_en_curso', []) + d.get('hijos_completados', []))
        for d in todos_pensum.values()
    )

    return render(request, 'courses/lista.html', {
        'en_curso': en_curso,
        'completados': completados,
        'disponibles': disponibles,
        'pensums': todos_pensum.values(),
        'tiempo_total_segundos': tiempo_total_segundos,
        'tiempo_total_formateado': total_formateado,
        'total_asignados': total_asignados,
        'tiempo_por_curso': tiempo_por_curso,
    })


@login_required
def detalle_curso(request, pk):
    curso = get_object_or_404(Curso, pk=pk, activo=True)

    # Si es un pensum, mostrar los cursos hijos
    hijos = curso.hijos.filter(activo=True).order_by('orden')
    if hijos.exists():
        hijos_con_asignacion = []
        total_hijos = hijos.count()
        completados_hijos = 0
        for h in hijos:
            asig = AsignacionCurso.objects.filter(
                models.Q(usuario=request.user) | models.Q(grupo__user=request.user),
                curso=h
            ).first()
            if not asig and h.disponible_para_todos:
                asig = AsignacionCurso.objects.create(curso=h, usuario=request.user)
            if asig and asig.completado:
                completados_hijos += 1
            hijos_con_asignacion.append({'curso': h, 'asignacion': asig})

        pct_pensum = int((completados_hijos / total_hijos * 100)) if total_hijos else 0

        return render(request, 'courses/detalle_pensum.html', {
            'curso': curso,
            'hijos': hijos_con_asignacion,
            'total_hijos': total_hijos,
            'completados_hijos': completados_hijos,
            'pct_pensum': pct_pensum,
        })

    asignacion = AsignacionCurso.objects.filter(
        models.Q(usuario=request.user) | models.Q(grupo__user=request.user),
        curso=curso
    ).select_related('curso').first()

    if not asignacion:
        if curso.disponible_para_todos:
            asignacion = AsignacionCurso.objects.create(
                curso=curso, usuario=request.user
            )
        else:
            return redirect('courses:lista')

    secciones = curso.secciones.all()
    progresos = {
        p.seccion_id: p
        for p in ProgresoSeccion.objects.filter(asignacion=asignacion, usuario=request.user)
    }

    total = secciones.count()
    completadas = sum(1 for s in secciones if progresos.get(s.id) and progresos[s.id].completado)
    pct = int((completadas / total * 100)) if total else 0

    secciones_data = []
    for s in secciones:
        prog = progresos.get(s.id)
        paginas = s.paginas.all()
        secciones_data.append({
            'seccion': s,
            'completado': prog.completado if prog else False,
            'completado_en': prog.completado_en if prog else None,
            'paginas': paginas,
        })

    return render(request, 'courses/detalle.html', {
        'curso': curso,
        'asignacion': asignacion,
        'secciones': secciones_data,
        'progreso': pct,
        'completadas': completadas,
        'total': total,
    })


@login_required
@require_POST
def marcar_completada(request, pk, seccion_id):
    curso = get_object_or_404(Curso, pk=pk, activo=True)
    seccion = get_object_or_404(Seccion, pk=seccion_id, curso=curso)
    asignacion = AsignacionCurso.objects.filter(
        models.Q(usuario=request.user) | models.Q(grupo__user=request.user),
        curso=curso
    ).first()

    if not asignacion:
        return JsonResponse({'error': 'No asignado'}, status=403)

    progreso, created = ProgresoSeccion.objects.get_or_create(
        asignacion=asignacion,
        seccion=seccion,
        usuario=request.user,
        defaults={'completado': True, 'completado_en': timezone.now()}
    )
    if not progreso.completado:
        progreso.completado = True
        progreso.completado_en = timezone.now()
        progreso.save()

    total = curso.total_secciones()
    completadas = ProgresoSeccion.objects.filter(
        asignacion=asignacion, usuario=request.user, completado=True
    ).count()
    pct = int((completadas / total * 100)) if total else 0

    if completadas >= total:
        asignacion.completado = True
        asignacion.fecha_completado = timezone.now()
        asignacion.save()

    return JsonResponse({
        'success': True,
        'progreso': pct,
        'completadas': completadas,
        'total': total,
        'curso_completado': completadas >= total,
    })


@staff_member_required
def lista_admin(request):
    padres = Curso.objects.filter(padre=None).order_by('-creado_en')
    data = []
    for p in padres:
        hijos = []
        for h in p.hijos.all().order_by('orden'):
            hijos.append({
                'curso': h,
                'secciones': h.total_secciones(),
                'asignados': h.asignaciones.count(),
            })
        data.append({
            'curso': p,
            'secciones': p.total_secciones(),
            'asignados': p.asignaciones.count(),
            'hijos': hijos,
        })
    return render(request, 'courses/admin_lista.html', {
        'cursos': data,
    })


@staff_member_required
@require_POST
def upload_image(request, pk=None):
    file = request.FILES.get('file')
    if not file:
        return JsonResponse({'error': 'No se recibió archivo'}, status=400)
    from django.core.files.storage import default_storage
    import uuid, os
    ext = os.path.splitext(file.name)[1]
    filename = f'uploads/{uuid.uuid4()}{ext}'
    path = default_storage.save(filename, file)
    url = default_storage.url(path)
    return JsonResponse({'url': url, 'filename': file.name})


@staff_member_required
def gestionar_pagina(request, curso_id, seccion_id, pagina_id=None):
    seccion = get_object_or_404(Seccion, pk=seccion_id, curso_id=curso_id)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'eliminar':
            pagina = get_object_or_404(Pagina, pk=pagina_id, seccion=seccion)
            pagina.delete()
            return JsonResponse({'ok': True})

        titulo = request.POST.get('titulo', '').strip() or 'Nueva página'
        contenido = request.POST.get('contenido_html', '')
        duracion = int(request.POST.get('duracion_minutos', 0) or 0)
        obligatorio = request.POST.get('obligatorio') == 'on'

        if action == 'crear':
            orden = seccion.paginas.count() + 1
            pagina = Pagina.objects.create(
                seccion=seccion, titulo=titulo,
                contenido_html=contenido,
                duracion_minutos=duracion, obligatorio=obligatorio,
                orden=orden
            )
        elif action == 'editar':
            pagina = get_object_or_404(Pagina, pk=pagina_id, seccion=seccion)
            pagina.titulo = titulo
            pagina.contenido_html = contenido
            pagina.duracion_minutos = duracion
            pagina.obligatorio = obligatorio
            pagina.save()

        # Return updated page list HTML
        paginas = seccion.paginas.all().order_by('orden')
        return render(request, 'courses/_paginas_list.html', {
            'curso_id': curso_id,
            'seccion': seccion,
            'paginas': paginas,
        })

    # GET — return page list HTML or single page JSON
    if not pagina_id:
        paginas = seccion.paginas.all().order_by('orden')
        return render(request, 'courses/_paginas_list.html', {
            'curso_id': curso_id,
            'seccion': seccion,
            'paginas': paginas,
        })

    pagina = get_object_or_404(Pagina, pk=pagina_id, seccion=seccion)
    return JsonResponse({
        'id': pagina.id,
        'titulo': pagina.titulo,
        'contenido_html': pagina.contenido_html,
        'duracion_minutos': pagina.duracion_minutos,
        'obligatorio': pagina.obligatorio,
    })


@staff_member_required
def editar_curso(request, pk=None):
    curso = get_object_or_404(Curso, pk=pk) if pk else None
    es_nuevo = curso is None

    if request.method == 'POST':
        form = CursoForm(request.POST, request.FILES, instance=curso)
        formset = SeccionFormSet(request.POST, instance=curso)

        if form.is_valid() and formset.is_valid():
            curso = form.save()
            formset.instance = curso
            formset.save()
            messages.success(request, 'Curso guardado exitosamente.')
            return redirect('courses:editar_curso', pk=curso.pk)
        else:
            for error in formset.non_form_errors():
                messages.error(request, f'Error en secciones: {error}')
            for f_idx, f_errors in enumerate(formset.errors):
                for field, err_list in f_errors.items():
                    for err in err_list:
                        messages.error(request, f'Sección {f_idx + 1}, campo "{field}": {err}')
            for field, err_list in form.errors.items():
                for err in err_list:
                    messages.error(request, f'Curso, campo "{field}": {err}')
    else:
        form = CursoForm(instance=curso)
        formset = SeccionFormSet(instance=curso)

    return render(request, 'courses/editor.html', {
        'form': form,
        'formset': formset,
        'curso': curso,
        'es_nuevo': es_nuevo,
    })


@staff_member_required
def visualizar_curso(request, pk):
    curso = get_object_or_404(Curso, pk=pk)

    # Si es pensum, mostrar hijos
    hijos = curso.hijos.filter(activo=True).order_by('orden')
    if hijos.exists():
        hijos_data = []
        total_hijos = hijos.count()
        completados_hijos = 0
        for h in hijos:
            asig, _ = AsignacionCurso.objects.get_or_create(
                curso=h, usuario=request.user,
                defaults={'asignado_por': request.user}
            )
            if asig.completado:
                completados_hijos += 1
            hijos_data.append({'curso': h, 'asignacion': asig})
        pct_pensum = int((completados_hijos / total_hijos * 100)) if total_hijos else 0
        return render(request, 'courses/visualizador_pensum.html', {
            'curso': curso,
            'hijos': hijos_data,
            'total_hijos': total_hijos,
            'completados_hijos': completados_hijos,
            'pct_pensum': pct_pensum,
        })

    secciones = curso.secciones.all()
    total = secciones.count()
    duracion = curso.duracion_estimada()

    # Auto-crear asignaci�n para staff que visualiza
    asignacion, _ = AsignacionCurso.objects.get_or_create(
        curso=curso, usuario=request.user,
        defaults={'asignado_por': request.user}
    )

    progresos = {
        p.seccion_id: p
        for p in ProgresoSeccion.objects.filter(asignacion=asignacion, usuario=request.user)
    }
    completadas = sum(1 for s in secciones if progresos.get(s.id) and progresos[s.id].completado)
    pct = int((completadas / total * 100)) if total else 0

    secciones_data = []
    for s in secciones:
        prog = progresos.get(s.id)
        paginas = s.paginas.all()
        secciones_data.append({
            'seccion': s,
            'completado': prog.completado if prog else False,
            'completado_en': prog.completado_en if prog else None,
            'paginas': paginas,
        })

    return render(request, 'courses/visualizador.html', {
        'curso': curso,
        'secciones': secciones_data,
        'total': total,
        'duracion': duracion,
        'completadas': completadas,
        'progreso': pct,
    })


@staff_member_required
def asignar_curso(request, pk):
    curso = get_object_or_404(Curso, pk=pk)
    asignaciones = AsignacionCurso.objects.filter(curso=curso).select_related('usuario', 'grupo')

    if request.method == 'POST':
        usuario_id = request.POST.get('usuario')
        grupo_id = request.POST.get('grupo')
        fecha_v = request.POST.get('fecha_vencimiento')
        if fecha_v:
            from datetime import datetime
            fecha_v = timezone.make_aware(datetime.strptime(fecha_v, '%Y-%m-%d'))
        else:
            fecha_v = None

        try:
            if usuario_id:
                user = User.objects.get(pk=usuario_id)
                AsignacionCurso.objects.get_or_create(
                    curso=curso, usuario=user,
                    defaults={'asignado_por': request.user, 'fecha_vencimiento': fecha_v}
                )
            if grupo_id:
                group = Group.objects.get(pk=grupo_id)
                AsignacionCurso.objects.get_or_create(
                    curso=curso, grupo=group,
                    defaults={'asignado_por': request.user, 'fecha_vencimiento': fecha_v}
                )
            messages.success(request, 'Asignación guardada.')
        except Exception as e:
            messages.error(request, f'Error: {e}')

        return redirect('courses:asignar_curso', pk=curso.pk)

    return render(request, 'courses/asignar.html', {
        'curso': curso,
        'asignaciones': asignaciones,
        'usuarios': User.objects.filter(is_active=True).order_by('username'),
        'grupos': Group.objects.all().order_by('name'),
        'now': timezone.now(),
    })


@staff_member_required
@require_POST
def desasignar_curso(request, pk, asignacion_id):
    asignacion = get_object_or_404(AsignacionCurso, pk=asignacion_id, curso_id=pk)
    asignacion.delete()
    messages.success(request, 'Asignación eliminada.')
    return redirect('courses:asignar_curso', pk=pk)


@login_required
@require_POST
def heartbeat_curso(request, pk):
    curso = get_object_or_404(Curso, pk=pk)
    if not AsignacionCurso.objects.filter(
        models.Q(usuario=request.user) | models.Q(grupo__user=request.user),
        curso=curso
    ).exists():
        return JsonResponse({'error': 'No asignado'}, status=403)
    action = request.POST.get('action', 'tick')
    hoy = timezone.now().date()
    registro, created = RegistroTiempo.objects.get_or_create(
        usuario=request.user,
        curso=curso,
        inicio__date=hoy,
        defaults={'inicio': timezone.now()}
    )
    if action == 'tick':
        segundos = int(request.POST.get('seconds', 30))
        registro.duracion_segundos += segundos
        registro.fin = timezone.now()
        registro.save()
    elif action == 'start' and created:
        pass
    return JsonResponse({'ok': True})


@login_required
def certificado_curso(request, pk):
    curso = get_object_or_404(Curso, pk=pk, activo=True)
    asignacion = AsignacionCurso.objects.filter(
        models.Q(usuario=request.user) | models.Q(grupo__user=request.user),
        curso=curso, completado=True
    ).select_related('curso').first()

    if not asignacion:
        messages.error(request, 'Debes completar el curso para obtener el certificado.')
        return redirect('courses:detalle', pk=pk)

    total = curso.total_secciones()
    completadas = ProgresoSeccion.objects.filter(
        asignacion=asignacion, usuario=request.user, completado=True
    ).count()

    return render(request, 'courses/certificado.html', {
        'curso': curso,
        'usuario': request.user,
        'fecha': asignacion.fecha_completado or timezone.now(),
        'completadas': completadas,
        'total': total,
    })


@staff_member_required
def estadisticas_curso(request, pk):
    curso = get_object_or_404(Curso, pk=pk)
    asignaciones = AsignacionCurso.objects.filter(curso=curso).select_related('usuario', 'grupo')

    # --- Inscritos ---
    usuarios_inscritos = set()
    for a in asignaciones:
        for u in a.usuarios_destino():
            usuarios_inscritos.add(u)
    usuarios_inscritos = sorted(usuarios_inscritos, key=lambda u: u.get_full_name() or u.username)
    total_inscritos = len(usuarios_inscritos)

    # --- Completados ---
    completados = [a for a in asignaciones if a.completado]
    usuarios_completaron = set()
    for a in completados:
        for u in a.usuarios_destino():
            usuarios_completaron.add(u)
    usuarios_completaron = sorted(usuarios_completaron, key=lambda u: u.get_full_name() or u.username)
    total_completados = len(usuarios_completaron)

    # --- Tiempo promedio de finalización ---
    tiempos_completacion = []
    for a in completados:
        if a.fecha_asignacion and a.fecha_completado:
            delta = a.fecha_completado - a.fecha_asignacion
            tiempos_completacion.append(delta.total_seconds())
    if tiempos_completacion:
        prom_segundos = sum(tiempos_completacion) / len(tiempos_completacion)
        if prom_segundos >= 86400:
            tiempo_promedio = f"{int(prom_segundos // 86400)}d {int((prom_segundos % 86400) // 3600)}h"
        elif prom_segundos >= 3600:
            tiempo_promedio = f"{int(prom_segundos // 3600)}h {int((prom_segundos % 3600) // 60)}m"
        else:
            tiempo_promedio = f"{int(prom_segundos // 60)}m"
    else:
        tiempo_promedio = "—"

    # --- Tiempo total de estudio ---
    tiempos = RegistroTiempo.objects.filter(curso=curso)
    tiempo_total_segundos = tiempos.aggregate(total=models.Sum('duracion_segundos'))['total'] or 0
    if tiempo_total_segundos >= 3600:
        tiempo_total = f"{tiempo_total_segundos // 3600}h {(tiempo_total_segundos % 3600) // 60}m"
    else:
        tiempo_total = f"{tiempo_total_segundos // 60}m"

    # --- Progreso promedio ---
    progresos = []
    for a in asignaciones:
        for u in a.usuarios_destino():
            pct = a.progreso_porcentaje(u)
            progresos.append(pct)
    progreso_promedio = int(sum(progresos) / len(progresos)) if progresos else 0

    return render(request, 'courses/estadisticas.html', {
        'curso': curso,
        'total_inscritos': total_inscritos,
        'usuarios_inscritos': usuarios_inscritos,
        'total_completados': total_completados,
        'usuarios_completaron': usuarios_completaron,
        'tiempo_promedio': tiempo_promedio,
        'tiempo_total': tiempo_total,
        'progreso_promedio': progreso_promedio,
        'total_asignaciones': asignaciones.count(),
    })


@staff_member_required
@require_POST
def importar_scorm(request, pk):
    curso = get_object_or_404(Curso, pk=pk)
    archivo = request.FILES.get('file')
    if not archivo or not archivo.name.lower().endswith('.zip'):
        return JsonResponse({'error': 'Debe subir un archivo ZIP de SCORM'}, status=400)

    try:
        with zipfile.ZipFile(archivo, 'r') as zf:
            names = zf.namelist()

            if 'imsmanifest.xml' not in names:
                return JsonResponse({'error': 'El ZIP no contiene imsmanifest.xml'}, status=400)

            # Parse manifest
            manifest_xml = zf.read('imsmanifest.xml')
            root = ET.fromstring(manifest_xml)
            ns = {
                'adlcp': 'http://www.adlnet.org/xsd/adlcp_rootv1p2',
                'imscp': 'http://www.imsproject.org/xsd/imscp_rootv1p1p2',
                'imsmd': 'http://www.imsglobal.org/xsd/imsmd_rootv1p2p1',
            }
            # Try to detect namespaces from the XML
            ns_map = {}
            for event, elem in ET.iterparse(BytesIO(manifest_xml), events=('start-ns',)):
                prefix, uri = elem
                if prefix:
                    ns_map[uri] = prefix

            def ns_tag(tag):
                for uri, prefix in ns_map.items():
                    if tag.startswith('{'):
                        return tag
                return tag

            # Extract organization title
            orgs = root.findall('.//{http://www.imsproject.org/xsd/imscp_rootv1p1p2}organization')
            if not orgs:
                orgs = root.findall('.//organization')
            if not orgs:
                # Try any namespace
                for el in root.iter():
                    if el.tag.endswith('organization'):
                        orgs = [el]
                        break

            # Extract items recursively
            def extract_items(parent_elem, parent_section=None):
                items = []
                for child in parent_elem:
                    tag = child.tag
                    if tag.endswith('}item') or tag == 'item':
                        title_el = child.find('{http://www.imsproject.org/xsd/imscp_rootv1p1p2}title')
                        if title_el is None:
                            title_el = child.find('title')
                        title = title_el.text.strip() if title_el is not None and title_el.text else 'Sin título'
                        idref = child.get('identifierref', '')
                        identifier = child.get('identifier', '')
                        sub_items = extract_items(child, parent_section)
                        if sub_items:
                            items.append({
                                'title': title,
                                'idref': '',
                                'identifier': identifier,
                                'children': sub_items,
                                'is_section': True,
                            })
                        else:
                            items.append({
                                'title': title,
                                'idref': idref,
                                'identifier': identifier,
                                'children': [],
                                'is_section': False,
                            })
                return items

            org_title = ''
            items = []
            for org in orgs:
                title_el = org.find('{http://www.imsproject.org/xsd/imscp_rootv1p1p2}title')
                if title_el is None:
                    title_el = org.find('title')
                if title_el is not None and title_el.text:
                    org_title = title_el.text.strip()
                items = extract_items(org)

            if not items:
                return JsonResponse({'error': 'No se encontraron ítems en el manifiesto SCORM'}, status=400)

            # Build resource map: identifier -> href
            resources = root.findall('.//{http://www.imsproject.org/xsd/imscp_rootv1p1p2}resource')
            if not resources:
                resources = root.findall('.//resource')
            if not resources:
                for el in root.iter():
                    if el.tag.endswith('resource'):
                        resources = [el]
                        break
            resource_map = {}
            for res in resources:
                rid = res.get('identifier', '')
                href = res.get('href', '')
                resource_map[rid] = href

            # Extract ZIP to storage
            base_path = f'scorm/course_{curso.pk}/'
            for name in names:
                if name.endswith('/'):
                    continue
                content = zf.read(name)
                dest_path = base_path + name.replace('\\', '/')
                if default_storage.exists(dest_path):
                    default_storage.delete(dest_path)
                default_storage.save(dest_path, ContentFile(content))

            scorm_base_url = default_storage.url(base_path)

            # Create sections and pages
            sec_orden = 0
            total_creados = 0

            # Flatten items: top-level items become sections, children become pages
            def create_content(items_list, parent_section=None):
                nonlocal sec_orden, total_creados
                for item_data in items_list:
                    if item_data['is_section'] or parent_section is None:
                        sec_orden += 1
                        section = Seccion.objects.create(
                            curso=curso,
                            titulo=item_data['title'],
                            orden=sec_orden,
                            contenido_html='',
                            duracion_minutos=0,
                            obligatorio=True,
                        )
                        if item_data['children']:
                            create_content(item_data['children'], section)
                    else:
                        if parent_section:
                            href = resource_map.get(item_data['idref'], '')
                            pag_orden = parent_section.paginas.count() + 1
                            if href:
                                scorm_url = default_storage.url(base_path + href.replace('\\', '/'))
                                contenido = (
                                    f'<div style="width:100%;height:600px;border:1px solid #e2e8f0;border-radius:8px;overflow:hidden;">'
                                    f'<iframe src="{scorm_url}" style="width:100%;height:100%;border:none;" allowfullscreen></iframe>'
                                    f'</div>'
                                )
                            else:
                                contenido = ''
                            Pagina.objects.create(
                                seccion=parent_section,
                                titulo=item_data['title'],
                                orden=pag_orden,
                                contenido_html=contenido,
                                duracion_minutos=0,
                                obligatorio=True,
                            )
                            total_creados += 1

            create_content(items)

            return JsonResponse({
                'success': True,
                'message': f'SCORM importado: {sec_orden} sección(es), {total_creados} página(s) creadas.',
                'secciones': sec_orden,
                'paginas': total_creados,
            })

    except zipfile.BadZipFile:
        return JsonResponse({'error': 'El archivo no es un ZIP válido'}, status=400)
    except ET.ParseError as e:
        return JsonResponse({'error': f'Error al leer imsmanifest.xml: {e}'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Error al importar SCORM: {str(e)}'}, status=400)


@staff_member_required
def servir_scorm(request, pk, subpath):
    curso = get_object_or_404(Curso, pk=pk)
    file_path = f'scorm/course_{curso.pk}/{subpath}'
    if not default_storage.exists(file_path):
        return HttpResponse('Archivo no encontrado', status=404)
    f = default_storage.open(file_path, 'rb')
    content = f.read()
    f.close()

    ext = os.path.splitext(subpath)[1].lower()
    mime_map = {
        '.html': 'text/html',
        '.htm': 'text/html',
        '.js': 'application/javascript',
        '.css': 'text/css',
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.svg': 'image/svg+xml',
        '.json': 'application/json',
        '.xml': 'application/xml',
        '.pdf': 'application/pdf',
        '.mp4': 'video/mp4',
        '.webm': 'video/webm',
        '.mp3': 'audio/mpeg',
        '.woff': 'font/woff',
        '.woff2': 'font/woff2',
        '.ttf': 'font/ttf',
        '.eot': 'application/vnd.ms-fontobject',
    }
    content_type = mime_map.get(ext, 'application/octet-stream')
    return HttpResponse(content, content_type=content_type)
