from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User, Group
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db import models
from django.utils import timezone
from django.contrib import messages
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
        if a.completado:
            completados.append(item)
        else:
            en_curso.append(item)

    # Cursos disponibles para todos (sin asignación)
    disponibles = Curso.objects.filter(
        activo=True, disponible_para_todos=True
    ).exclude(
        pk__in=[a.curso_id for a in asignaciones]
    )

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
    total_asignados = len(completados) + len(en_curso)

    return render(request, 'courses/lista.html', {
        'en_curso': en_curso,
        'completados': completados,
        'disponibles': disponibles,
        'tiempo_total_segundos': tiempo_total_segundos,
        'tiempo_total_formateado': total_formateado,
        'total_asignados': total_asignados,
        'tiempo_por_curso': tiempo_por_curso,
    })


@login_required
def detalle_curso(request, pk):
    curso = get_object_or_404(Curso, pk=pk, activo=True)
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
    cursos = Curso.objects.all().order_by('-creado_en')
    data = []
    for c in cursos:
        data.append({
            'curso': c,
            'secciones': c.total_secciones(),
            'asignados': c.asignaciones.count(),
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
