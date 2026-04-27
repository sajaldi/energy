from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from .models import Auditoria, ResultadoAuditoria
from activos.models import Ubicacion, Categoria, Activo
from .forms import AuditoriaStep1Form, AuditoriaStep2Form
import json
import random
import string

def generate_auditoria_name(ubicacion_ids):
    if not ubicacion_ids:
        return f"AUD-{timezone.now().strftime('%Y%m%d')}"
    
    try:
        # Pick a random location from the selected ones
        u_id = random.choice(ubicacion_ids)
        u = Ubicacion.objects.get(id=u_id)
        
        # Search for Building and Level in parents
        building = None
        level = None
        
        curr = u
        while curr:
            if curr.tipo == 'EDIFICIO':
                building = curr
            elif curr.tipo == 'NIVEL':
                level = curr
            curr = curr.padre
            
        # Top of hierarchy (Root)
        top = u.get_root()
        
        parts = []
        
        # 1. Nivel (3 letters)
        if level:
            parts.append(level.nombre[:3].upper())
        
        # 2. Edificio (3 letters)
        if building:
            parts.append(building.nombre[:3].upper())
            
        # 3. Tipo top hierarchy (3 letters)
        # The user says "Tipo el top de la jerarquía ( las primeras 3 letras)"
        # Assuming they mean the name of the top node.
        if top:
            parts.append(top.nombre[:3].upper())
            
        # Add random suffix to avoid duplicates
        suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=3))
        
        if not parts:
            return f"AUD-{u.nombre[:5].upper()}-{suffix}"
            
        return "-".join(parts) + "-" + suffix
    except Exception:
        return f"AUD-{random.randint(1000, 9999)}"

@login_required
def auditoria_wizard(request):
    # Si el usuario entra a /auditorias/nuevo/ sin especificar paso, 
    # asumimos que quiere iniciar una auditoría desde cero y limpiamos la sesión.
    if 'step' not in request.GET and request.method == 'GET':
        if 'auditoria_wizard_data' in request.session:
            del request.session['auditoria_wizard_data']
            
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
                session_data['tipo'] = form.cleaned_data['tipo']
                if form.cleaned_data.get('fecha_fin'):
                    session_data['fecha_fin'] = form.cleaned_data['fecha_fin'].isoformat()
                
                request.session['auditoria_wizard_data'] = session_data
                return redirect('/auditorias/nuevo/?step=2')
        else:
            initial = {
                'nombre': session_data.get('nombre', ''),
                'tipo': session_data.get('tipo', 'ACTIVOS'),
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
                u_ids = [u.id for u in form.cleaned_data['ubicaciones']]
                session_data['ubicaciones'] = u_ids
                session_data['categorias'] = [c.id for c in form.cleaned_data['categorias']]
                
                # Generar nombre si no existe
                if not session_data.get('nombre'):
                    session_data['nombre'] = generate_auditoria_name(u_ids)
                
                request.session['auditoria_wizard_data'] = session_data
                return redirect('/auditorias/nuevo/?step=3')
        else:
            initial = {
                'ubicaciones': session_data.get('ubicaciones', []),
                'categorias': session_data.get('categorias', [])
            }
            form = AuditoriaStep2Form(initial=initial)
            
        context = {
            'form': form, 
            'step': 2,
            'ubicaciones_roots': Ubicacion.objects.filter(padre__isnull=True).order_by('orden', 'nombre'),
            'categorias_roots': Categoria.objects.filter(padre__isnull=True).order_by('nombre'),
            'selected_ubicaciones': [str(id) for id in session_data.get('ubicaciones', [])],
            'selected_categorias': [str(id) for id in session_data.get('categorias', [])],
        }
        return render(request, 'auditorias/wizard/step2.html', context)

    elif step == 3:
        # Paso 3: Confirmación y Vista Previa
        if request.method == 'POST':
            # Crear Auditoría
            try:
                with transaction.atomic():
                    auditoria = Auditoria.objects.create(
                        nombre=session_data.get('nombre'),
                        tipo=session_data.get('tipo', 'ACTIVOS'),
                        fecha_fin=session_data.get('fecha_fin'),
                        creado_por=request.user,
                        estado='BORRADOR'
                    )
                    
                    if session_data.get('ubicaciones'):
                        auditoria.ubicaciones.set(session_data['ubicaciones'])
                    
                    if session_data.get('categorias'):
                        auditoria.categorias.set(session_data['categorias'])
                    
                    if auditoria.tipo == 'CONTEO':
                        # Lógica para Conteo Masivo detallado (por sub-ubicación, categoría y modelo)
                        from .models import ConteoAuditoria
                        from django.db.models import Count
                        
                        ubicaciones_ids = session_data.get('ubicaciones', [])
                        categorias_ids = session_data.get('categorias', [])
                        
                        # Obtener todos los IDs de las ubicaciones descendientes
                        all_sub_ubicaciones = set()
                        for u_id in ubicaciones_ids:
                            ubi = Ubicacion.objects.filter(id=u_id).first()
                            if ubi:
                                all_sub_ubicaciones.update(ubi.get_descendants(include_self=True).values_list('id', flat=True))
                        
                        # Obtener todos los IDs de las categorías descendientes
                        all_sub_categorias = set()
                        for c_id in categorias_ids:
                            cat = Categoria.objects.filter(id=c_id).first()
                            if cat:
                                all_sub_categorias.update(cat.get_descendants(include_self=True).values_list('id', flat=True))
                        
                        # 1. Agrupar activos por (ubicacion_id, categoria_id, modelo_id)
                        assets_grouped = Activo.objects.filter(
                            ubicacion_id__in=all_sub_ubicaciones,
                            modelo__categoria_id__in=all_sub_categorias
                        ).values('ubicacion_id', 'modelo__categoria_id', 'modelo_id').annotate(total=Count('id'))
                        
                        conteo_objects = []
                        covered_pairs = set() # (ubicacion_id, categoria_id)

                        # Crear registros para lo que realmente existe
                        for group in assets_grouped:
                            u_id = group['ubicacion_id']
                            c_id = group['modelo__categoria_id']
                            conteo_objects.append(ConteoAuditoria(
                                auditoria=auditoria,
                                ubicacion_id=u_id,
                                categoria_id=c_id,
                                modelo_id=group['modelo_id'],
                                cantidad_esperada=group['total']
                            ))
                            covered_pairs.add((u_id, c_id))
                        
                        # 2. Asegurar que TODAS las combinaciones (Ubicación x Categoría) existan (incluso con 0)
                        for u_id in all_sub_ubicaciones:
                            for c_id in all_sub_categorias:
                                if (u_id, c_id) not in covered_pairs:
                                    conteo_objects.append(ConteoAuditoria(
                                        auditoria=auditoria,
                                        ubicacion_id=u_id,
                                        categoria_id=c_id,
                                        modelo_id=None,
                                        cantidad_esperada=0
                                    ))
                        
                        if conteo_objects:
                            ConteoAuditoria.objects.bulk_create(conteo_objects)
                        
                        auditoria.estado = 'EN_CURSO'
                        auditoria.save()


                        
                        del request.session['auditoria_wizard_data']
                        messages.success(request, f"Auditoría de conteo '{auditoria.nombre}' creada.")
                        return redirect(f'/auditorias/ejecutar/{auditoria.id}/')

                    else:
                        # Lógica original para Activos Individuales
                        assets_query = Activo.objects.all()
                        
                        # (Original filtering and bulk creation logic follows...)
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
