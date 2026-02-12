from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from .models import Auditoria, ResultadoAuditoria
from activos.models import Ubicacion, Categoria, Activo
from .forms import AuditoriaStep1Form, AuditoriaStep2Form
import json

@login_required
def auditoria_wizard(request):
    step = int(request.GET.get('step', 1))
    
    # Datos guardados en sesión
    session_data = request.session.get('auditoria_wizard_data', {})
    
    if step == 1:
        # Paso 1: Información Básica
        if request.method == 'POST':
            form = AuditoriaStep1Form(request.POST)
            if form.is_valid():
                # Guardar datos en sesión
                session_data['nombre'] = form.cleaned_data['nombre']
                if form.cleaned_data.get('fecha_fin'):
                    session_data['fecha_fin'] = form.cleaned_data['fecha_fin'].isoformat()
                
                request.session['auditoria_wizard_data'] = session_data
                return redirect('/auditorias/nuevo/?step=2')
        else:
            initial = {
                'nombre': session_data.get('nombre', ''),
                'fecha_fin': session_data.get('fecha_fin', '')
            }
            form = AuditoriaStep1Form(initial=initial)
        
        return render(request, 'auditorias/wizard/step1.html', {'form': form, 'step': 1})

    elif step == 2:
        # Paso 2: Alcance (Ubicaciones y Categorías)
        if request.method == 'POST':
            form = AuditoriaStep2Form(request.POST)
            if form.is_valid():
                # Guardar IDs
                session_data['ubicaciones'] = [u.id for u in form.cleaned_data['ubicaciones']]
                session_data['categorias'] = [c.id for c in form.cleaned_data['categorias']]
                
                request.session['auditoria_wizard_data'] = session_data
                return redirect('/auditorias/nuevo/?step=3')
        else:
            initial = {
                'ubicaciones': session_data.get('ubicaciones', []),
                'categorias': session_data.get('categorias', [])
            }
            form = AuditoriaStep2Form(initial=initial)
            
        return render(request, 'auditorias/wizard/step2.html', {'form': form, 'step': 2})

    elif step == 3:
        # Paso 3: Confirmación y Vista Previa
        if request.method == 'POST':
            # Crear Auditoría
            try:
                with transaction.atomic():
                    auditoria = Auditoria.objects.create(
                        nombre=session_data.get('nombre'),
                        fecha_fin=session_data.get('fecha_fin'),
                        creado_por=request.user,
                        estado='BORRADOR'
                    )
                    
                    if session_data.get('ubicaciones'):
                        auditoria.ubicaciones.set(session_data['ubicaciones'])
                    
                    if session_data.get('categorias'):
                        auditoria.categorias.set(session_data['categorias'])
                    
                    assets_query = Activo.objects.all()
                    
                    # Filtrar descendientes de ubicaciones
                    if session_data.get('ubicaciones'):
                        all_loc_ids = set()
                        for uid in session_data['ubicaciones']:
                            u = Ubicacion.objects.filter(id=uid).first()
                            if u:
                                all_loc_ids.update(u.get_descendants(include_self=True).values_list('id', flat=True))
                        assets_query = assets_query.filter(ubicacion_id__in=all_loc_ids)

                    # Filtrar descendientes de categorias
                    if session_data.get('categorias'):
                        all_cat_ids = set()
                        for cid in session_data['categorias']:
                            c = Categoria.objects.filter(id=cid).first()
                            if c:
                                all_cat_ids.update(c.get_descendants(include_self=True).values_list('id', flat=True))
                        assets_query = assets_query.filter(modelo__categoria_id__in=all_cat_ids)
                    
                    # Crear resultados masivos
                    res_objects = []
                    for activo in assets_query:
                        res_objects.append(ResultadoAuditoria(
                            auditoria=auditoria,
                            activo=activo,
                            ubicacion_esperada=activo.ubicacion,
                            estado='PENDIENTE'
                        ))
                    if res_objects:
                        ResultadoAuditoria.objects.bulk_create(res_objects)
                    
                    # Actualizar estado a EN_CURSO pues ya tiene items
                    if res_objects:
                        auditoria.estado = 'EN_CURSO'
                        auditoria.save()
                    
                    del request.session['auditoria_wizard_data']
                    messages.success(request, f"Auditoría '{auditoria.nombre}' creada con {len(res_objects)} activos.")
                    return redirect(f'/auditorias/ejecutar/{auditoria.id}/')
            
            except Exception as e:
                messages.error(request, f"Error al crear la auditoría: {e}")
                return redirect('/auditorias/nuevo/?step=3')

        # Calcular alcance para vista previa
        ubicaciones_ids = session_data.get('ubicaciones', [])
        categorias_ids = session_data.get('categorias', [])
        
        assets_query = Activo.objects.all()
        
        # Filtrar descendientes de ubicaciones
        if ubicaciones_ids:
            all_loc_ids = set()
            for uid in ubicaciones_ids:
                u = Ubicacion.objects.filter(id=uid).first()
                if u:
                    all_loc_ids.update(u.get_descendants(include_self=True).values_list('id', flat=True))
            assets_query = assets_query.filter(ubicacion_id__in=all_loc_ids)

        # Filtrar descendientes de categorias
        if categorias_ids:
            all_cat_ids = set()
            for cid in categorias_ids:
                c = Categoria.objects.filter(id=cid).first()
                if c:
                    all_cat_ids.update(c.get_descendants(include_self=True).values_list('id', flat=True))
            assets_query = assets_query.filter(modelo__categoria_id__in=all_cat_ids)
            
        total_assets = assets_query.count()
        sample_assets = assets_query[:5]
        
        context = {
            'step': 3,
            'nombre': session_data.get('nombre'),
            'total_assets': total_assets,
            'sample_assets': sample_assets,
            'ubicaciones_count': len(ubicaciones_ids),
            'categorias_count': len(categorias_ids),
        }
        return render(request, 'auditorias/wizard/step3.html', context)
    
    return redirect('/auditorias/nuevo/?step=1')
