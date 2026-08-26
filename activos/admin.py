from django.shortcuts import render
from django.urls import reverse
from django.db import models
from django.contrib import admin, messages
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from django.db.models import Count, Max, Q
from import_export.admin import ImportExportModelAdmin, ImportExportMixin, ImportExportActionModelAdmin
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from django.contrib.auth.models import User
from .models import Activo, Categoria, Familia, Ubicacion, Marca, Modelo, Plano, VisorPlano, PinPlano, PuntoMedicion, DocumentoMedicion, RegistroImportacion, Disciplina, ControlSubmittal, DocumentoAltaBaja, ItemAltaBaja, ArchivoAltaBaja, FotoUbicacion, ReporteGenerado, DowntimeActivo, CaracteristicaCategoria, ValorCaracteristicaModelo

@admin.register(ReporteGenerado)
class ReporteGeneradoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'usuario', 'estado', 'creado_en', 'completado_en')
    list_filter = ('estado', 'creado_en')
    search_fields = ('nombre', 'usuario__username')
    readonly_fields = ('creado_en', 'completado_en')

@admin.register(DowntimeActivo)
class DowntimeActivoAdmin(admin.ModelAdmin):
    list_display = ('activo', 'aviso', 'orden_trabajo', 'inicio', 'fin', 'duracion_horas', 'motivo')
    list_filter = ('inicio', 'activo', ('aviso', admin.EmptyFieldListFilter), ('orden_trabajo', admin.EmptyFieldListFilter))
    search_fields = ('activo__nombre', 'orden_trabajo__codigo_de_orden', 'aviso__id', 'motivo')
    readonly_fields = ('duracion_horas',)
    autocomplete_fields = ('activo', 'orden_trabajo', 'aviso')

@admin.register(FotoUbicacion)
class FotoUbicacionAdmin(admin.ModelAdmin):
    list_display = ('id', 'ubicacion', 'subido_por', 'creado_en')
    list_filter = ('creado_en', 'subido_por')
    search_fields = ('ubicacion__nombre', 'descripcion')
    readonly_fields = ('creado_en',)

# ... (resto de registros)
from auditorias.models import ResultadoAuditoria

from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from inventarios.models import CompatibilidadMaterial
from documentos.models import Documento

# Importar admin de Bien Afecto
from .admin_bien_afecto import BienAfectoAdmin, HistorialBienAfectoAdmin
from django import forms

from .forms import ActivoAdminForm
from .widgets import (SmartModeloWidget, SmartUserWidget, SmartActivoWidget, SmartFamiliaWidget, 
                      SmartParentWidget, CachedDisciplinaWidget, CachedUbicacionWidget, 
                      SmartPlanoWidget, SmartUbicacionWidget)
from .filters import ActivoFaltantesFilter, UbicacionHierarchyFilter
from .inlines import (SubFamiliaInline, ActivoFamiliaInline, PinPlanoInline, CompatibilidadMaterialInline, 
                      ModeloInline, UbicacionHijaInline, PlanoInline, UbicacionEnPlanosInline, 
                      ComponenteActivoInline, PuntoMedicionInline, DocumentoMedicionInline, AuditoriasActivoInline)
from .resources import (PlanoResource, DisciplinaResource, FamiliaResource, UbicacionResource, ModeloResource, ActivoResource, ControlSubmittalResource)



@admin.register(Plano)
class PlanoAdmin(ImportExportModelAdmin):
    list_per_page = 50
    resource_class = PlanoResource
    change_list_template = 'admin/activos/plano/change_list.html'
    list_display = ('nombre', 'tipo_plano', 'numero_documento', 'titulo', 'disciplina', 'ubicacion', 'documento_info', 'creado_en')
    list_filter = (
        'tipo_plano', 
        ('disciplina', admin.RelatedOnlyFieldListFilter),
        UbicacionHierarchyFilter
    )

    def has_import_permission(self, request):
        return True

    list_select_related = (
        'ubicacion', 'ubicacion__padre', 'ubicacion__padre__padre',
        'disciplina', 'disciplina__padre', 'disciplina__padre__padre',
        'documento', 'documento__ultima_revision'
    )
    search_fields = ('nombre', 'ubicacion__nombre', 'documento__codigo')
    autocomplete_fields = ('documento', 'disciplina', 'ubicacion', 'activos')
    readonly_fields = ('visor_pdf_interactivo',)
    fieldsets = (
        (None, {'fields': ('nombre', 'tipo_plano', 'numero_documento', 'titulo', 'disciplina', 'ubicacion', 'descripcion')}),
        ('Archivo del Plano', {
            'fields': ('documento', 'archivo', 'visor_pdf_interactivo'),
            'description': 'Usa "Documento" para control de versiones, o "Archivo" para carga directa.'
        }),
        ('Activos Vinculados', {'fields': ('activos',)}),
    )

    def documento_info(self, obj):
        if obj.documento:
            rev = obj.revision_actual or ''
            return format_html('<span style="color: #2563eb;">{}</span> <small style="color: #64748b;">{}</small>', 
                             obj.documento.codigo, rev)
        return mark_safe('<span style="color: #94a3b8;">Sin documento</span>')
    documento_info.short_description = "Documento"

    def visor_pdf_interactivo(self, obj):
        if not obj.pk:
            return mark_safe('<p style="color:#94a3b8;font-size:13px;">Guarda el plano primero para ver el visor.</p>')
        archivo = obj.archivo_actual
        if not archivo:
            return mark_safe('<p style="color:#94a3b8;font-size:13px;">Sin archivo adjunto.</p>')
        visor_url = f'/activos/visor-pdf/{obj.pk}/'
        proxy_url = f'/activos/plano-proxy/{obj.pk}/'
        rev = f' &nbsp;<span style="color:#64748b;font-size:11px;">({obj.revision_actual})</span>' if obj.revision_actual else ''
        return mark_safe(f'''
<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:4px 0;">
  <a href="{visor_url}" target="_blank"
     style="display:inline-flex;align-items:center;gap:8px;background:#2563eb;color:white;
            padding:8px 18px;border-radius:6px;font-size:13px;font-weight:700;
            text-decoration:none;letter-spacing:0.3px;">
    📐 Abrir Visor de Plano
  </a>
  <a href="{proxy_url}" target="_blank"
     style="display:inline-flex;align-items:center;gap:6px;background:#f8fafc;color:#475569;
            padding:8px 14px;border-radius:6px;font-size:13px;font-weight:600;
            text-decoration:none;border:1px solid #e2e8f0;">
    ↗ Ver archivo crudo
  </a>
  {rev}
</div>
''')

    visor_pdf_interactivo.short_description = "Visor"
    
    def get_queryset(self, request):
        """Optimizar la consulta base con joins pre-calculados para evitar N+1."""
        return super().get_queryset(request).select_related(
            *self.list_select_related
        )

    resource_class = PlanoResource

    # get_changelist_template removed in favor of class attribute

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('import-background/', self.admin_site.admin_view(self.import_background), name='activos_plano_import_background'),
            path('import-process/', self.admin_site.admin_view(self.import_process), name='activos_plano_import_process'),
            path('import-progress/', self.admin_site.admin_view(self.import_progress), name='activos_plano_import_progress'),
        ]
        return custom_urls + urls

    def import_background(self, request):
        context = {
            'title': 'Importación masiva de Planos',
        }
        return render(request, 'admin/activos/plano/background_import.html', context)

    @csrf_exempt
    def import_process(self, request):
        print(f"DEBUG: import_process called. Method: {request.method}")
        if request.method == 'POST' and request.FILES.get('file'):
            import os, uuid
            from django.core.files.storage import default_storage
            from django.core.files.base import ContentFile
            from django.http import JsonResponse
            from tablib import Dataset
            
            myfile = request.FILES['file']
            file_name = myfile.name
            file_format = file_name.split('.')[-1].lower()
            import_id = str(uuid.uuid4())
            temp_path = f'tmp/plano_imp_{import_id}.{file_format}'
            path = default_storage.save(temp_path, ContentFile(myfile.read()))
            
            try:
                with default_storage.open(path, 'rb') as f:
                    file_content = f.read()
                    if file_format == 'csv':
                        # Usar una decodificación robusta para CSVs de Excel
                        from .tasks import try_decode
                        dataset = Dataset().load(try_decode(file_content), format='csv')
                    else:
                        dataset = Dataset().load(file_content, format=file_format)
                
                # Normalizar encabezados (quitar acentos, espacios, a minúsculas y cambiar espacios por guiones bajos)
                import unicodedata
                def normalize(text):
                    text = str(text).strip().lower()
                    # Quitar acentos: á -> a, é -> e, etc.
                    text = "".join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')
                    return text.replace(' ', '_').replace('.', '_')

                dataset.headers = [normalize(h) for h in dataset.headers]
                print(f"DEBUG: Normalized headers: {dataset.headers}")
                
                # Guardar versión JSON para procesamiento ultra rápido en los chunks
                # Convertimos a bytes explícitamente para evitar errores de checksum en S3/MinIO
                json_path = f'tmp/plano_imp_{import_id}.json'
                json_data = dataset.json.encode('utf-8')
                default_storage.save(json_path, ContentFile(json_data))
                
                # Eliminar archivo original
                try:
                    default_storage.delete(path)
                except:
                    pass

                return JsonResponse({
                    'status': 'started',
                    'import_id': import_id,
                    'total': len(dataset),
                    'file_format': 'json'
                })
            except Exception as e:
                return JsonResponse({'status': 'error', 'message': f'Error al leer archivo: {str(e)}'}, status=400)
        return JsonResponse({'status': 'error', 'message': 'No se recibió archivo'}, status=400)

    def import_progress(self, request):
        from django.http import JsonResponse
        from django.core.files.storage import default_storage
        from tablib import Dataset
        from import_export import resources
        import os

        import_id = request.GET.get('import_id')
        start = int(request.GET.get('start', 0))
        chunk_size = int(request.GET.get('size', 50))
        file_format = request.GET.get('format', 'xlsx')

        if not import_id:
            return JsonResponse({'status': 'error', 'message': 'Falta import_id'}, status=400)

        temp_path = f'tmp/plano_imp_{import_id}.json'
        if not default_storage.exists(temp_path):
            return JsonResponse({'status': 'error', 'message': 'Sesión expirada o archivo no encontrado'}, status=404)

        resource = PlanoResource()
        
        try:
            with default_storage.open(temp_path, 'rb') as f:
                file_content = f.read()
                dataset = Dataset().load(file_content, format='json')
            
            total = len(dataset)
            end = min(start + chunk_size, total)
            
            print(f"IMPORT PLANOS (ULTRA): Procesando lote {start} - {end} de {total}")
            
            mini_dataset = Dataset()
            mini_dataset.headers = dataset.headers
            for row in dataset[start:end]:
                mini_dataset.append(row)
            
            from django.db import transaction
            
            # Debug: Mostrar qué estamos intentando importar
            print(f"DEBUG: Mini-dataset headers: {mini_dataset.headers}")
            if len(mini_dataset) > 0:
                print(f"DEBUG: First row: {mini_dataset[0]}")

            with transaction.atomic():
                result = resource.import_data(mini_dataset, dry_run=False, raise_errors=False)
            
            from .models import Plano
            db_count = Plano.objects.count()
            print(f"IMPORT PLANOS: {result.totals.get('new', 0)} nuevos, {result.totals.get('update', 0)} actualizados. Total en DB ahora: {db_count}")

            if end >= total:
                try:
                    default_storage.delete(temp_path)
                except:
                    pass

            error_details = []
            for error in result.row_errors():
                row_idx = error[0]
                error_list = error[1]
                for err in error_list:
                    error_details.append({
                        'row': start + row_idx + 1,
                        'message': str(err.error)
                    })
            
            for err in result.base_errors:
                error_details.append({
                    'row': 'General',
                    'message': str(err.error)
                })

            return JsonResponse({
                'status': 'PROGRESS',
                'current': end,
                'total': total,
                'new': result.totals.get('new', 0),
                'updated': result.totals.get('update', 0) + result.totals.get('updated', 0),
                'skipped': result.totals.get('skip', 0),
                'errors': len(result.base_errors) + len(result.row_errors()),
                'error_list': error_details,
                'db_total': db_count,
                'is_last': end >= total
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@admin.register(Disciplina)
class DisciplinaAdmin(ImportExportModelAdmin):
    resource_class = DisciplinaResource
    list_display = ('nombre', 'padre', 'get_ruta_completa')
    search_fields = ('nombre',)
    list_filter = ('padre',)
    autocomplete_fields = ('padre',)
    
    def get_ruta_completa(self, obj):
        return obj.get_ruta_completa()
    get_ruta_completa.short_description = "Ruta Completa"


@admin.register(VisorPlano)
class VisorPlanoAdmin(admin.ModelAdmin):
    list_per_page = 50
    list_display = ('nombre', 'plano', 'abrir_visor', 'creado_en')
    list_filter = ('plano',)
    list_select_related = ('plano',)
    search_fields = ('nombre', 'plano__nombre')
    inlines = [PinPlanoInline]

    def abrir_visor(self, obj):
        return format_html('<a href="/activos/visor/{0}/" target="_blank" class="button" style="background-color: #447e9b; color: white; padding: 5px 10px; border-radius: 4px; text-decoration: none;">👁️ Abrir Visor Interactivo</a>', obj.pk)
    abrir_visor.short_description = "Visor"

@admin.register(PinPlano)
class PinPlanoAdmin(admin.ModelAdmin):
    list_per_page = 50
    list_display = ('visor', 'activo', 'x', 'y', 'color')
    list_filter = ('visor', 'visor__plano')
    list_select_related = ('visor', 'activo')
    search_fields = ('visor__nombre', 'activo__nombre')
    autocomplete_fields = ['activo', 'visor']

@admin.register(CaracteristicaCategoria)
class CaracteristicaCategoriaAdmin(ImportExportModelAdmin):
    list_per_page = 50
    list_display = ('nombre', 'categoria', 'tipo_dato', 'requerido', 'unidad_medida')
    list_filter = ('categoria', 'tipo_dato', 'requerido')
    search_fields = ('nombre', 'categoria__nombre')
    autocomplete_fields = ('categoria',)

class CaracteristicaCategoriaInline(admin.TabularInline):
    model = CaracteristicaCategoria
    extra = 1

@admin.register(Categoria)
class CategoriaAdmin(ImportExportModelAdmin):
    list_per_page = 50
    list_display = ('nombre', 'icono', 'descripcion', 'cantidad_activos')
    search_fields = ('nombre',)
    inlines = [CaracteristicaCategoriaInline]
    change_form_template = 'admin/activos/categoria/change_form.html'
    change_list_template = 'admin/activos/categoria/change_list.html'

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('<path:object_id>/explorer/', self.admin_site.admin_view(self.explorer_view), name='activos_categoria_explorer'),
        ]
        return custom_urls + urls

    def explorer_view(self, request, object_id):
        obj = self.get_object(request, object_id)
        # Calculate total assets (including descendants)
        descendants = obj.get_descendants(include_self=True)
        total_activos = Activo.objects.filter(modelo__categoria__in=descendants).count()

        context = {
            **self.admin_site.each_context(request),
            'object': obj,
            'cat_id': obj.id,
            'total_activos': total_activos,
            'is_popup': True, # To hide some admin elements if template supports it
            'hide_chatbot': True,
        }
        return render(request, 'admin/activos/categoria/explorer_tab.html', context)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.annotate(
            _activos_count=Count('modelos__activos', distinct=True)
        )
        return queryset

    def cantidad_activos(self, obj):
        count = getattr(obj, '_activos_count', 0)
        if count == 0:
            return mark_safe('<span style="color: #cbd5e1;">0</span>')
        return format_html(
            '<span style="background: #eff6ff; color: #2563eb; padding: 2px 10px; border-radius: 12px; font-weight: 700;">{}</span>',
            count
        )
    cantidad_activos.short_description = "Cantidad Activos"
    cantidad_activos.admin_order_field = '_activos_count'

@admin.register(Familia)
class FamiliaAdmin(ImportExportModelAdmin):
    list_per_page = 50
    resource_class = FamiliaResource
    list_display = ('nombre_con_indentacion', 'descripcion')
    list_display_links = ('nombre_con_indentacion',)
    search_fields = ('nombre',)
    list_select_related = ('padre', 'padre__padre')
    autocomplete_fields = ('padre',)
    inlines = [SubFamiliaInline]

    def nombre_con_indentacion(self, obj):
        # Usar lógica similar a Ubicacion si queremos niveles
        # Por ahora simple o calcular profundidad
        depth = 0
        curr = obj.padre
        while curr:
            depth += 1
            curr = curr.padre
        
        indent = depth * 20
        icon = "📁" if depth == 0 else "↳"
        return format_html(
            '<div style="text-indent: {0}px; display: flex; align-items: center;">'
            '<span style="margin-right: 8px; opacity: 0.6;">{1}</span> {2}'
            '</div>',
            indent, icon, obj.nombre
        )
    nombre_con_indentacion.short_description = 'Familia'



@admin.register(Marca)
class MarcaAdmin(ImportExportModelAdmin):
    list_per_page = 50
    list_display = ('nombre_expandible', 'total_modelos')
    search_fields = ('nombre',)
    inlines = [ModeloInline]

    def total_modelos(self, obj):
        return obj.modelos.count()
    total_modelos.short_description = "N° Modelos"

    def nombre_expandible(self, obj):
        edit_url = reverse('admin:activos_marca_change', args=[obj.pk])
        return format_html(
            '<div class="brand-tree-node" data-brand-id="{0}" style="cursor: pointer; display: flex; align-items: center; width: 100%;">'
            '<span class="tree-toggle mr-2"><i class="fas fa-chevron-right text-muted-fiori"></i></span>'
            '<span class="brand-name font-weight-bold" style="color: #0854a0; flex-grow: 1;">{1}</span>'
            '<a href="{2}" class="ml-2 text-muted edit-brand-link" title="Editar Marca" onclick="event.stopPropagation();">'
            '<i class="fas fa-edit" style="font-size: 0.8rem; opacity: 0.5;"></i>'
            '</a>'
            '</div>',
            obj.pk, obj.nombre, edit_url
        )
    nombre_expandible.short_description = "Marca"

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('<path:object_id>/get_models_ajax/', self.admin_site.admin_view(self.get_models_ajax), name='activos_marca_get_models'),
        ]
        return custom_urls + urls

    def get_models_ajax(self, request, object_id):
        marca = self.get_object(request, object_id)
        modelos = marca.modelos.select_related('categoria').all()
        
        if not modelos:
            return HttpResponse('<div class="p-3 text-muted"><i class="fas fa-info-circle mr-1"></i> Esta marca no tiene modelos registrados.</div>')
        
        html = '<div class="models-tree-child shadow-sm" style="background: #f8fafc; margin: 10px 0 10px 30px; border-radius: 8px; border: 1px solid #e2e8f0; overflow: hidden;">'
        html += '<table class="table table-sm mb-0" style="font-size: 0.85rem;">'
        html += '<thead style="background: #eff6ff;"><tr>'
        html += '<th class="pl-3 py-2">Modelo</th><th class="py-2">Categoría</th><th class="py-2 text-center">Equipos</th><th class="py-2 text-center">Acción</th>'
        html += '</tr></thead><tbody>'
        
        for m in modelos:
            cat_name = m.categoria.nombre if m.categoria else "Sin categoría"
            count = m.activos.count()
            edit_url = reverse('admin:activos_modelo_change', args=[m.id])
            
            html += f'<tr style="border-bottom: 1px solid #f1f5f9;">'
            html += f'<td class="pl-3 py-2"><strong>{m.nombre}</strong></td>'
            html += f'<td class="py-2 text-muted">{cat_name}</td>'
            html += f'<td class="py-2 text-center"><span class="badge badge-info" style="background: #e0f2fe; color: #0369a1; font-weight: 600;">{count}</span></td>'
            html += f'<td class="py-2 text-center"><a href="{edit_url}" target="_blank" class="text-muted"><i class="fas fa-edit"></i></a></td>'
            html += '</tr>'
            
        html += '</tbody></table></div>'
        return HttpResponse(html)

    class Media:
        js = (
            'https://code.jquery.com/jquery-3.6.0.min.js',
            'core/js/brand_tree.js',
        )
        css = {
            'all': ('core/css/brand_tree.css',)
        }

class ValorCaracteristicaModeloInline(admin.TabularInline):
    model = ValorCaracteristicaModelo
    extra = 1

@admin.register(Modelo)
class ModeloAdmin(ImportExportModelAdmin):
    list_per_page = 50
    resource_class = ModeloResource
    list_display = ('thumbnail', 'nombre', 'marca', 'categoria', 'total_activos')
    list_filter = ('marca', 'categoria')
    list_select_related = ('marca', 'categoria')
    autocomplete_fields = ('marca', 'categoria', 'documentos')
    inlines = [CompatibilidadMaterialInline, ValorCaracteristicaModeloInline]

    def get_import_resource_kwargs(self, request, *args, **kwargs):
        return {'user': request.user}
    
    def get_export_resource_kwargs(self, request, *args, **kwargs):
        return {'user': request.user}
    search_fields = ('nombre', 'marca__nombre')
    readonly_fields = ('preview_imagen', 'lista_activos_ubicacion', 'rutinas_aplicables')

    def thumbnail(self, obj):
        if obj.imagen:
            return format_html('<img src="{}" style="width: 40px; height: 40px; object-fit: cover; border-radius: 4px;" />', obj.imagen)
        return mark_safe('<div style="width: 40px; height: 40px; background: #f1f5f9; border-radius: 4px; display: flex; align-items: center; justify-content: center; color: #cbd5e1;"><ion-icon name="image-outline"></ion-icon></div>')
    thumbnail.short_description = 'Imagen'

    def preview_imagen(self, obj):
        if obj.imagen:
            return format_html('<img src="{}" style="max-width: 300px; max-height: 300px; border-radius: 8px; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);" />', obj.imagen)
        return mark_safe('<span style="color: #94a3b8; font-style: italic;">No hay imagen configurada</span>')
    preview_imagen.short_description = 'Vista Previa'

    def rutinas_aplicables(self, obj):
        if not obj.categoria:
            return mark_safe('<span style="color: #94a3b8; font-style: italic;">No hay una categoría de activo definida para este modelo.</span>')
        
        cat = obj.categoria
        from mantenimiento.models import Rutina, Tipo

        # Obtener todos los Tipos vinculados a esta categoría
        tipo_ids = set(Tipo.objects.filter(categoria_activo=cat).values_list('id', flat=True))

        # También buscar por el reverse relation (mantenimiento_tipo)
        m_cat_mgr = getattr(cat, 'mantenimiento_tipo', None)
        if m_cat_mgr is not None:
            tipo_ids.update(m_cat_mgr.values_list('id', flat=True))

        # Obtener ancestros de todos esos tipos (jerarquía padre)
        all_tipo_ids = set(tipo_ids)
        queue = list(tipo_ids)
        while queue:
            children = Tipo.objects.filter(padre_id__in=queue).values_list('id', flat=True)
            new_ids = set(children) - all_tipo_ids
            all_tipo_ids.update(new_ids)
            queue = list(new_ids)

        # Buscar rutinas vinculadas por tipo (jerarquía) O directamente por categoria_activo
        q = Q(categoria_activo=cat)
        if all_tipo_ids:
            q |= Q(tipo_id__in=all_tipo_ids)
        rutinas = Rutina.objects.filter(q).select_related('frecuencia', 'tipo')

        if not rutinas.exists():
            return format_html('<span style="color: #94a3b8; font-style: italic;">La categoría "{0}" no tiene tipos de mantenimiento vinculados ni rutinas directas.</span>', cat.nombre)

        html = '<div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; margin-top: 10px;">'
        html += '<table style="width: 100%; border-collapse: collapse; font-size: 0.85rem;">'
        html += '<thead style="background: #f8fafc; border-bottom: 2px solid #e2e8f0;">'
        html += '<tr>'
        html += '<th style="text-align: left; padding: 12px 15px; color: #475569; font-weight: 700;">Rutina</th>'
        html += '<th style="text-align: center; padding: 12px 15px; color: #475569; font-weight: 700;">Frecuencia</th>'
        html += '<th style="text-align: center; padding: 12px 15px; color: #475569; font-weight: 700;">HH/Técnicos</th>'
        html += '<th style="text-align: center; padding: 12px 15px; color: #475569; font-weight: 700;">Acción</th>'
        html += '</tr></thead><tbody>'
        
        for r in rutinas:
            frec_nombre = r.frecuencia.nombre if r.frecuencia else "N/A"
            hh = r.tiempo_estimado if r.tiempo_estimado else "---"
            tecs = r.cantidad_tecnicos
            
            html += f'<tr style="border-bottom: 1px solid #f1f5f9;">'
            html += f'<td style="padding: 12px 15px;">'
            html += f'<div style="font-weight: 600; color: #1e293b;">{r.nombre}</div>'
            html += f'<div style="font-size: 0.75rem; color: #64748b;">{r.tipo.nombre if r.tipo else "General"}</div>'
            html += f'</td>'
            html += f'<td style="padding: 12px 15px; text-align: center;">'
            html += f'<span style="background: #eff6ff; color: #2563eb; padding: 4px 10px; border-radius: 12px; font-weight: 600; font-size: 0.75rem;">{frec_nombre}</span>'
            html += f'</td>'
            html += f'<td style="padding: 12px 15px; text-align: center; color: #475569;">'
            html += f'{hh} <br> <small style="color: #94a3b8;">({tecs} Tec.)</small>'
            html += f'</td>'
            html += f'<td style="padding: 12px 15px; text-align: center;">'
            html += f'<a href="/admin/mantenimiento/rutina/{r.id}/change/" target="_blank" style="background: #f1f5f9; color: #475569; padding: 5px; border-radius: 4px; display: inline-flex; align-items: center; border: 1px solid #e2e8f0; text-decoration: none;">'
            html += f'<ion-icon name="open-outline" style="font-size: 1rem;"></ion-icon>'
            html += '</a></td></tr>'
        
        html += '</tbody></table></div>'
        return mark_safe(html)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(activos_count=Count('activos'))

    def total_activos(self, obj):
        return getattr(obj, 'activos_count', obj.activos.count())
    total_activos.short_description = 'Total Activos'
    total_activos.admin_order_field = 'activos_count'

    def lista_activos_ubicacion(self, obj):
        activos = obj.activos.select_related('ubicacion').order_by('ubicacion__nombre')
        if not activos:
            return mark_safe('<span style="color: #999;">No hay activos registrados con este modelo.</span>')

        html = '<div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden;">'
        html += '<table style="width: 100%; border-collapse: collapse; font-size: 0.85rem;">'
        html += '<thead style="background: #f1f5f9; border-bottom: 1px solid #e2e8f0;">'
        html += '<tr>'
        html += '<th style="text-align: left; padding: 10px 15px; color: #64748b;">Ubicación</th>'
        html += '<th style="text-align: left; padding: 10px 15px; color: #64748b;">Código Interno</th>'
        html += '<th style="text-align: left; padding: 10px 15px; color: #64748b;">Nombre / Serie</th>'
        html += '<th style="text-align: center; padding: 10px 15px; color: #64748b;">Estado</th>'
        html += '<th style="text-align: center; padding: 10px 15px; color: #64748b;">Acción</th>'
        html += '</tr></thead><tbody>'

        for activo in activos:
            ubicacion_str = activo.ubicacion.ruta_completa if activo.ubicacion else '<span style="color: #dc3545;">Sin Ubicación</span>'
            estado_color = {
                'OPERATIVO': '#10b981',
                'MANTENIMIENTO': '#f59e0b',
                'REPARACION': '#ef4444',
                'FUERA_SERVICIO': '#4b5563',
                'OBSOLETO': '#64748b'
            }.get(activo.estado, '#000')

            html += f'<tr style="border-bottom: 1px solid #f1f5f9;">'
            html += f'<td style="padding: 10px 15px; font-weight: 500;">{ubicacion_str}</td>'
            html += f'<td style="padding: 10px 15px; color: #007bff; font-family: monospace;">{activo.codigo_interno or "---"}</td>'
            html += f'<td style="padding: 10px 15px;">{activo.nombre}<br><small style="color: #94a3b8;">S/N: {activo.serie or "N/A"}</small></td>'
            html += f'<td style="padding: 10px 15px; text-align: center;">'
            html += f'<span style="background: {estado_color}15; color: {estado_color}; padding: 3px 8px; border-radius: 12px; font-size: 0.75rem; font-weight: 700;">{activo.get_estado_display()}</span>'
            html += f'</td>'
            html += f'<td style="padding: 10px 15px; text-align: center;">'
            html += f'<a href="/admin/activos/activo/{activo.id}/change/" target="_blank" style="color: #64748b;"><ion-icon name="create-outline" style="font-size: 1.1rem;"></ion-icon></a>'
            html += f'</td></tr>'

        html += '</tbody></table></div>'
        return mark_safe(html)
    lista_activos_ubicacion.short_description = 'Activos Clasificados por Ubicación'

    fieldsets = (
        ('Información General', {
            'fields': ('nombre', 'marca', 'categoria', 'precio_promedio', 'descripcion')
        }),
        ('Imagen del Modelo', {
            'fields': (('imagen_archivo', 'imagen_url'), 'preview_imagen'),
            'description': 'Puedes subir una imagen local o proporcionar una URL externa. Si usas ambas, tendrá prioridad el archivo cargado.'
        }),
        ('Mantenimiento Preventivo Sugerido', {
            'fields': ('rutinas_aplicables',),
            'description': 'Listado de rutinas que aplican a todos los activos de este modelo basándose en su categoría.'
        }),
        ('Distribución de Activos', {
            'fields': ('lista_activos_ubicacion',),
            'description': 'Listado completo de equipos físicos asociados a este modelo, organizados jerárquicamente por su ubicación.'
        }),
        ('Biblioteca de Documentos', {
            'fields': ('documentos',),
            'description': 'Gestione aquí los manuales, fichas técnicas y otros documentos asociados a este modelo de equipo.'
        }),
    )


@admin.register(Ubicacion)
class UbicacionAdmin(ImportExportMixin, admin.ModelAdmin):
    """
    Admin para ubicaciones jerárquicas con estructura premium.
    """
    list_per_page = 50
    list_display = ('nombre_con_indentacion', 'tipo', 'es_almacen', 'padre', 'orden', 'total_hijos')
    list_display_links = ('nombre_con_indentacion',)
    list_editable = ('orden', 'tipo', 'es_almacen')
    search_fields = ('nombre',)
    
    class RaizFilter(admin.SimpleListFilter):
        title = 'Nivel'
        parameter_name = 'nivel'
        def lookups(self, request, model_admin):
            return (('raices', 'Filtrar solo Principales'),)
        def queryset(self, request, queryset):
            if self.value() == 'raices':
                return queryset.filter(padre__isnull=True)
            return queryset

    list_filter = ('tipo', RaizFilter)
    autocomplete_fields = ('padre', 'categoria')
    inlines = [UbicacionHijaInline, PlanoInline, UbicacionEnPlanosInline]
    change_list_template = 'admin/activos/ubicacion/change_list.html'
    readonly_fields = ('rutinas_mantenimiento',)

    fieldsets = (
        ('Datos Principales', {
            'fields': (('nombre', 'tipo'), ('padre', 'orden'), ('categoria', 'es_almacen'))
        }),
        ('Detalles', {
            'fields': ('descripcion',)
        }),
        ('Área (Bodegas)', {
            'fields': (('ancho_m', 'largo_m'),),
            'description': 'Dimensiones del piso del almacén en metros (solo para ubicaciones tipo BODEGA).',
        }),
        ('Mantenimiento Programado', {
            'fields': ('rutinas_mantenimiento',),
            'description': 'Rutinas de mantenimiento asociadas a la categoría de esta ubicación.'
        }),
    )

    def rutinas_mantenimiento(self, obj):
        if not obj.categoria:
            return mark_safe('<span style="color: #94a3b8; font-style: italic;">No hay categoría asignada. Asigne una categoría (ej: "Quirófano", "Subestación") para ver las rutinas.</span>')
        
        cat = obj.categoria
        from mantenimiento.models import Rutina, Tipo

        # Obtener todos los Tipos vinculados a esta categoría
        tipo_ids = set(Tipo.objects.filter(categoria_activo=cat).values_list('id', flat=True))

        # También buscar por el reverse relation (mantenimiento_tipo)
        m_cat_mgr = getattr(cat, 'mantenimiento_tipo', None)
        if m_cat_mgr is not None:
            tipo_ids.update(m_cat_mgr.values_list('id', flat=True))

        # Obtener ancestros de todos esos tipos (jerarquía padre)
        all_tipo_ids = set(tipo_ids)
        queue = list(tipo_ids)
        while queue:
            children = Tipo.objects.filter(padre_id__in=queue).values_list('id', flat=True)
            new_ids = set(children) - all_tipo_ids
            all_tipo_ids.update(new_ids)
            queue = list(new_ids)

        # Buscar rutinas vinculadas por tipo (jerarquía) O directamente por categoria_activo
        q = Q(categoria_activo=cat)
        if all_tipo_ids:
            q |= Q(tipo_id__in=all_tipo_ids)
        rutinas = Rutina.objects.filter(q).select_related('frecuencia', 'tipo', 'puesto_trabajo')

        if not rutinas.exists():
            return format_html(
                '<div style="background: #fff1f2; color: #be123c; padding: 10px; border-radius: 6px; border: 1px solid #fecaca;">'
                '<strong style="display:block; margin-bottom:4px;">Sin vinculación de Mantenimiento</strong>'
                'La categoría de activo <em>"{}"</em> no tiene rutinas configuradas. '
                '<a href="/admin/mantenimiento/categoria/" target="_blank">Configure esto aquí</a>.'
                '</div>', 
                cat.nombre
            )
            
        html = '<div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; margin-top: 5px;">'
        html += '<table style="width: 100%; border-collapse: collapse; font-size: 0.85rem;">'
        html += '<thead style="background: #f8fafc; border-bottom: 2px solid #e2e8f0;">'
        html += '<tr>'
        html += '<th style="text-align: left; padding: 12px 15px; color: #475569; font-weight: 700;">Rutina</th>'
        html += '<th style="text-align: left; padding: 12px 15px; color: #475569; font-weight: 700;">Frecuencia / Puesto</th>'
        html += '<th style="text-align: center; padding: 12px 15px; color: #475569; font-weight: 700;">Estimado</th>'
        html += '<th style="text-align: center; padding: 12px 15px; color: #475569; font-weight: 700;">Acción</th>'
        html += '</tr></thead><tbody>'
        
        for r in rutinas:
            frec_nombre = r.frecuencia.nombre if r.frecuencia else "N/A"
            puesto = r.puesto_trabajo.nombre if r.puesto_trabajo else "Cualquiera"
            tiempo = f"{int(r.tiempo_estimado.total_seconds() // 60)} min" if r.tiempo_estimado else "---"
            is_inherited = r.categoria.id != m_cat.id
            
            row_style = 'background: #fdfdfd;' if is_inherited else 'background: white;'
            
            html += f'<tr style="border-bottom: 1px solid #f1f5f9; {row_style}">'
            html += f'<td style="padding: 12px 15px;">'
            html += f'<div style="font-weight: 600; color: #1e293b;">{r.nombre}</div>'
            if is_inherited:
                html += f'<div style="font-size: 0.70rem; color: #94a3b8;">Heredada de: {r.tipo.nombre}</div>'
            else:
                html += f'<div style="font-size: 0.70rem; color: #10b981;">Específica del sitio</div>'
            html += f'</td>'
            
            html += f'<td style="padding: 12px 15px;">'
            html += f'<span style="background: #eff6ff; color: #2563eb; padding: 3px 8px; border-radius: 4px; font-weight: 600; font-size: 0.75rem; margin-right:5px;">{frec_nombre}</span>'
            html += f'<span style="color: #64748b; font-size: 0.8rem;">{puesto}</span>'
            html += f'</td>'
            
            html += f'<td style="padding: 12px 15px; text-align: center; color: #475569;">'
            html += f'<ion-icon name="time-outline" style="vertical-align:middle;"></ion-icon> {tiempo}'
            html += f'</td>'
            
            html += f'<td style="padding: 12px 15px; text-align: center;">'
            html += f'<a href="/admin/mantenimiento/rutina/{r.id}/change/" target="_blank" title="Ver Detalles" style="color: #64748b; padding: 5px; text-decoration: none;">'
            html += f'<ion-icon name="open-outline" style="font-size: 1.2rem;"></ion-icon>'
            html += '</a></td></tr>'
        
        html += '</tbody></table></div>'
        return mark_safe(html)
    rutinas_mantenimiento.short_description = "Rutinas Aplicables"
    change_list_template = 'admin/activos/ubicacion/change_list.html'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'padre', 'padre__padre', 'padre__padre__padre', 'padre__padre__padre__padre'
        ).annotate(
            _hijos_count=Count('sub_ubicaciones')
        )

    class Media:
        css = {
            'all': (
                'https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap',
                # CSS inyectado para ajustar anchos de columnas del inline
                'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css',
            )
        }
        js = ('https://unpkg.com/ionicons@5.5.2/dist/ionicons/ionicons.esm.js', 
              'https://unpkg.com/ionicons@5.5.2/dist/ionicons/ionicons.js')

    # Añadimos un pequeño hack de CSS inline para el admin
    def get_inline_instances(self, request, obj=None):
        from django.utils.safestring import mark_safe
        # Inyectamos estilos directamente en el encabezado mediante un truco de admin
        # para forzar anchos de tabla del inline
        request._inline_css = mark_safe("""
            <style>
                .inline-group .tabular td.column-render_icon { width: 50px !important; text-align: center; }
                .inline-group .tabular td.column-orden { width: 80px !important; }
                .inline-group .tabular td.column-total_count { width: 120px !important; white-space: nowrap; }
                .inline-group .tabular td.column-nombre { width: 300px !important; }
                .inline-group fieldset { border: none !important; border-top: 1px solid #eee !important; }
            </style>
        """)
        return super().get_inline_instances(request, obj)

    def nombre_con_indentacion(self, obj):
        level = obj.level
        indent = level * 20
        icon = "🏢" if level == 0 else "↳"
        color = "#1e293b" if level == 0 else "#64748b"
        weight = "700" if level == 0 else "400"
        
        return format_html(
            '<div style="text-indent: {0}px; color: {1}; font-weight: {2}; display: flex; align-items: center;">'
            '<span style="margin-right: 8px; opacity: 0.6; font-style: normal;">{3}</span> {4}'
            '</div>',
            indent, color, weight, icon, obj.nombre
        )
    nombre_con_indentacion.short_description = 'Ubicación'

    def total_hijos(self, obj):
        count = getattr(obj, '_hijos_count', obj.sub_ubicaciones.count())
        if count == 0:
            return mark_safe('<span style="color: #cbd5e1; font-size: 0.8rem;">Vacio</span>')
        return format_html('<span style="background: #f1f5f9; color: #475569; padding: 2px 10px; border-radius: 12px; font-weight: 700; font-size: 0.75rem;">{} sub-niveles</span>', count)
    total_hijos.short_description = 'Estructura'

    def total_activos(self, obj):
        # Contar activos en esta ubicación y todas sus descendientes
        from .models import Activo
        ubicaciones_ids = obj.get_descendants().values_list('id', flat=True)
        total = Activo.objects.filter(ubicacion_id__in=ubicaciones_ids).count()
        
        if total == 0:
            return mark_safe('<span style="color: #cbd5e1; font-size: 0.8rem;">Sin equipos</span>')
        return format_html('<span style="background: #eff6ff; color: #1d4ed8; padding: 2px 10px; border-radius: 12px; font-weight: 700; font-size: 0.75rem;">{} equipos</span>', total)
    total_activos.short_description = 'Carga de Activos'




# @admin.register(Activo) -> DESACTIVADO PARA FORZAR REGISTRO MANUAL AL FINAL
class ActivoAdminCustom(ImportExportActionModelAdmin):
    form = ActivoAdminForm
    list_per_page = 13  # MARCADOR VISUAL: Si ves 13 items por pagina, es este admin.
    resource_class = ActivoResource
    change_list_template = 'admin/activos/activo/change_list_custom.html'

    def export_admin_background(self, request):
        from django.http import JsonResponse
        from .models import ReporteGenerado
        from .tasks import generar_reporte_activos_task
        
        # Guardamos el query del admin tal como está
        cl = self.get_changelist_instance(request)
        queryset = cl.get_queryset(request)
        
        ids_list = list(queryset.values_list('id', flat=True))
        
        if not ids_list:
            return JsonResponse({'status': 'error', 'message': 'No hay activos para exportar con estos filtros.'}, status=400)
            
        reporte = ReporteGenerado.objects.create(
            usuario=request.user,
            nombre=f"Exportación ({len(ids_list)} activos)",
            estado='PENDIENTE'
        )
        
        # Despachar tarea enviando solo los IDs a exportar
        task = generar_reporte_activos_task.delay(reporte.id, query_ids=ids_list)
        reporte.task_id = task.id
        reporte.save(update_fields=['task_id'])
        
        return JsonResponse({
            'status': 'ok',
            'reporte_id': reporte.id,
            'message': 'El reporte se está generando en segundo plano.'
        })




    def get_import_resource_kwargs(self, request, *args, **kwargs):
        return {'user': request.user}
    
    def get_export_resource_kwargs(self, request, *args, **kwargs):
        return {'user': request.user}


    def import_background(self, request):
        context = {
            **self.admin_site.each_context(request),
            'title': 'Importación masiva de Activos (Background)',
        }
        return render(request, 'admin/activos/activo/background_import.html', context)

    def import_process(self, request):
        if request.method == 'POST' and request.FILES.get('import_file'):
            import os
            import uuid
            from django.core.files.storage import default_storage
            from django.core.files.base import ContentFile
            from django.http import JsonResponse
            from .tasks import import_activos_task
            
            myfile = request.FILES['import_file']
            file_name = myfile.name
            file_format = file_name.split('.')[-1].lower()
            
            import_id = str(uuid.uuid4())
            temp_path = f'tmp/activo_imp_{import_id}.{file_format}'
            
            # Guardar el archivo temporalmente
            path = default_storage.save(temp_path, ContentFile(myfile.read()))
            
            # Obtener path absoluto para Celery
            try:
                abs_path = default_storage.path(path)
            except NotImplementedError:
                abs_path = path

            # Tarea Celery con el ID de usuario para el progreso en caché
            task = import_activos_task.delay(abs_path, file_format, user_id=request.user.id, import_name=f"Importación {file_name}")
            
            return JsonResponse({
                'status': 'started',
                'task_id': task.id
            })
            
        return JsonResponse({'status': 'error', 'message': 'No se recibió archivo'}, status=400)

    def import_progress(self, request):
        from celery.result import AsyncResult
        from django.http import JsonResponse
        from django.core.cache import cache
        
        task_id = request.GET.get('task_id')
        if not task_id:
            return JsonResponse({'status': 'error', 'message': 'Falta task_id'}, status=400)
            
        res = AsyncResult(task_id)
        
        # Intentar obtener info detallada desde caché (actualizada por la tarea)
        cache_data = cache.get(f"import_progress_{request.user.id}")
        
        response_data = {
            'state': res.state,
            'status': 'Procesando...',
            'percent': 0
        }
        
        if cache_data:
            if isinstance(cache_data, dict):
                response_data.update(cache_data)
                # Calcular porcentaje si no viene
                if 'current' in cache_data and 'total' in cache_data and cache_data['total'] > 0:
                    response_data['percent'] = int((cache_data['current'] / cache_data['total']) * 100)
            else:
                response_data['percent'] = cache_data

        if res.state == 'SUCCESS':
            if isinstance(res.result, dict):
                response_data.update(res.result)
            response_data['state'] = 'COMPLETED'
            response_data['percent'] = 100
        elif res.state == 'FAILURE':
            response_data['error'] = str(res.result)
            
        return JsonResponse(response_data)


    class NombreStartsWithFilter(admin.SimpleListFilter):
        title = 'Nombre comienza con'
        parameter_name = 'nombre_starts_with'

        def lookups(self, request, model_admin):
            # 0-9
            lookups = [('0-9', '0-9 (Números)')]
            # A-Z
            import string
            for char in string.ascii_uppercase:
                lookups.append((char, char))
            return lookups

        def queryset(self, request, queryset):
            if self.value() == '0-9':
                # Filtra nombres que empiezan con dígito
                return queryset.filter(nombre__regex=r'^\d')
            elif self.value():
                # Filtra por la letra seleccionada (case insensitive)
                return queryset.filter(nombre__istartswith=self.value())
            return queryset



    
    list_display = ('nombre', 'ver_en_fiori', 'codigo_interno', 'get_categoria', 'mt_mtbf', 'mt_total_downtime', 'epc', 'descripcion', 'ultima_auditoria_display', 'get_marca_modelo', 'serie', 'get_plano_codigo', 'referencia', 'get_ubicacion_ruta')
    list_filter = (
        NombreStartsWithFilter,
        ActivoFaltantesFilter, 
        'estado', 
        ('familia', admin.RelatedOnlyFieldListFilter),
        ('modelo__categoria', admin.RelatedOnlyFieldListFilter),
        ('modelo__marca', admin.RelatedOnlyFieldListFilter),
        ('responsable', admin.RelatedOnlyFieldListFilter),
        'creado_en', 
        UbicacionHierarchyFilter
    )
    # Optimización: Mantenemos select_related para evitar N+1 en las columnas personalizadas
    list_select_related = (
        'modelo__marca', 
        'modelo__categoria', 
        'ubicacion', 
        'ubicacion__padre',
        'ubicacion__padre__padre',
        'ubicacion__padre__padre__padre',
        'responsable', 
        'padre', 
        'familia',
        'plano'
    )
    search_fields = ('nombre', 'descripcion', 'codigo_interno', 'epc', 'serie', 'referencia', 'familia__nombre', 'plano__nombre', 'modelo__marca__nombre', 'modelo__nombre', 'marca_legacy', 'modelo_legacy', 'ubicacion__nombre', 'ubicacion_legacy')
    autocomplete_fields = ('familia', 'modelo', 'ubicacion', 'responsable', 'padre', 'plano')


    inlines = [ComponenteActivoInline, PuntoMedicionInline, DocumentoMedicionInline, AuditoriasActivoInline]
    readonly_fields = ('mt_mtbf', 'mt_total_downtime', 'historial_paradas_table', 'ultima_auditoria_display', 'get_marca', 'get_categoria_display', 'get_ubicacion_ruta', 'get_modelo_img', 'ver_en_plano', 'rutinas_aplicables', 'ordenes_programadas', 'historial_ordenes', 'tickets_asociados', 'crear_aviso_link', 'get_puntos_medicion_summary')
    actions = ['export_admin_action', 'export_direct_xlsx', 'export_streaming_csv', 'limpiar_todo_el_inventario']

    @admin.action(description="BORRADO RÁPIDO: Eliminar selección actual (evita error de límites)")
    def limpiar_todo_el_inventario(self, request, queryset):
        """
        Borra los activos seleccionados usando .delete() de QuerySet.
        Esto es mucho más rápido y evita el error TooManyFieldsSent porque
        no intenta construir la página de confirmación con miles de objetos.
        """
        count = queryset.count()
        queryset.delete()
        self.message_user(request, f"Se han eliminado {count} activos correctamente.")

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related(
            *self.list_select_related
        ).only(
            # Campos del modelo Activo necesarios para list_display
            'id', 'nombre', 'codigo_interno', 'epc', 'descripcion', 'serie', 'referencia',
            'marca_legacy', 'modelo_legacy',
            # FKs necesarias
            'modelo_id', 'ubicacion_id', 'plano_id', 'responsable_id', 'padre_id', 'familia_id',
            # Campos de modelo relacionado (select_related)
            'modelo__marca__nombre', 'modelo__nombre', 'modelo__categoria_id',
            'ubicacion__nombre', 'ubicacion__padre_id',
            'ubicacion__padre__nombre', 'ubicacion__padre__padre_id',
            'ubicacion__padre__padre__nombre', 'ubicacion__padre__padre__padre_id',
            'plano__nombre', 'plano__numero_documento'
        ).prefetch_related('pines_planos__visor').annotate(
            ultima_auditoria_fecha=Max('auditorias_participadas__fecha_escaneo')
        )
        
        # --- Lógica de Filtros Dinámicos (Dynamic Table Filters) ---
        dtf_param = request.GET.get('_dtf')
        if dtf_param:
            import json
            from django.db.models import Q
            try:
                filters = json.loads(dtf_param)
                # filters es una lista de objetos: {field, operator, value}
                if isinstance(filters, list):
                    q_object = Q()
                    for f in filters:
                        field = f.get('field')
                        operator = f.get('operator')
                        value = f.get('value')
                        
                        if not field or not operator:
                            continue
                            
                        # Mapeo de operadores a lookups de Django
                        lookup = ""
                        if operator == 'contains':
                            lookup = f"{field}__icontains"
                        elif operator == 'equals':
                            lookup = f"{field}__iexact"
                        elif operator == 'gt':
                            lookup = f"{field}__gt"
                        elif operator == 'lt':
                            lookup = f"{field}__lt"
                        elif operator == 'gte':
                            lookup = f"{field}__gte"
                        elif operator == 'lte':
                            lookup = f"{field}__lte"
                        elif operator == 'startswith':
                            lookup = f"{field}__istartswith"
                        elif operator == 'endswith':
                            lookup = f"{field}__iendswith"
                            
                        if lookup:
                            # Manejo especial para fechas o números si es necesario
                            # Por ahora asumimos que el string value funciona (Django lo casta usualmente)
                            q_object &= Q(**{lookup: value})
                    
                    qs = qs.filter(q_object)
            except Exception as e:
                print(f"Error parsing Dynamic Filters: {e}")
                pass
                
        return qs

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        # Pasamos campos disponibles para el filtro dinámico
        extra_context['available_filter_fields'] = [
            {'name': 'nombre', 'label': 'Nombre', 'type': 'text'},
            {'name': 'descripcion', 'label': 'Descripción', 'type': 'text'},
            {'name': 'codigo_interno', 'label': 'Código Interno', 'type': 'text'},
            {'name': 'epc', 'label': 'Código EPC', 'type': 'text'},
            {'name': 'serie', 'label': 'N° Serie', 'type': 'text'},
            {'name': 'modelo__marca__nombre', 'label': 'Marca', 'type': 'text'},
            {'name': 'modelo__nombre', 'label': 'Modelo', 'type': 'text'},
            {'name': 'ubicacion__nombre', 'label': 'Ubicación', 'type': 'text'},
            {'name': 'costo', 'label': 'Costo', 'type': 'number'},
            {'name': 'fecha_compra', 'label': 'Fecha Compra', 'type': 'date'},
            {'name': 'estado', 'label': 'Estado', 'type': 'select', 'options': [
                {'val': 'OPERATIVO', 'label': 'Operativo'},
                {'val': 'MANTENIMIENTO', 'label': 'Mantenimiento'},
                {'val': 'REPARACION', 'label': 'Reparación'},
                {'val': 'OBSOLETO', 'label': 'Obsoleto'},
            ]},
            {'name': 'creado_en', 'label': 'Fecha Creación', 'type': 'date'},
            {'name': 'actualizado_en', 'label': 'Última Modificación', 'type': 'date'},
        ]
        return super().changelist_view(request, extra_context=extra_context)

    def export_admin_action(self, request, queryset):
        """Redirección con descripción personalizada (2 pasos)"""
        return super().export_admin_action(request, queryset)
    export_admin_action.short_description = "Exportar activos seleccionados"

    @admin.action(description="⬇️ Descarga Directa Excel (Completo y Rápido)")
    def export_direct_xlsx(self, request, queryset):
        """Exportación en un solo paso con todos los campos necesarios para edición masiva"""
        try:
            from django.utils import timezone
            # Usar la clase del recurso directamente ya que el método dinámico falló
            resource_class = self.get_export_resource_class() if hasattr(self, 'get_export_resource_class') else self.resource_class
            
            # CRITICAL FIX: El get_queryset usa .only() que difiere campos como costo y fecha_compra.
            # Al exportar, el resource accede a estos campos, causando un refresh_from_db por CADA fila (N+1 masivo).
            # .defer(None) borra cualquier deferral anterior, cargando todos los campos de inmediato.
            if hasattr(queryset, 'defer'):
                queryset = queryset.defer(None)
                
            resource = resource_class(**self.get_export_resource_kwargs(request))
            dataset = resource.export(queryset)
            
            fecha = timezone.now().strftime('%Y%m%d_%H%M')
            response = HttpResponse(
                dataset.xlsx, 
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename="export_activos_{fecha}.xlsx"'
            return response
        except Exception as e:
            self.message_user(request, f"Error en exportación directa: {str(e)}", messages.ERROR)
            return None

    @admin.action(description="⚡ Exportar CSV Streaming (Rápido - 85k+ registros)")
    def export_streaming_csv(self, request, queryset):
        """
        Exporta datos en CSV usando StreamingHttpResponse para evitar timeouts
        y uso excesivo de memoria con grandes volúmenes de datos.
        Optimización: 
        1. Carga mapa de ubicaciones en memoria para evitar N+1 recursivo en __str__.
        2. Usa values_list para evitar instanciación de modelos.
        """
        import csv
        from django.http import StreamingHttpResponse
        from .models.ubicacion import Ubicacion
        from .models.foto_ubicacion import FotoUbicacion

        # Clase auxiliar para escribir en el buffer de respuesta
        class Echo:
            def write(self, value):
                return value

        # 1. Pre-calcular mapa de ubicaciones (Full Path)
        # Esto reduce 250k+ queries a 1 query + procesamiento en memoria
        # Asumimos que el número de ubicaciones no es masivo (<10k) comparado con activos
        def build_location_map():
            # Traemos todas las ubicaciones: id, nombre, padre
            locs = list(Ubicacion.objects.values('id', 'nombre', 'padre_id'))
            loc_dict = {l['id']: l for l in locs}
            full_path_map = {}

            def get_path(loc_id, depth=0):
                if loc_id in full_path_map:
                    return full_path_map[loc_id]
                if depth > 20: return "[Max Depth]" # Evitar bucles infinitos
                
                node = loc_dict.get(loc_id)
                if not node: return ""
                
                name = node['nombre']
                parent_id = node['padre_id']
                
                if parent_id:
                    path = f"{get_path(parent_id, depth+1)} → {name}"
                else:
                    path = name
                
                full_path_map[loc_id] = path
                return path

            for l in locs:
                get_path(l['id'])
            
            return full_path_map

        # Generador optimizado
        def rows_generator(queryset):
            # Excel needs BOM to recognize UTF-8
            yield [u'\ufeffID', 'Codigo Interno', 'EPC', 'Nombre', 'Descripcion', 'Referencia', 'Marca', 'Modelo', 
                'Serie', 'Estado', 'Ubicacion', 'Plano', 'Responsable', 'Costo', 'Fecha Compra']

            # Pre-load cache
            loc_map = build_location_map()
            
            # Use values_list for maximum speed (no model instances)
            # Fkeys: modelo__marca__nombre, modelo__nombre, ubicacion_id, responsable__username
            values = queryset.values_list(
                'id',
                'codigo_interno',
                'epc',
                'nombre',
                'descripcion',
                'referencia',
                'modelo__marca__nombre',
                'modelo__nombre',
                'marca_legacy', # fallback
                'modelo_legacy', # fallback
                'serie',
                'estado',
                'ubicacion_id',
                'ubicacion_legacy', # fallback
                'plano__nombre',
                'plano__numero_documento',
                'responsable__username',
                'costo',
                'fecha_compra'
            ).iterator(chunk_size=5000)

            # ESTADO MAPPING
            estado_map = dict(self.model.ESTADO_CHOICES)

            for row in values:
                # Unpack tuple efficiently
                (rid, code, epc_val, name, desc, ref, m_brand, m_model, m_brand_leg, m_model_leg, 
                 serie, status, loc_id, loc_leg, pl_name, pl_doc, resp, cost, date) = row

                # Logic for fallbacks
                final_brand = m_brand if m_brand else (m_brand_leg or '')
                final_model = f"{final_brand} - {m_model}" if m_model else (m_model_leg or '')
                
                final_loc = loc_map.get(loc_id, "") if loc_id else (loc_leg or '')
                final_status = estado_map.get(status, status)

                yield [
                    str(rid),
                    code or '',
                    epc_val or '',
                    name or '',
                    desc or '',
                    ref or '',
                    final_brand,
                    final_model,
                    serie or '',
                    final_status,
                    final_loc,
                    pl_doc or pl_name or '',
                    resp or '',
                    str(cost) if cost is not None else '',
                    str(date) if date else '',
                ]

        pseudo_buffer = Echo()
        writer = csv.writer(pseudo_buffer)
        
        response = StreamingHttpResponse(
            (writer.writerow(row) for row in rows_generator(queryset)),
            content_type="text/csv"
        )
        
        from django.utils import timezone
        fecha = timezone.now().strftime('%Y%m%d_%H%M')
        response['Content-Disposition'] = f'attachment; filename="export_activos_fast_{fecha}.csv"'
        return response

    def rutinas_aplicables(self, obj):
        if not obj.modelo or not obj.modelo.categoria:
            return mark_safe('<span style="color: #94a3b8; font-style: italic;">No hay una categoría de activo definida para este modelo.</span>')
        
        cat = obj.modelo.categoria
        from mantenimiento.models import Rutina, Tipo

        # Obtener todos los Tipos vinculados a esta categoría
        tipo_ids = set(Tipo.objects.filter(categoria_activo=cat).values_list('id', flat=True))

        # También buscar por el reverse relation (mantenimiento_tipo)
        m_cat_mgr = getattr(cat, 'mantenimiento_tipo', None)
        if m_cat_mgr is not None:
            tipo_ids.update(m_cat_mgr.values_list('id', flat=True))

        # Obtener ancestros de todos esos tipos (jerarquía padre)
        all_tipo_ids = set(tipo_ids)
        queue = list(tipo_ids)
        while queue:
            children = Tipo.objects.filter(padre_id__in=queue).values_list('id', flat=True)
            new_ids = set(children) - all_tipo_ids
            all_tipo_ids.update(new_ids)
            queue = list(new_ids)

        # Buscar rutinas vinculadas por tipo (jerarquía) O directamente por categoria_activo
        q = Q(categoria_activo=cat)
        if all_tipo_ids:
            q |= Q(tipo_id__in=all_tipo_ids)
        rutinas = Rutina.objects.filter(q).select_related('frecuencia', 'tipo')
        
        if not rutinas.exists():
            return format_html('<span style="color: #94a3b8; font-style: italic;">No hay rutinas de mantenimiento configuradas para la categoría "{0}".</span>', obj.modelo.categoria.nombre)
            
        html = '<div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; margin-top: 10px;">'
        html += '<table style="width: 100%; border-collapse: collapse; font-size: 0.85rem;">'
        html += '<thead style="background: #f8fafc; border-bottom: 2px solid #e2e8f0;">'
        html += '<tr>'
        html += '<th style="text-align: left; padding: 12px 15px; color: #475569; font-weight: 700;">Rutina</th>'
        html += '<th style="text-align: center; padding: 12px 15px; color: #475569; font-weight: 700;">Frecuencia</th>'
        html += '<th style="text-align: center; padding: 12px 15px; color: #475569; font-weight: 700;">HH/Técnicos</th>'
        html += '<th style="text-align: center; padding: 12px 15px; color: #475569; font-weight: 700;">Acción</th>'
        html += '</tr></thead><tbody>'
        
        for r in rutinas:
            frec_nombre = r.frecuencia.nombre if r.frecuencia else "N/A"
            hh = r.tiempo_estimado if r.tiempo_estimado else "---"
            tecs = r.cantidad_tecnicos
            
            html += f'<tr style="border-bottom: 1px solid #f1f5f9;">'
            html += f'<td style="padding: 12px 15px;">'
            html += f'<div style="font-weight: 600; color: #1e293b;">{r.nombre}</div>'
            html += f'<div style="font-size: 0.75rem; color: #64748b;">{r.tipo.nombre if r.tipo else "General"}</div>'
            html += f'</td>'
            html += f'<td style="padding: 12px 15px; text-align: center;">'
            html += f'<span style="background: #eff6ff; color: #2563eb; padding: 4px 10px; border-radius: 12px; font-weight: 600; font-size: 0.75rem;">{frec_nombre}</span>'
            html += f'</td>'
            html += f'<td style="padding: 12px 15px; text-align: center; color: #475569;">'
            html += f'{hh} <br> <small style="color: #94a3b8;">({tecs} Tec.)</small>'
            html += f'</td>'
            html += f'<td style="padding: 12px 15px; text-align: center;">'
            html += f'<a href="/admin/mantenimiento/rutina/{r.id}/change/" target="_blank" style="background: #f1f5f9; color: #475569; padding: 5px; border-radius: 4px; display: inline-flex; align-items: center; border: 1px solid #e2e8f0; text-decoration: none;">'
            html += f'<ion-icon name="open-outline" style="font-size: 1rem;"></ion-icon>'
            html += '</a></td></tr>'
        
        html += '</tbody></table></div>'
        return mark_safe(html)

    def ordenes_programadas(self, obj):
        from mantenimiento.models import OrdenTrabajo
        from django.utils import timezone
        
        # Obtener órdenes vigentes (no terminadas ni canceladas)
        ordenes_all = obj.ordenes_trabajo.filter(
            estado__in=['ESPERA', 'PROGRAMADA', 'EJECUCION']
        ).select_related('rutina', 'tecnico', 'programacion').order_by('inicio_programado')
        
        count_total = ordenes_all.count()
        ordenes = ordenes_all[:10]

        if not ordenes.exists():
            return mark_safe('<div style="color: #94a3b8; font-style: italic; padding: 10px; background: #f8fafc; border: 1px dashed #cbd5e1; border-radius: 8px;">No hay órdenes de trabajo programadas pendientes para este equipo.</div>')

        html = '<div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; margin-top: 10px;">'
        html += '<table style="width: 100%; border-collapse: collapse; font-size: 0.85rem;">'
        html += '<thead style="background: #f8fafc; border-bottom: 2px solid #e2e8f0;">'
        html += '<tr>'
        html += '<th style="text-align: left; padding: 12px 15px; color: #475569; font-weight: 700;">OT #</th>'
        html += '<th style="text-align: left; padding: 12px 15px; color: #475569; font-weight: 700;">Rutina / Motivo</th>'
        html += '<th style="text-align: center; padding: 12px 15px; color: #475569; font-weight: 700;">Programado</th>'
        html += '<th style="text-align: center; padding: 12px 15px; color: #475569; font-weight: 700;">Estado</th>'
        html += '<th style="text-align: center; padding: 12px 15px; color: #475569; font-weight: 700;">Acción</th>'
        html += '</tr></thead><tbody>'

        for ot in ordenes:
            inicio = timezone.localtime(ot.inicio_programado).strftime('%d/%m/%Y %H:%M')
            fin = timezone.localtime(ot.fin_programado).strftime('%H:%M')
            
            # Color según estado
            color = '#3b82f6' if ot.estado == 'PROGRAMADA' else '#10b981'
            bg_color = '#eff6ff' if ot.estado == 'PROGRAMADA' else '#ecfdf5'
            
            desc = ot.rutina.nombre if ot.rutina else (ot.aviso.descripcion[:50] if ot.aviso else "Sin descripción")
            tecnico = ot.tecnico.get_full_name() or ot.tecnico.username if ot.tecnico else "Sin asignar"

            html += f'<tr style="border-bottom: 1px solid #f1f5f9;">'
            html += f'<td style="padding: 12px 15px; font-weight: 700; color: #1e293b;">{ot.id}</td>'
            html += f'<td style="padding: 12px 15px;">'
            html += f'<div style="font-weight: 600; color: #1e293b;">{desc}</div>'
            html += f'<div style="font-size: 0.75rem; color: #64748b;">Asignado a: {tecnico}</div>'
            html += f'</td>'
            html += f'<td style="padding: 12px 15px; text-align: center; color: #475569;">'
            html += f'<div style="font-weight: 600;">{inicio}</div>'
            html += f'<div style="font-size: 0.7rem; color: #94a3b8;">Finaliza aprox: {fin}</div>'
            html += f'</td>'
            html += f'<td style="padding: 12px 15px; text-align: center;">'
            html += f'<span style="background: {bg_color}; color: {color}; padding: 4px 10px; border-radius: 12px; font-weight: 600; font-size: 0.75rem; border: 1px solid {color}40;">{ot.get_estado_display()}</span>'
            html += f'</td>'
            html += f'<td style="padding: 12px 15px; text-align: center;">'
            html += f'<a href="/admin/mantenimiento/ordentrabajo/{ot.id}/change/" target="_blank" style="background: #f1f5f9; color: #475569; padding: 5px; border-radius: 4px; display: inline-flex; align-items: center; border: 1px solid #e2e8f0; text-decoration: none;">'
            html += f'<ion-icon name="open-outline" style="font-size: 1rem;"></ion-icon>'
            html += '</a></td></tr>'

        html += '</tbody></table>'
        
        if count_total > 10:
            url = f"/admin/mantenimiento/ordentrabajo/?activos__id__exact={obj.id}&estado__in=ESPERA,PROGRAMADA,EJECUCION"
            html += f'<div style="padding: 10px; text-align: center; border-top: 1px solid #e2e8f0; background: #f8fafc;">'
            html += f'<a href="{url}" target="_blank" style="color: #2563eb; font-weight: 600; text-decoration: none; font-size: 0.8rem;">Ver las {count_total} órdenes pendientes →</a>'
            html += '</div>'
            
        html += '</div>'
        return mark_safe(html)
    ordenes_programadas.short_description = "Órdenes de Trabajo Pendientes"

    def historial_ordenes(self, obj):
        from mantenimiento.models import OrdenTrabajo
        from django.utils import timezone
        
        # Obtener órdenes terminadas o canceladas
        ordenes_all = obj.ordenes_trabajo.filter(
            estado__in=['REALIZADA', 'CANCELADA']
        ).select_related('rutina', 'tecnico').order_by('-inicio_programado')
        
        count_total = ordenes_all.count()
        ordenes = ordenes_all[:10]

        if not ordenes.exists():
            return mark_safe('<div style="color: #94a3b8; font-style: italic; padding: 10px; background: #f8fafc; border: 1px dashed #cbd5e1; border-radius: 8px;">No hay historial de órdenes de trabajo para este equipo.</div>')

        html = '<div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; margin-top: 10px;">'
        html += '<table style="width: 100%; border-collapse: collapse; font-size: 0.85rem;">'
        html += '<thead style="background: #f8fafc; border-bottom: 2px solid #e2e8f0;">'
        html += '<tr>'
        html += '<th style="text-align: left; padding: 12px 15px; color: #475569; font-weight: 700;">OT #</th>'
        html += '<th style="text-align: left; padding: 12px 15px; color: #475569; font-weight: 700;">Rutina / Motivo</th>'
        html += '<th style="text-align: center; padding: 12px 15px; color: #475569; font-weight: 700;">Fecha</th>'
        html += '<th style="text-align: center; padding: 12px 15px; color: #475569; font-weight: 700;">Estado</th>'
        html += '<th style="text-align: center; padding: 12px 15px; color: #475569; font-weight: 700;">Acción</th>'
        html += '</tr></thead><tbody>'

        for ot in ordenes:
            fecha = timezone.localtime(ot.inicio_programado).strftime('%d/%m/%Y')
            
            # Color según estado
            color = '#10b981' if ot.estado == 'REALIZADA' else '#ef4444'
            bg_color = '#ecfdf5' if ot.estado == 'REALIZADA' else '#fef2f2'
            
            desc = ot.rutina.nombre if ot.rutina else (ot.aviso.descripcion[:50] if ot.aviso else "Sin descripción")
            tecnico = ot.tecnico.get_full_name() or ot.tecnico.username if ot.tecnico else "Sin asignar"

            html += f'<tr style="border-bottom: 1px solid #f1f5f9;">'
            html += f'<td style="padding: 12px 15px; font-weight: 700; color: #1e293b;">{ot.id}</td>'
            html += f'<td style="padding: 12px 15px;">'
            html += f'<div style="font-weight: 600; color: #1e293b;">{desc}</div>'
            html += f'<div style="font-size: 0.75rem; color: #64748b;">Técnico: {tecnico}</div>'
            html += f'</td>'
            html += f'<td style="padding: 12px 15px; text-align: center; color: #475569;">'
            html += f'<div style="font-weight: 600;">{fecha}</div>'
            html += f'</td>'
            html += f'<td style="padding: 12px 15px; text-align: center;">'
            html += f'<span style="background: {bg_color}; color: {color}; padding: 4px 10px; border-radius: 12px; font-weight: 600; font-size: 0.75rem; border: 1px solid {color}40;">{ot.get_estado_display()}</span>'
            html += f'</td>'
            html += f'<td style="padding: 12px 15px; text-align: center;">'
            html += f'<a href="/admin/mantenimiento/ordentrabajo/{ot.id}/change/" target="_blank" style="background: #f1f5f9; color: #475569; padding: 5px; border-radius: 4px; display: inline-flex; align-items: center; border: 1px solid #e2e8f0; text-decoration: none;">'
            html += f'<ion-icon name="open-outline" style="font-size: 1rem;"></ion-icon>'
            html += '</a></td></tr>'

        html += '</tbody></table>'
        
        if count_total > 10:
            url = f"/admin/mantenimiento/ordentrabajo/?activos__id__exact={obj.id}&estado__in=REALIZADA,CANCELADA"
            html += f'<div style="padding: 10px; text-align: center; border-top: 1px solid #e2e8f0; background: #f8fafc;">'
            html += f'<a href="{url}" target="_blank" style="color: #2563eb; font-weight: 600; text-decoration: none; font-size: 0.8rem;">Ver historial completo ({count_total} órdenes) →</a>'
            html += '</div>'
            
        html += '</div>'
        return mark_safe(html)
    historial_ordenes.short_description = "Historial de Órdenes de Trabajo"

    def tickets_asociados(self, obj):
        from mantenimiento.models import Aviso
        avisos = Aviso.objects.filter(activo=obj).order_by('-creado_en')
        
        if not avisos.exists():
            return mark_safe('<div style="color: #94a3b8; font-style: italic; padding: 10px; background: #f8fafc; border: 1px dashed #cbd5e1; border-radius: 8px;">No hay avisos/tickets reportados para este equipo.</div>')

        html = '<div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; margin-top: 10px;">'
        html += '<table style="width: 100%; border-collapse: collapse; font-size: 0.85rem;">'
        html += '<thead style="background: #f8fafc; border-bottom: 2px solid #e2e8f0;">'
        html += '<tr>'
        html += '<th style="text-align: left; padding: 12px 15px; color: #475569; font-weight: 700;">Ticket #</th>'
        html += '<th style="text-align: left; padding: 12px 15px; color: #475569; font-weight: 700;">Descripción</th>'
        html += '<th style="text-align: center; padding: 12px 15px; color: #475569; font-weight: 700;">Prioridad</th>'
        html += '<th style="text-align: center; padding: 12px 15px; color: #475569; font-weight: 700;">Estado</th>'
        html += '<th style="text-align: center; padding: 12px 15px; color: #475569; font-weight: 700;">Fecha</th>'
        html += '<th style="text-align: center; padding: 12px 15px; color: #475569; font-weight: 700;">Acción</th>'
        html += '</tr></thead><tbody>'

        for av in avisos:
            fecha = av.creado_en.strftime('%d/%m/%Y')
            
            # Colores para prioridad
            prio_color = {
                'BAJA': '#64748b',
                'MEDIA': '#3b82f6',
                'ALTA': '#f59e0b',
                'CRITICA': '#ef4444'
            }.get(av.prioridad, '#000')
            
            # Colores para estado
            est_color = {
                'ABIERTO': '#ef4444',
                'PROCESO': '#3b82f6',
                'CERRADO': '#10b981',
                'CANCELADO': '#64748b'
            }.get(av.estado, '#000')

            html += f'<tr style="border-bottom: 1px solid #f1f5f9;">'
            html += f'<td style="padding: 12px 15px; font-weight: 700; color: #1e293b;">AV-{av.id}</td>'
            html += f'<td style="padding: 12px 15px;">'
            html += f'<div style="font-weight: 600; color: #1e293b;">{av.get_tipo_display()}</div>'
            html += f'<div style="font-size: 0.75rem; color: #64748b;">{av.descripcion[:100]}{"..." if len(av.descripcion) > 100 else ""}</div>'
            html += f'</td>'
            html += f'<td style="padding: 12px 15px; text-align: center;">'
            html += f'<span style="color: {prio_color}; font-weight: 700;">{av.get_prioridad_display()}</span>'
            html += f'</td>'
            html += f'<td style="padding: 12px 15px; text-align: center;">'
            html += f'<span style="background: {est_color}15; color: {est_color}; padding: 4px 10px; border-radius: 12px; font-weight: 600; font-size: 0.75rem;">{av.get_estado_display()}</span>'
            html += f'</td>'
            html += f'<td style="padding: 12px 15px; text-align: center; color: #475569;">{fecha}</td>'
            html += f'<td style="padding: 12px 15px; text-align: center;">'
            html += f'<a href="/admin/mantenimiento/aviso/{av.id}/change/" target="_blank" style="background: #f1f5f9; color: #475569; padding: 5px; border-radius: 4px; display: inline-flex; align-items: center; border: 1px solid #e2e8f0; text-decoration: none;">'
            html += f'<ion-icon name="open-outline" style="font-size: 1rem;"></ion-icon>'
            html += '</a></td></tr>'

        html += '</tbody></table></div>'
        return mark_safe(html)
    tickets_asociados.short_description = "Avisos / Tickets Asociados"

    def crear_aviso_link(self, obj):
        if not obj.id: return "-"
        url = f"/admin/mantenimiento/aviso/add/?activo={obj.id}"
        if obj.ubicacion:
            url += f"&ubicacion={obj.ubicacion.id}"
            
        return format_html(
            '<a href="{0}" class="button" style="background: #ef4444; color: white; padding: 10px 20px; border-radius: 6px; font-weight: bold; text-decoration: none; display: inline-flex; align-items: center; gap: 8px; border: none; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);">'
            '<ion-icon name="alert-circle-outline" style="font-size: 1.2rem;"></ion-icon>'
            'Reportar Falla / Mal Funcionamiento'
            '</a>',
            url
        )
    crear_aviso_link.short_description = 'Reporte de Falla'
    
    def get_ubicacion_ruta(self, obj):
        if obj.ubicacion:
            return obj.ubicacion.ruta_completa
        return obj.ubicacion_legacy or "---"
    get_ubicacion_ruta.short_description = 'Ubicación Jerárquica'

    def get_modelo_img(self, obj):
        if obj.modelo and obj.modelo.imagen:
            return format_html('<img src="{}" style="max-width: 300px; max-height: 300px; border-radius: 8px; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);" />', obj.modelo.imagen)
        return mark_safe('<span style="color: #94a3b8; font-style: italic;">El modelo no tiene imagen asociada</span>')
    get_modelo_img.short_description = 'Imagen del Modelo'

    def get_parent_info(self, obj):
        if obj.padre:
            return format_html('<span style="color: #64748b; font-size: 0.85rem;">↳ {}</span>', obj.padre.nombre)
        return mark_safe('<span style="color: #10b981; font-weight: bold; font-size: 0.75rem;">PRINCIPAL</span>')
    get_parent_info.short_description = 'Jerarquía'

    def changelist_view(self, request, extra_context=None):
        if request.GET.get('_popup'):
            from .models import Ubicacion, Activo
            
            # Obtener todas las ubicaciones en orden alfabético (MPTT removido)
            ubicaciones = Ubicacion.objects.all().order_by('nombre')
            
            # Obtener activos base (ignorando filtros del admin que puedan restringir el popup involuntariamente)
            queryset = Activo.objects.all().select_related('ubicacion', 'categoria')
            
            # El popup de Django envía el término de búsqueda en 'q'
            search_term = request.GET.get('q')
            if search_term:
                queryset = queryset.filter(
                    models.Q(nombre__icontains=search_term) | 
                    models.Q(codigo_interno__icontains=search_term) |
                    models.Q(epc__icontains=search_term) |
                    models.Q(serie__icontains=search_term)
                )

            # Organizar datos para el árbol: {"ubicacion_id": {"categoria_id": {"nombre": '...', activos: []}}}
            tree_data = {}
            for activo in queryset:
                if not activo.ubicacion: continue
                u_id = str(activo.ubicacion.id)
                cat = activo.modelo.categoria if activo.modelo else None
                c_id = str(cat.id) if cat else "0"
                c_nombre = cat.nombre if cat else "Sin Categoría"
                
                if u_id not in tree_data:
                    tree_data[u_id] = {}
                if c_id not in tree_data[u_id]:
                    tree_data[u_id][c_id] = {'nombre': c_nombre, 'activos': []}
                
                tree_data[u_id][c_id]['activos'].append({
                    'id': activo.id,
                    'nombre': activo.nombre,
                    'codigo_interno': activo.codigo_interno or 'S/C',
                    'estado': activo.get_estado_display()
                })

            extra_context = extra_context or {}
            extra_context.update({
                'tree_data': tree_data,
                'ubicaciones': ubicaciones,
                'is_popup': True,
                'title': 'Seleccionar Activo (Explorador Jerárquico)'
            })
            # Cambiar la plantilla solo para el popup
            self.change_list_template = 'admin/activos/activo/lookup_tree.html'
            
        else:
            # Restaurar la plantilla de importación/exportación si no es popup
            self.change_list_template = 'admin/activos/activo/change_list_custom.html'
            
        return super().changelist_view(request, extra_context=extra_context)
    
    def mt_mtbf(self, obj):
        val = obj.get_mtbf()
        if val is None: return "-"
        return f"{val:.1f} h"
    mt_mtbf.short_description = "MTBF (h)"

    def mt_total_downtime(self, obj):
        return f"{obj.get_total_downtime():.1f} h"
    mt_total_downtime.short_description = "Downtime Total"

    def historial_paradas_table(self, obj):
        paradas = obj.historial_paradas.all()[:10]
        if not paradas.exists():
            return "No hay paradas registradas"
        
        html = '<table style="width:100%; border-collapse: collapse; font-size: 0.85rem;">'
        html += '<thead style="background:#f1f5f9;"><tr>'
        html += '<th style="padding:8px; text-align:left;">Inicio</th>'
        html += '<th style="padding:8px; text-align:left;">Fin</th>'
        html += '<th style="padding:8px; text-align:center;">Horas</th>'
        html += '<th style="padding:8px; text-align:left;">Motivo</th>'
        html += '</tr></thead><tbody>'
        for p in paradas:
            fin = p.fin.strftime('%d/%m/%Y %H:%M') if p.fin else '<span style="color:red; font-weight:bold;">En curso</span>'
            html += f'<tr style="border-bottom:1px solid #eee;">'
            html += f'<td style="padding:8px;">{p.inicio.strftime("%d/%m/%Y %H:%M")}</td>'
            html += f'<td style="padding:8px;">{fin}</td>'
            html += f'<td style="padding:8px; text-align:center;">{p.duracion_horas:.1f}</td>'
            html += f'<td style="padding:8px;">{p.motivo or ""}</td></tr>'
        html += '</tbody></table>'
        return mark_safe(html)
    historial_paradas_table.short_description = "Historial de Paradas"
    
    def get_categoria(self, obj):
        if obj.modelo and obj.modelo.categoria:
            return obj.modelo.categoria
        return "---"
    get_categoria.short_description = 'Categoría'

    def get_marca(self, obj):
        if obj.modelo:
            return obj.modelo.marca
        return obj.marca_legacy
    get_marca.short_description = 'Marca'

    @admin.display(description="Marca -> Modelo", ordering='modelo__marca__nombre')
    def get_marca_modelo(self, obj):
        marca = obj.modelo.marca.nombre if obj.modelo and obj.modelo.marca else (obj.marca_legacy or "---")
        modelo = obj.modelo.nombre if obj.modelo else (obj.modelo_legacy or "---")
        return f"{marca} -> {modelo}"

    @admin.display(description="Categoría", ordering='modelo__categoria__nombre')
    def get_categoria(self, obj):
        if obj.modelo and obj.modelo.categoria:
            return obj.modelo.categoria.nombre
        return "—"

    @admin.display(description="Categoría (del Modelo)")
    def get_categoria_display(self, obj):
        if obj.modelo and obj.modelo.categoria:
            return obj.modelo.categoria.nombre
        return "— Sin categoría asignada al modelo —"

    @admin.display(description="Código de Plano", ordering='plano__nombre')
    def get_plano_codigo(self, obj):
        if obj.plano:
            return obj.plano.numero_documento or obj.plano.nombre
        return "---"

    @admin.display(description="Última Auditoría", ordering='ultima_auditoria_fecha')
    def ultima_auditoria_display(self, obj):
        fecha = getattr(obj, 'ultima_auditoria_fecha', None)
        if not fecha:
            return mark_safe('<span style="color: #94a3b8; font-style: italic;">Nunca auditado</span>')
        
        from django.utils.timezone import now
        dias = (now() - fecha).days
        
        color = "#10b981" # Verde (reciente)
        if dias > 180: color = "#ef4444" # Rojo (>6 meses)
        elif dias > 90: color = "#f59e0b" # Naranja (>3 meses)
        
        return format_html(
            '<div style="display: flex; align-items: center; gap: 8px;">'
            '<span style="height: 8px; width: 8px; background-color: {0}; border-radius: 50%; display: inline-block;"></span>'
            '<span>{1}</span>'
            '</div>',
            color,
            fecha.strftime('%d/%m/%Y')
        )

    def ver_en_plano(self, obj):
        pines = obj.pines_planos.all()
        if not pines:
            return mark_safe('<span style="color: #999;">❌ No ubicado en planos</span>')
        
        html = '<div style="display: flex; flex-wrap: wrap; gap: 10px;">'
        for pin in pines:
            html += format_html(
                '<a href="/activos/visor/{0}/" target="_blank" style="background: #1e293b; color: white; padding: 8px 12px; border-radius: 8px; border: 1px solid #00d2ff; text-decoration: none; display: flex; align-items: center; gap: 8px;">'
                '<span style="color: #00d2ff; font-size: 1.2rem;">📍</span>'
                '<div>'
                '<div style="font-weight: bold; font-size: 0.8rem;">{1}</div>'
                '<div style="font-size: 0.7rem; opacity: 0.7;">Ver en Plano</div>'
                '</div>'
                '</a>',
                pin.visor.id,
                pin.visor.nombre
            )
        html += '</div>'
        return mark_safe(html)
    ver_en_plano.short_description = 'Ubicación en Planos'

    fieldsets = (
        ('Información Crítica (Obligatoria)', {
            'fields': (
                ('nombre', 'codigo_interno'), 
                'estado',
                'epc'
            ),
            'description': 'Estos campos son requeridos para identificar el activo.'
        }),
        ('Clasificación y Detalles', {
            'fields': (
                ('familia', 'modelo'),
                ('get_marca', 'serie'),
                'get_categoria_display',
                'referencia',
                'padre',
                'get_modelo_img'
            )
        }),
        ('Ubicación y Responsable', {
            'fields': (
                'ubicacion', 
                ('responsable', 'plano'),
                'ver_en_plano',
                'ubicacion_legacy'
            )
        }),
        ('Detalles Adicionales', {
            'fields': ('descripcion', 'foto', 'marca_legacy', 'modelo_legacy'),
            'classes': ('collapse',)
        }),
        ('Mantenimiento Preventivo', {
            'fields': (
                ('rutinas_aplicables', 'ordenes_programadas'), 
                'historial_ordenes', 
                'tickets_asociados',
                'ultima_auditoria_display',
                'crear_aviso_link'
            ),
            'description': 'Información sobre rutinas aplicables, órdenes pendientes, historial de mantenimiento y avisos/tickets.'
        }),
        ('Historial de Paradas y MTBF', {
            'fields': (
                ('mt_mtbf', 'mt_total_downtime'),
                'historial_paradas_table'
            ),
            'description': 'Métricas de confiabilidad y disponibilidad basadas en el historial de fallos y paradas.'
        }),
    )

    change_form_template = 'admin/activos/activo/change_form.html'

    def ver_en_fiori(self, obj):
        url = reverse('activos:activo_fiori', args=[obj.pk])
        return format_html('<a href="{0}" target="_blank" style="background: #0070f2; color: white; padding: 4px 10px; border-radius: 4px; text-decoration: none; font-weight: bold; font-size: 0.75rem; display: inline-flex; align-items: center; gap: 4px;"><ion-icon name="eye-outline"></ion-icon> Ver</a>', url)
    ver_en_fiori.short_description = 'Fiori'

    def sync_audit_location(self, request, activo_id, resultado_id):
        from django.shortcuts import get_object_or_404, redirect
        from django.contrib import messages
        
        activo = get_object_or_404(Activo, id=activo_id)
        resultado = get_object_or_404(ResultadoAuditoria, id=resultado_id)
        
        if resultado.ubicacion_encontrada:
            old_loc = activo.ubicacion.nombre if activo.ubicacion else "Ninguna"
            activo.ubicacion = resultado.ubicacion_encontrada
            activo.save()
            
            # Registrar trazabilidad en el resultado de la auditoría
            from django.utils import timezone
            resultado.sincronizado = True
            resultado.sincronizado_por = request.user
            resultado.fecha_sincronizacion = timezone.now()
            resultado.save()
            
            messages.success(request, f"Ubicación actualizada: de '{old_loc}' a '{resultado.ubicacion_encontrada.nombre}'. Movimiento registrado por {request.user.username}.")
        else:
            messages.error(request, "No se puede actualizar: el resultado de auditoría no registra una ubicación encontrada.")
            
        return redirect(reverse('admin:activos_activo_change', args=[activo.id]))

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('<path:object_id>/explorer/', self.admin_site.admin_view(self.explorer_view), name='activos_activo_explorer'),
            path('<path:object_id>/documentos-altabaja/', self.admin_site.admin_view(self.documentos_altabaja_view), name='activos_activo_documentos_altabaja'),
            path('<int:activo_id>/sync-audit/<int:resultado_id>/', self.admin_site.admin_view(self.sync_audit_location), name='activos_activo_sync_audit_location'),
            path('import-background/', self.admin_site.admin_view(self.import_background), name='activos_activo_import_background'),
            path('import-process/', self.admin_site.admin_view(self.import_process), name='activos_activo_import_process'),
            path('import-progress/', self.admin_site.admin_view(self.import_progress), name='activos_activo_import_progress'),
            path('export-admin-background/', self.admin_site.admin_view(self.export_admin_background), name='activos_activo_export_admin_background'),
        ]
        return custom_urls + urls

    def explorer_view(self, request, object_id):
        obj = self.get_object(request, object_id)
        # Optimization: Only count direct components to avoid N+1 recursion
        # If deeper stats are needed, they should be loaded asynchronously via the API
        total_componentes = obj.componentes.count()

        # Determine root for the tree view
        # If asset has a parent, show the parent as root to provide context
        tree_root = obj.padre if obj.padre else obj

        context = {
            **self.admin_site.each_context(request),
            'object': obj,
            'tree_root': tree_root,
            'cat_id': None, # Not strictly filter by category context here
            'total_activos': total_componentes,
            'is_popup': True,
            'hide_chatbot': True,
        }
        return render(request, 'admin/activos/activo/explorer_tab.html', context)

    def documentos_altabaja_view(self, request, object_id):
        obj = self.get_object(request, object_id)
        items = ItemAltaBaja.objects.filter(activo=obj).select_related('documento', 'activo').order_by('-documento__fecha')
        context = {
            **self.admin_site.each_context(request),
            'object': obj,
            'items': items,
            'is_popup': True,
            'hide_chatbot': True,
        }
        return render(request, 'admin/activos/activo/documentos_altabaja_tab.html', context)

    def import_background(self, request):
        context = {
            **self.admin_site.each_context(request),
            'title': 'Importación masiva en segundo plano',
        }
        return render(request, 'admin/activos/activo/background_import.html', context)

    def import_process(self, request):
        if request.method == 'POST' and request.FILES.get('file'):
            import os
            import uuid
            from django.core.files.storage import default_storage
            from django.core.files.base import ContentFile
            from django.http import JsonResponse
            from tablib import Dataset
            
            myfile = request.FILES['file']
            file_name = myfile.name
            file_format = file_name.split('.')[-1].lower()
            
            # Crear ID de sesión único
            import_id = str(uuid.uuid4())
            temp_path = f'tmp/imp_{import_id}.{file_format}'
            
            # Guardar archivo temporal
            path = default_storage.save(temp_path, ContentFile(myfile.read()))
            # Obtener conteo total para informar al front
            try:
                # Usar default_storage.open para compatibilidad con S3/MinIO
                with default_storage.open(path, 'rb') as f:
                    file_content = f.read()
                    if file_format == 'csv':
                        dataset = Dataset().load(file_content.decode('utf-8', errors='ignore'), format='csv')
                    else:
                        dataset = Dataset().load(file_content, format=file_format)
                
                return JsonResponse({
                    'status': 'started',
                    'import_id': import_id,
                    'total': len(dataset),
                    'file_format': file_format
                })
            except Exception as e:
                return JsonResponse({'status': 'error', 'message': f'Error al leer archivo: {str(e)}'}, status=400)
                
        return JsonResponse({'status': 'error', 'message': 'No se recibió archivo'}, status=400)

    def import_progress(self, request):
        """Ahora funciona como procesador de CHUNKS secuenciales"""
        from django.http import JsonResponse
        from django.core.files.storage import default_storage
        from tablib import Dataset
        from import_export import resources
        import os

        import_id = request.GET.get('import_id')
        start = int(request.GET.get('start', 0))
        chunk_size = int(request.GET.get('size', 50))
        file_format = request.GET.get('format', 'xlsx')

        if not import_id:
            return JsonResponse({'status': 'error', 'message': 'Falta import_id'}, status=400)

        temp_path = f'tmp/imp_{import_id}.{file_format}'
        if not default_storage.exists(temp_path):
            return JsonResponse({'status': 'error', 'message': 'Sesión expirada o archivo no encontrado'}, status=404)

        # No intentamos acceder a full_path, usamos open directamente
        
        resource = ActivoResource()
        
        try:
            with default_storage.open(temp_path, 'rb') as f:
                file_content = f.read()
                if file_format == 'csv':
                    dataset = Dataset().load(file_content.decode('utf-8', errors='ignore'), format='csv')
                else:
                    dataset = Dataset().load(file_content, format=file_format)
            
            total = len(dataset)
            end = min(start + chunk_size, total)
            
            # Log de progreso en consola para depuración
            print(f"IMPORT: Procesando lote {start} - {end} de {total} (ID: {import_id})")
            
            # Crear un mini-dataset para el chunk actual
            mini_dataset = Dataset()
            mini_dataset.headers = dataset.headers
            for row in dataset[start:end]:
                mini_dataset.append(row)
            
            # Procesar el lote usando el método estándar (más robusto)
            result = resource.import_data(mini_dataset, dry_run=False, raise_errors=False)

            # Si es el último chunk, borrar archivo
            if end >= total:
                try:
                    default_storage.delete(temp_path)
                except:
                    pass

            return JsonResponse({
                'status': 'PROGRESS',
                'current': end,
                'total': total,
                'new': result.totals.get('new', 0),
                'updated': result.totals.get('update', 0) + result.totals.get('updated', 0),
                'skipped': result.totals.get('skip', 0),
                'errors': len(result.base_errors) + len(result.row_errors()),
                'is_last': end >= total
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

    @admin.display(description="Resumen de Mediciones")
    def get_puntos_medicion_summary(self, obj):
        puntos = obj.puntos_medicion.all().prefetch_related('lecturas')
        if not puntos:
            return mark_safe('<span style="color: #94a3b8; font-style: italic;">No hay puntos de medición configurados para este equipo.</span>')
        
        html = '<div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; margin-top: 10px;">'
        html += '<table style="width: 100%; border-collapse: collapse; font-size: 0.85rem;">'
        html += '<thead style="background: #f8fafc; border-bottom: 2px solid #e2e8f0;">'
        html += '<tr>'
        html += '<th style="text-align: left; padding: 12px 15px;">Punto de Medición</th>'
        html += '<th style="text-align: center; padding: 12px 15px;">Último Valor</th>'
        html += '<th style="text-align: center; padding: 12px 15px;">Fecha Lectura</th>'
        html += '<th style="text-align: center; padding: 12px 15px;">Acción</th>'
        html += '</tr></thead><tbody>'
        
        for p in puntos:
            ultima = p.lecturas.first()
            valor = f"{ultima.valor} {p.unidad}" if ultima else "---"
            fecha = ultima.fecha_lectura.strftime('%d/%m/%Y %H:%M') if ultima else "---"
            
            html += f'<tr style="border-bottom: 1px solid #f1f5f9;">'
            html += f'<td style="padding: 12px 15px;">'
            html += f'<div style="font-weight: 600;">{p.nombre}</div>'
            html += f'<div style="font-size: 0.75rem; color: #64748b;">Cód: {p.codigo or "N/A"} | { "Acumulativo" if p.es_acumulativo else "Variable" }</div>'
            html += f'</td>'
            html += f'<td style="padding: 12px 15px; text-align: center; font-weight: bold; color: #2563eb;">{valor}</td>'
            html += f'<td style="padding: 12px 15px; text-align: center;">{fecha}</td>'
            html += f'<td style="padding: 12px 15px; text-align: center;">'
            html += f'<a href="/admin/activos/puntomedicion/{p.id}/change/" class="button" style="padding: 4px 8px; font-size: 0.75rem;">Configurar</a>'
            html += '</td></tr>'
        
        html += '</tbody></table></div>'
        return mark_safe(html)

@admin.register(PuntoMedicion)
class PuntoMedicionAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'activo', 'codigo', 'unidad', 'es_acumulativo', 'valor_objetivo', 'etiqueta_qr')
    list_filter = ('es_acumulativo', 'unidad')
    search_fields = ('nombre', 'codigo', 'activo__nombre', 'activo__codigo_interno')
    list_select_related = ('activo',)
    autocomplete_fields = ('activo',)
    readonly_fields = ('etiqueta_qr',)

    @admin.display(description='QR PDF')
    def etiqueta_qr(self, obj):
        if obj.pk:
            from django.urls import reverse
            url = reverse('activos:punto_medicion_qr_pdf', args=[obj.pk])
            return format_html(
                '<a class="button" href="{}" target="_blank" style="background:#2563eb; color:white; font-weight:bold; border-radius:4px;">Generar QR PDF</a>',
                url
            )
        return "-"

@admin.register(DocumentoMedicion)
class DocumentoMedicionAdmin(admin.ModelAdmin):
    list_display = ('punto', 'valor', 'fecha_lectura', 'tecnico', 'orden_trabajo')
    list_filter = ('fecha_lectura', 'tecnico')
    list_select_related = ('punto__activo', 'tecnico', 'orden_trabajo')
    search_fields = ('punto__nombre', 'punto__activo__nombre', 'observaciones')
    autocomplete_fields = ('punto', 'tecnico', 'orden_trabajo')


# Registro robusto para evitar AlreadyRegistered
class RegistroImportacionAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'tipo', 'fecha', 'usuario', 'estado', 'stats_summary', 'revert_button')
    list_filter = ('tipo', 'estado', 'fecha', 'usuario')
    search_fields = ('nombre',)
    readonly_fields = ('nombre', 'fecha', 'usuario', 'estado', 'total_filas', 'filas_nuevas', 'filas_actualizadas', 'filas_omitidas', 'filas_error', 'detalles_error', 'ids_creados')
    
    actions = ['revertir_importacion_action']

    def stats_summary(self, obj):
        return format_html(
            '<span style="color: green;">+{}</span> / '
            '<span style="color: blue;">∆{}</span> / '
            '<span style="color: orange;">ø{}</span> / '
            '<span style="color: red;">!{}</span>',
            obj.filas_nuevas, obj.filas_actualizadas, obj.filas_omitidas, obj.filas_error
        )
    stats_summary.short_description = 'N / A / O / E'

    def revert_button(self, obj):
        if obj.estado == 'COMPLETADO' and obj.filas_nuevas > 0:
            return format_html(
                '<a class="button" href="revert/{}/" style="background-color: #d9534f; color: white;">Revertir</a>',
                obj.id
            )
        return "-"
    revert_button.short_description = 'Acciones'

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('revert/<int:registro_id>/', self.admin_site.admin_view(self.revert_view), name='activos_registroimportacion_revert'),
        ]
        return custom_urls + urls

    def revert_view(self, request, registro_id):
        from .tasks import revertir_importacion_task
        # Ejecutar tarea de reversión
        # En una app real, esto podría ser async, pero para feedback inmediato lo hacemos sincrónico o lanzamos delay y avisamos
        res = revertir_importacion_task(registro_id)
        
        if res['status'] == 'completed':
            self.message_user(request, f"Importación revertida con éxito. Se eliminaron {res['deleted_count']} activos.", messages.SUCCESS)
        else:
            self.message_user(request, f"Error al revertir: {res['message']}", messages.ERROR)
            
        from django.shortcuts import redirect
        return redirect('..')

    def revertir_importacion_action(self, request, queryset):
        for obj in queryset:
            if obj.estado == 'COMPLETADO':
                from .tasks import revertir_importacion_task
                revertir_importacion_task.delay(obj.id)
        self.message_user(request, "Se han lanzado las tareas de reversión para las importaciones seleccionadas.", messages.INFO)
    revertir_importacion_action.short_description = "Revertir importaciones seleccionadas"

try:
    admin.site.unregister(RegistroImportacion)
except:
    pass
admin.site.register(RegistroImportacion, RegistroImportacionAdmin)

# Fuerza la re-registración de ACTIVO para asegurar que use ActivoAdminCustom
try:
    admin.site.unregister(Activo)
except:
    pass
admin.site.register(Activo, ActivoAdminCustom)
@admin.register(ControlSubmittal)
class ControlSubmittalAdmin(ImportExportModelAdmin):
    resource_class = ControlSubmittalResource
    change_list_template = 'admin/activos/controlsubmittal/change_list.html'
    list_display = (
        'codigo_ficha', 'codigo_submittal', 'num_submittal', 
        'especialidad', 'fecha_recibido', 'estatus_ccg', 'dictamen_sup'
    )
    list_filter = ('estatus_ccg', 'dictamen_sup', 'estatus_aconex')
    search_fields = ('codigo_ficha', 'codigo_submittal', 'descripcion', 'especialidad', 'trab_act_n')
    date_hierarchy = 'fecha_recibido'
    
    fieldsets = (
        ('Información General', {
            'fields': ('descripcion', 'especialidad', 'trab_act_n', 'fecha_recibido', 'codigo_ficha', 'codigo_submittal', 'num_submittal')
        }),
        ('EPC (Revisión)', {
            'fields': ('fecha_revisado_epc', 'comentario_epc', 'observacion_epc')
        }),
        ('Supervisión', {
            'fields': (
                'fecha_envio_sup', 'transmision_epc_sup', 'transmision_sup_epc', 
                'fecha_recepcion_sup', 'dictamen_sup', 'observacion_sup'
            )
        }),
        ('Constructora (CCC)', {
            'fields': ('enviado_constructora', 'fecha_envio_ccc', 'transmitido_a_ccc', 'fecha_envio_ccc_final')
        }),
        ('Estatus y Control', {
            'fields': ('estatus_aconex', 'estatus_ccg', 'carpeta')
        }),
    )

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('import-background/', self.admin_site.admin_view(self.import_background), name='activos_controlsubmittal_import_background'),
            path('import-process/', self.admin_site.admin_view(self.import_process), name='activos_controlsubmittal_import_process'),
            path('import-progress/', self.admin_site.admin_view(self.import_progress), name='activos_controlsubmittal_import_progress'),
            path('download-template/', self.admin_site.admin_view(self.download_template), name='activos_controlsubmittal_download_template'),
        ]
        return custom_urls + urls

    def import_background(self, request):
        context = {
            'title': 'Importación masiva de Submittals',
        }
        return render(request, 'admin/activos/controlsubmittal/background_import.html', context)

    @csrf_exempt
    def import_process(self, request):
        if request.method == 'POST' and request.FILES.get('file'):
            import os, uuid
            from django.core.files.storage import default_storage
            from django.core.files.base import ContentFile
            from django.http import JsonResponse
            from tablib import Dataset
            
            myfile = request.FILES['file']
            file_name = myfile.name
            file_format = file_name.split('.')[-1].lower()
            import_id = str(uuid.uuid4())
            temp_path = f'tmp/sub_imp_{import_id}.{file_format}'
            path = default_storage.save(temp_path, ContentFile(myfile.read()))
            
            try:
                with default_storage.open(path, 'rb') as f:
                    file_content = f.read()
                    if file_format == 'csv':
                        from .tasks import try_decode
                        dataset = Dataset().load(try_decode(file_content), format='csv')
                    else:
                        dataset = Dataset().load(file_content, format=file_format)
                
                # Normalizar encabezados
                import unicodedata
                def normalize(text):
                    text = str(text).strip().lower()
                    text = "".join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')
                    return text.replace(' ', '_').replace('.', '_')

                dataset.headers = [normalize(h) for h in dataset.headers]
                
                # Guardar JSON
                json_path = f'tmp/sub_imp_{import_id}.json'
                json_data = dataset.json.encode('utf-8')
                default_storage.save(json_path, ContentFile(json_data))
                
                try:
                    default_storage.delete(path)
                except:
                    pass

                return JsonResponse({
                    'status': 'started',
                    'import_id': import_id,
                    'total': len(dataset),
                    'file_format': 'json'
                })
            except Exception as e:
                return JsonResponse({'status': 'error', 'message': f'Error: {str(e)}'}, status=400)
        return JsonResponse({'status': 'error', 'message': 'No hay archivo'}, status=400)

    def import_progress(self, request):
        from django.http import JsonResponse
        from django.core.files.storage import default_storage
        from tablib import Dataset
        import_id = request.GET.get('import_id')
        start = int(request.GET.get('start', 0))
        chunk_size = int(request.GET.get('size', 50))
        
        temp_path = f'tmp/sub_imp_{import_id}.json'
        if not default_storage.exists(temp_path):
            return JsonResponse({'status': 'error', 'message': 'No encontrado'}, status=404)

        resource = ControlSubmittalResource()
        try:
            with default_storage.open(temp_path, 'rb') as f:
                dataset = Dataset().load(f.read(), format='json')
            
            total = len(dataset)
            end = min(start + chunk_size, total)
            chunk = dataset[start:end]
            
            # Ejecutar importación del chunk
            res = resource.import_data(chunk, dry_run=False, raise_errors=False)
            
            # Recopilar errores
            error_list = []
            for row_res in res.rows:
                if row_res.errors:
                    error_list.append({
                        'row': start + row_res.row_number,
                        'message': str(row_res.errors[0].error)
                    })

            # Guardar acumulados en cache/session si fuera necesario, aquí lo hacemos simple
            # para que el JS los maneje
            
            is_last = end >= total
            if is_last:
                try:
                    default_storage.delete(temp_path)
                except:
                    pass

            return JsonResponse({
                'status': 'success',
                'current': end,
                'total': total,
                'new': res.totals.get('new', 0),
                'updated': res.totals.get('update', 0),
                'errors': len(error_list),
                'error_list': error_list,
                'is_last': is_last
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

    def download_template(self, request):
        from django.http import HttpResponse
        from tablib import Dataset
        resource = ControlSubmittalResource()
        dataset = resource.export(queryset=ControlSubmittal.objects.none())
        
        response = HttpResponse(dataset.xlsx, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="formato_submittals.xlsx"'
        return response


class ItemAltaBajaInline(admin.TabularInline):
    model = ItemAltaBaja
    extra = 1
    fields = ('activo', 'get_codigo', 'get_estado', 'get_ubicacion', 'observacion')
    readonly_fields = ('get_codigo', 'get_estado', 'get_ubicacion')
    autocomplete_fields = ['activo']

    def get_codigo(self, obj):
        if obj.activo:
            return obj.activo.codigo_interno
        return "-"
    get_codigo.short_description = "Código"

    def get_estado(self, obj):
        if obj.activo:
            colores = {
                'OPERATIVO': '#10B981',
                'MANTENIMIENTO': '#F59E0B',
                'REPARACION': '#F97316',
                'FUERA_SERVICIO': '#EF4444',
                'OBSOLETO': '#6B7280',
            }
            color = colores.get(obj.activo.estado, '#6B7280')
            return format_html('<span style="color: {}; font-weight: bold;">{}</span>', color, obj.activo.get_estado_display())
        return "-"
    get_estado.short_description = "Estado Actual"

    def get_ubicacion(self, obj):
        if obj.activo and obj.activo.ubicacion:
            return str(obj.activo.ubicacion)
        return "-"
    get_ubicacion.short_description = "Ubicación"


class ArchivoAltaBajaInline(admin.TabularInline):
    model = ArchivoAltaBaja
    extra = 1
    fields = ('archivo', 'comentario', 'subido_en')
    readonly_fields = ('subido_en',)


@admin.register(DocumentoAltaBaja)
class DocumentoAltaBajaAdmin(admin.ModelAdmin):
    list_display = ('numero', 'get_tipo_badge', 'fecha', 'get_total_activos', 'estado', 'elaborado_por')
    list_filter = ('tipo', 'estado', 'fecha')
    search_fields = ('numero', 'motivo')
    inlines = [ItemAltaBajaInline, ArchivoAltaBajaInline]
    autocomplete_fields = ['elaborado_por', 'autorizado_por', 'recibido_por']
    readonly_fields = ('numero', 'imprimir_btn')

    def imprimir_btn(self, obj):
        if obj.pk:
            url = reverse('activos:print_altabaja', args=[obj.pk])
            return format_html(
                '<a href="{}" target="_blank" class="button" '
                'style="background: #2563eb; color: white; padding: 8px 20px; border-radius: 6px; '
                'font-weight: 700; text-decoration: none; font-size: 0.9rem;">'
                '🖨️ Imprimir Documento</a>',
                url
            )
        return "Guarde primero para imprimir."
    imprimir_btn.short_description = "Acciones"

    fieldsets = (
        ('Identificación', {
            'fields': ('tipo', 'numero', 'fecha', 'estado', 'imprimir_btn')
        }),
        ('Detalle', {
            'fields': ('motivo', 'observaciones')
        }),
        ('Responsables', {
            'fields': ('elaborado_por', 'autorizado_por', 'recibido_por')
        }),
    )

    def get_fieldsets(self, request, obj=None):
        if not obj:
            # Al crear, ocultar numero (se genera al guardar)
            return (
                ('Identificación', {
                    'fields': ('tipo', 'fecha', 'estado')
                }),
                ('Detalle', {
                    'fields': ('motivo', 'observaciones')
                }),
                ('Responsables', {
                    'fields': ('elaborado_por', 'autorizado_por', 'recibido_por')
                }),
            )
        return super().get_fieldsets(request, obj)

    def get_tipo_badge(self, obj):
        color = '#10B981' if obj.tipo == 'ALTA' else '#EF4444'
        icon = '📥' if obj.tipo == 'ALTA' else '📤'
        return format_html(
            '<span style="background: {}15; color: {}; padding: 4px 12px; border-radius: 12px; font-weight: 700; font-size: 0.8rem;">'
            '{} {}</span>',
            color, color, icon, obj.get_tipo_display()
        )
    get_tipo_badge.short_description = "Tipo"

    def get_total_activos(self, obj):
        count = obj.total_activos
        return format_html(
            '<span style="background: #eff6ff; color: #2563eb; padding: 2px 10px; border-radius: 12px; font-weight: 700;">{}</span>',
            count
        )
    get_total_activos.short_description = "# Activos"

from .models import PlantillaEtiquetaQR

@admin.register(PlantillaEtiquetaQR)
class PlantillaEtiquetaQRAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'ancho_cm', 'alto_cm', 'prefijo_defecto', 'activo', 'diseñar_etiqueta')
    list_filter = ('activo',)
    search_fields = ('nombre', 'prefijo_defecto')
    readonly_fields = ('compiled_html',)

    def diseñar_etiqueta(self, obj):
        if obj.id:
            url = f"/activos/etiquetas/designer/{obj.id}/"
            return format_html(
                '<a class="button" style="background:#3b82f6; color:white; padding:4px 10px; border-radius:4px; font-weight:bold; text-decoration:none;" href="{}">🖌️ Diseñador Visual</a>',
                url
            )
        return "Guarde primero para diseñar"
    diseñar_etiqueta.short_description = "WYSIWYG"
