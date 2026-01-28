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
from .models import Activo, Categoria, Familia, Ubicacion, Marca, Modelo, Plano, VisorPlano, PinPlano, PuntoMedicion, DocumentoMedicion, RegistroImportacion, Disciplina

# ... (resto de registros)
from auditorias.models import ResultadoAuditoria

from django.utils.html import format_html
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from inventarios.models import CompatibilidadMaterial
from documentos.models import Documento

# Importar admin de Bien Afecto
from .admin_bien_afecto import BienAfectoAdmin, HistorialBienAfectoAdmin

class SmartModeloWidget(ForeignKeyWidget):
    """Widget que usa el caché del Resource para evitar Modelo.DoesNotExist o consultas N+1."""
    def clean(self, value, row=None, **kwargs):
        if not value:
            return None
        
        val_str = str(value).strip()
        # Tratamos literales como "None" o "NULL" como vacíos
        if val_str.upper() in ('NONE', 'NULL', 'N/A', ''):
            return None
            
        val_upper = val_str.upper()
        resource = kwargs.get('resource')
        if resource and hasattr(resource, 'modelo_cache'):
            # Si no está en caché, simplemente devolvemos None (obviar errores)
            return resource.modelo_cache.get(val_upper)
            
        # Fallback seguro que no levanta DoesNotExist si no encuentra
        try:
            return super().clean(value, row, **kwargs)
        except Exception:
            return None

class SmartUserWidget(ForeignKeyWidget):
    """Widget que busca el usuario por username y devuelve None si no existe instead of crashing."""
    def clean(self, value, row=None, **kwargs):
        if not value:
            return None
        val_str = str(value).strip()
        if val_str.upper() in ('NONE', 'NULL', 'N/A', ''):
            return None
        from django.contrib.auth.models import User
        return User.objects.filter(username=val_str).first()

class SmartActivoWidget(ForeignKeyWidget):
    """Widget que busca el activo por código interno y devuelve None si no existe."""
    def clean(self, value, row=None, **kwargs):
        if not value:
            return None
        val_str = str(value).strip()
        from .models import Activo
        return Activo.objects.filter(codigo_interno=val_str).first()

class SmartFamiliaWidget(ForeignKeyWidget):
    """Widget que busca la familia por nombre y devuelve None si no existe."""
    def clean(self, value, row=None, **kwargs):
        if not value:
            return None
        val_str = str(value).strip()
        from .models import Familia
        return Familia.objects.filter(nombre__iexact=val_str).first()

class SmartParentWidget(ForeignKeyWidget):
    """
    Widget que busca el padre por nombre y devuelve el primero encontrado.
    Evita MultipleObjectsReturned en jerarquías con nombres repetidos en distintos niveles.
    """
    def clean(self, value, row=None, **kwargs):
        if not value:
            return None
        return Ubicacion.objects.filter(nombre=value).first()

class CachedDisciplinaWidget(ForeignKeyWidget):
    """
    Widget que utiliza un caché del Resource para evitar consultas redundantes a la DB.
    """
    def clean(self, value, row=None, **kwargs):
        if not value or str(value).strip().upper() in ('NONE', 'NULL', 'N/A', '', 'NAN'):
            return None
        val_orig = str(value).strip()
        val_clean = val_orig.upper()
        resource = kwargs.get('resource')
        
        if resource and hasattr(resource, 'disciplina_cache'):
            return resource.disciplina_cache.get(val_clean)
        
        from .models import Disciplina
        return Disciplina.objects.filter(nombre__iexact=val_orig).first()

class CachedUbicacionWidget(ForeignKeyWidget):
    """
    Widget que utiliza un caché del Resource para evitar consultas redundantes a la DB.
    """
    def clean(self, value, row=None, **kwargs):
        if not value or str(value).strip().upper() in ('NONE', 'NULL', 'N/A', '', 'NAN'):
            return None
        val_orig = str(value).strip()
        val_clean = val_orig.upper()
        resource = kwargs.get('resource')
        
        if resource and hasattr(resource, 'ubicacion_cache'):
            return resource.ubicacion_cache.get(val_clean)
        
        from .models import Ubicacion
        return Ubicacion.objects.filter(nombre__iexact=val_orig).first()

class PlanoResource(resources.ModelResource):
    ubicacion_nombre = fields.Field(
        column_name='ubicacion_nombre',
        attribute='ubicacion',
        widget=CachedUbicacionWidget(Ubicacion, field='nombre')
    )
    disciplina_nombre = fields.Field(
        column_name='disciplina_nombre',
        attribute='disciplina',
        widget=CachedDisciplinaWidget(Disciplina, field='nombre')
    )

    def dehydrate_disciplina_nombre(self, plano):
        if plano.disciplina:
            return plano.disciplina.get_ruta_completa()
        return ''

    documento_codigo = fields.Field(
        column_name='documento_codigo',
        attribute='documento',
        widget=ForeignKeyWidget(Documento, field='codigo'), 
    )

    def before_import(self, dataset, **kwargs):
        """Caching agresivo en memoria: Cargamos todo el universo de datos una sola vez."""
        from .models import Ubicacion, Disciplina, Plano
        from documentos.models import Documento
        
        # Diccionarios de búsqueda rápida (O(1)) de OBJETOS completos
        self.ubicacion_cache = {str(u.nombre).strip().upper(): u for u in Ubicacion.objects.all()}
        self.disciplina_cache = {str(d.nombre).strip().upper(): d for d in Disciplina.objects.all()}
        self.documento_cache = {str(doc.codigo).strip().upper(): doc for doc in Documento.objects.all()}
        self.planos_existentes = {str(p.nombre).strip().upper() for p in Plano.objects.all()}

    class Meta:
        model = Plano
        import_id_fields = ('nombre',)
        fields = ('nombre', 'tipo_plano', 'numero_documento', 'titulo', 'ubicacion_nombre', 'disciplina_nombre', 'descripcion', 'documento_codigo')
        use_bulk = False
        batch_size = 1000
        skip_unchanged = True
    
    def before_import_row(self, row, **kwargs):
        # Mapeo flexible de nombres de columnas comunes
        if 'ubicacion' in row and 'ubicacion_nombre' not in row:
            row['ubicacion_nombre'] = row['ubicacion']
        if 'disciplina' in row and 'disciplina_nombre' not in row:
            row['disciplina_nombre'] = row['disciplina']
        if 'documento' in row and 'documento_codigo' not in row:
            row['documento_codigo'] = row['documento']

        # Limpieza básica y normalización
        for field in ['ubicacion_nombre', 'disciplina_nombre', 'documento_codigo']:
            if field in row and row[field]:
                # Quitar espacios y convertir a string limpio
                row[field] = str(row[field]).strip()
                if field == 'documento_codigo':
                    row[field] = row[field].upper()

class DisciplinaResource(resources.ModelResource):
    padre_nombre = fields.Field(
        column_name='padre_nombre',
        attribute='padre',
        widget=CachedDisciplinaWidget(Disciplina, field='nombre')
    )

    def before_import(self, dataset, **kwargs):
        """Cargar todas las disciplinas existentes en un caché para evitar N+1."""
        self.disciplina_cache = {d.nombre: d for d in Disciplina.objects.all()}

    def after_save_instance(self, instance, row=None, **kwargs):
        """Actualizar el caché con la nueva disciplina creada para que sus hijos la encuentren."""
        dry_run = kwargs.get('dry_run', False)
        if not dry_run and instance:
            self.disciplina_cache[instance.nombre] = instance

    def before_import_row(self, row, **kwargs):
        """Limpiar espacios en blanco en los nombres para evitar duplicados por error tipográfico."""
        if 'nombre' in row:
            row['nombre'] = str(row['nombre']).strip()
        if 'padre_nombre' in row and row['padre_nombre']:
            row['padre_nombre'] = str(row['padre_nombre']).strip()
        else:
            row['padre_nombre'] = None

    class Meta:
        model = Disciplina
        import_id_fields = ('nombre',)
        fields = ('nombre', 'padre_nombre', 'descripcion')
        export_order = fields
        skip_unchanged = True
        report_skipped = True
        skip_unchanged = True
        report_skipped = True
        use_bulk = False  # Desactivado para jerarquías (fila a fila para actualizar caché)


class SmartPlanoWidget(ForeignKeyWidget):
    """Widget que busca el plano por nombre. Si no existe lo crea."""
    def clean(self, value, row=None, **kwargs):
        if not value:
            return None
        val_str = str(value).strip()
        if val_str.upper() in ('NONE', 'NULL', 'N/A', ''):
            return None
            
        from .models import Plano, Ubicacion
        plano = Plano.objects.filter(nombre__iexact=val_str).first()
        if not plano:
            # Si no existe, lo creamos. Intentamos obtener la ubicación del row.
            # En ActivoResource, el campo de ubicación se llama 'ubicacion_nombre'
            ubicacion_val = row.get('ubicacion_nombre')
            ubicacion = None
            if ubicacion_val:
                # Usar lógica de jerarquía también al crear planos automáticamente
                import re
                u_val_clean = str(ubicacion_val).strip()
                u_norm = re.sub(r'\s*([→|>]|->)\s*', '|', u_val_clean).strip().upper()
                
                # Intentar buscar por ruta completa primero
                ubicacion = None
                for loc in Ubicacion.objects.filter(nombre__iexact=u_norm.split('|')[-1]):
                    if loc.get_clave_unica().upper() == u_norm:
                        ubicacion = loc
                        break
                
                # Fallback a nombre simple si no se encontró por jerarquía
                if not ubicacion:
                    ubicacion = Ubicacion.objects.filter(nombre__iexact=u_val_clean).first()
            
            # Ahora permitimos crear planos sin ubicación
            plano = Plano.objects.create(nombre=val_str, ubicacion=ubicacion)
            
        return plano



class ActivoFaltantesFilter(admin.SimpleListFilter):
    title = 'Calidad de Datos'
    parameter_name = 'faltante'

    def lookups(self, request, model_admin):
        return (
            ('serie', '❌ Sin N° Serie'),
            ('responsable', '👤 Sin Responsable'),
            ('ubicacion', '📍 Sin Ubicación'),
            ('codigo', '🆔 Sin Código Interno'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'serie':
            return queryset.filter(models.Q(serie__isnull=True) | models.Q(serie=''))
        if self.value() == 'responsable':
            return queryset.filter(responsable__isnull=True)
        if self.value() == 'ubicacion':
            return queryset.filter(ubicacion__isnull=True)
        if self.value() == 'codigo':
            return queryset.filter(models.Q(codigo_interno__isnull=True) | models.Q(codigo_interno=''))
        return queryset

class UbicacionHierarchyFilter(admin.SimpleListFilter):
    title = 'Ubicación'
    parameter_name = 'ubicacion_id'

    def lookups(self, request, model_admin):
        # Optimización: No cargar miles de ubicaciones con ruta_completa en el sidebar.
        # Solo mostrar las ubicaciones raíz o usar un límite razonable.
        from .models import Ubicacion
        lookups = [('none', '📍 Sin Ubicación Asignada')]
        
        # Solo mostramos los primeros niveles para evitar bloqueos por volumen
        locations = Ubicacion.objects.filter(padre__isnull=True).order_by('nombre')
        for loc in locations:
            lookups.append((loc.id, f"🏢 {loc.nombre}"))
            
        return lookups

    def queryset(self, request, queryset):
        val = self.value()
        if val:
            if val == 'none':
                return queryset.filter(ubicacion__isnull=True)
            
            from .models import Ubicacion
            try:
                ubicacion = Ubicacion.objects.get(id=val)
                # Obtener todos los descendientes incluyendo el actual
                descendientes_ids = ubicacion.get_descendants(include_self=True).values_list('id', flat=True)
                return queryset.filter(ubicacion_id__in=descendientes_ids)
            except (Ubicacion.DoesNotExist, ValueError):
                return queryset
        return queryset

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
    filter_horizontal = ('activos',)
    autocomplete_fields = ('documento', 'disciplina', 'ubicacion')
    readonly_fields = ('visualizar_archivo',)
    fieldsets = (
        (None, {'fields': ('nombre', 'tipo_plano', 'numero_documento', 'titulo', 'disciplina', 'ubicacion', 'descripcion')}),
        ('Archivo del Plano', {
            'fields': ('documento', 'archivo'),
            'description': 'Usa "Documento" para control de versiones, o "Archivo" para carga directa.'
        }),
        ('Activos Vinculados', {'fields': ('activos',)}),
    )

    def documento_info(self, obj):
        if obj.documento:
            rev = obj.revision_actual or ''
            return format_html('<span style="color: #2563eb;">{}</span> <small style="color: #64748b;">{}</small>', 
                             obj.documento.codigo, rev)
        return format_html('<span style="color: #94a3b8;">Sin documento</span>')
    documento_info.short_description = "Documento"

    def visualizar_archivo(self, obj):
        archivo = obj.archivo_actual
        if archivo:
            rev_tag = f' ({obj.revision_actual})' if obj.revision_actual else ''
            return format_html('<a href="{0}" target="_blank">📄 Ver Plano{1}</a>', archivo.url, rev_tag)
        return "No hay archivo"
    visualizar_archivo.short_description = "Visualizar"
    
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


class PinPlanoInline(admin.TabularInline):
    model = PinPlano
    extra = 1
    autocomplete_fields = ['activo']

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

@admin.register(Categoria)
class CategoriaAdmin(ImportExportModelAdmin):
    list_per_page = 50
    list_display = ('nombre', 'icono', 'descripcion', 'cantidad_activos')
    search_fields = ('nombre',)
    change_form_template = 'admin/activos/categoria/change_form.html'

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
            return format_html('<span style="color: #cbd5e1;">0</span>')
        return format_html(
            '<span style="background: #eff6ff; color: #2563eb; padding: 2px 10px; border-radius: 12px; font-weight: 700;">{}</span>',
            count
        )
    cantidad_activos.short_description = "Cantidad Activos"
    cantidad_activos.admin_order_field = '_activos_count'

class SubFamiliaInline(admin.TabularInline):
    model = Familia
    fk_name = 'padre'
    extra = 1
    verbose_name = "Sub-Familia"
    verbose_name_plural = "Sub-Familias"
    formfield_overrides = {
        models.TextField: {'widget': admin.widgets.AdminTextInputWidget(attrs={'style': 'width: 100%;'})},
    }

class ActivoFamiliaInline(admin.TabularInline):
    from .models import Activo
    model = Activo
    extra = 0
    fields = ('nombre', 'codigo_interno', 'modelo', 'estado', 'ubicacion')
    autocomplete_fields = ('modelo', 'ubicacion')
    readonly_fields = ('nombre', 'codigo_interno', 'modelo', 'estado', 'ubicacion')
    can_delete = False
    show_change_link = True
    verbose_name = "Activo en esta Familia"
    verbose_name_plural = "Activos vinculados a esta Familia"

    def has_add_permission(self, request, obj=None):
        return False

class FamiliaResource(resources.ModelResource):
    padre_nombre = fields.Field(
        column_name='padre_nombre',
        attribute='padre',
        widget=ForeignKeyWidget(Familia, field='nombre')
    )

    class Meta:
        model = Familia
        import_id_fields = ('nombre', 'padre_nombre')
        fields = ('id', 'nombre', 'padre_nombre', 'descripcion')
        export_order = ('id', 'nombre', 'padre_nombre', 'descripcion')

@admin.register(Familia)
class FamiliaAdmin(ImportExportModelAdmin):
    list_per_page = 50
    resource_class = FamiliaResource
    list_display = ('nombre_con_indentacion', 'descripcion')
    list_display_links = ('nombre_con_indentacion',)
    search_fields = ('nombre',)
    list_select_related = ('padre', 'padre__padre')
    autocomplete_fields = ('padre',)
    inlines = [SubFamiliaInline, ActivoFamiliaInline]

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



class UbicacionResource(resources.ModelResource):
    """
    Resource para Ubicaciones jerárquicas.
    Permite importar usando 'padre_nombre' en lugar de IDs.
    """
    padre_nombre = fields.Field(
        column_name='padre_nombre',
        attribute='padre',
        widget=SmartParentWidget(Ubicacion, field='nombre')
    )
    
    # Campos adicionales para exportación
    id = fields.Field(column_name='id', attribute='id', readonly=True)
    clave_unica = fields.Field(column_name='clave_unica', readonly=True)
    ruta_completa = fields.Field(column_name='ruta_completa', readonly=True)
    categoria_nombre = fields.Field(
        column_name='categoria_nombre',
        attribute='categoria',
        widget=ForeignKeyWidget(Categoria, field='nombre')
    )

    class Meta:
        model = Ubicacion
        # Usamos nombre y padre_nombre como identificadores para evitar duplicados en importación
        import_id_fields = ('nombre', 'padre_nombre')
        fields = ('id', 'clave_unica', 'ruta_completa', 'nombre', 'tipo', 'padre_nombre', 'categoria_nombre', 'orden', 'descripcion')
        export_order = ('id', 'clave_unica', 'ruta_completa', 'nombre', 'tipo', 'padre_nombre', 'categoria_nombre', 'orden', 'descripcion')
        skip_unchanged = True
        report_skipped = True
        
        # Desactivamos bulk para manejar la jerarquía fila a fila y evitar errores de bulk_update con PKs
        use_bulk = False

    def dehydrate_clave_unica(self, obj):
        return obj.get_clave_unica()

    def dehydrate_ruta_completa(self, obj):
        return obj.ruta_completa


class CompatibilidadMaterialInline(admin.TabularInline):
    from inventarios.models import CompatibilidadMaterial
    model = CompatibilidadMaterial
    extra = 1
    autocomplete_fields = ['material']

class ModeloInline(admin.TabularInline):
    model = Modelo
    extra = 1

@admin.register(Marca)
class MarcaAdmin(ImportExportModelAdmin):
    list_per_page = 50
    list_display = ('nombre',)
    search_fields = ('nombre',)
    inlines = [ModeloInline]

class ModeloResource(resources.ModelResource):
    marca_nombre = fields.Field(
        column_name='marca_nombre',
        attribute='marca',
        widget=ForeignKeyWidget(Marca, field='nombre')
    )
    categoria_nombre = fields.Field(
        column_name='categoria_nombre',
        attribute='categoria',
        widget=ForeignKeyWidget(Categoria, field='nombre')
    )

    class Meta:
        model = Modelo
        # Identificamos por nombre y marca para que si el ID está vacío, 
        # actualice si ya existe esa combinación o cree uno nuevo si no.
        import_id_fields = ('nombre', 'marca_nombre')
        fields = ('id', 'nombre', 'marca_nombre', 'categoria_nombre', 'imagen_url')
        export_order = ('id', 'nombre', 'marca_nombre', 'categoria_nombre', 'imagen_url')

    def skip_row(self, instance, original, row, import_validation_errors=None, **kwargs):
        if not any(row.values()): return True
        return super().skip_row(instance, original, row, import_validation_errors, **kwargs)

    def before_import_row(self, row, **kwargs):
        """Asegurar que la marca existe antes de importar el modelo"""
        marca_name = str(row.get('marca_nombre') or '').strip()
        if marca_name:
            from .models import Marca
            Marca.objects.get_or_create(nombre=marca_name)

@admin.register(Modelo)
class ModeloAdmin(ImportExportModelAdmin):
    list_per_page = 50
    resource_class = ModeloResource
    list_display = ('thumbnail', 'nombre', 'marca', 'categoria', 'total_activos')
    list_filter = ('marca', 'categoria')
    list_select_related = ('marca', 'categoria')
    autocomplete_fields = ('marca', 'categoria')
    inlines = [CompatibilidadMaterialInline]

    def get_import_resource_kwargs(self, request, *args, **kwargs):
        return {'user': request.user}
    
    def get_export_resource_kwargs(self, request, *args, **kwargs):
        return {'user': request.user}
    search_fields = ('nombre', 'marca__nombre')
    readonly_fields = ('preview_imagen', 'lista_activos_ubicacion', 'rutinas_aplicables')

    def thumbnail(self, obj):
        if obj.imagen:
            return format_html('<img src="{}" style="width: 40px; height: 40px; object-fit: cover; border-radius: 4px;" />', obj.imagen)
        return format_html('<div style="width: 40px; height: 40px; background: #f1f5f9; border-radius: 4px; display: flex; align-items: center; justify-content: center; color: #cbd5e1;"><ion-icon name="image-outline"></ion-icon></div>')
    thumbnail.short_description = 'Imagen'

    def preview_imagen(self, obj):
        if obj.imagen:
            return format_html('<img src="{}" style="max-width: 300px; max-height: 300px; border-radius: 8px; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);" />', obj.imagen)
        return format_html('<span style="color: #94a3b8; font-style: italic;">No hay imagen configurada</span>')
    preview_imagen.short_description = 'Vista Previa'

    def rutinas_aplicables(self, obj):
        if not obj.categoria:
            return format_html('<span style="color: #94a3b8; font-style: italic;">No hay una categoría de activo definida para este modelo.</span>')
        
        # Buscar la categoría de mantenimiento vinculada (a través de la relación inversa)
        m_cat = getattr(obj.categoria, 'mantenimiento_categoria', None)
        
        if not m_cat:
            return format_html('<span style="color: #94a3b8; font-style: italic;">La categoría "{0}" no tiene una categoría de mantenimiento vinculada.</span>', obj.categoria.nombre)

        from mantenimiento.models import Rutina
        # Obtener ancestros de la categoría de mantenimiento vinculada para incluir rutinas generales
        m_cats_ids = []
        curr = m_cat
        while curr:
            m_cats_ids.append(curr.id)
            curr = curr.padre
            
        rutinas = Rutina.objects.filter(categoria_id__in=m_cats_ids).select_related('frecuencia', 'categoria')
        
        if not rutinas.exists():
            return format_html('<span style="color: #94a3b8; font-style: italic;">No hay rutinas de mantenimiento configuradas para la categoría "{0}".</span>', obj.categoria.nombre)
            
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
            html += f'<div style="font-size: 0.75rem; color: #64748b;">{r.categoria.nombre if r.categoria else "General"}</div>'
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
        return format_html(html)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(activos_count=Count('activos'))

    def total_activos(self, obj):
        return getattr(obj, 'activos_count', obj.activos.count())
    total_activos.short_description = 'Total Activos'
    total_activos.admin_order_field = 'activos_count'

    def lista_activos_ubicacion(self, obj):
        activos = obj.activos.select_related('ubicacion').order_by('ubicacion__nombre')
        if not activos:
            return format_html('<span style="color: #999;">No hay activos registrados con este modelo.</span>')

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
        return format_html(html)
    lista_activos_ubicacion.short_description = 'Activos Clasificados por Ubicación'

    fieldsets = (
        ('Información General', {
            'fields': ('nombre', 'marca', 'categoria')
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
    )


class UbicacionHijaInline(admin.TabularInline):
    model = Ubicacion
    fk_name = 'padre'
    extra = 1
    verbose_name = "Sub-Ubicación"
    verbose_name_plural = "Sub-Ubicaciones (Niveles Hijos)"
    fields = ('render_icon', 'nombre', 'orden', 'categoria', 'total_count', 'descripcion')
    autocomplete_fields = ['categoria']
    readonly_fields = ('render_icon', 'total_count')
    show_change_link = True

    def render_icon(self, obj):
        icon = "📍"
        if obj.tipo == 'EDIFICIO': icon = "🏢"
        elif obj.tipo == 'NIVEL': icon = "layers" # Ionicons name, but here we use emoji for simplicity in inline or maybe check if we can use ion-icon
        elif obj.tipo == 'ESPACIO': icon = "🚪"
        
        # Using ion-icon if supported or emoji
        if obj.tipo == 'NIVEL':
            return format_html('<div style="font-size: 1.2rem; display: flex; align-items: center; justify-content: center; height: 100%; color: #64748b;">🔢</div>')
        elif obj.tipo == 'EDIFICIO':
            return format_html('<div style="font-size: 1.2rem; display: flex; align-items: center; justify-content: center; height: 100%; color: #1e293b;">🏢</div>')
        
        return format_html('<div style="font-size: 1.2rem; display: flex; align-items: center; justify-content: center; height: 100%;">📍</div>')
    render_icon.short_description = 'Tipo'

    def total_count(self, obj):
        if not obj.pk:
            return format_html('<span style="color: #94a3b8; font-size: 0.7rem;">(Pendiente)</span>')
        count = getattr(obj, '_activos_count', 0)
        if count == 0:
            return format_html('<span style="color: #cbd5e1; font-size: 0.75rem;">Vacío</span>')
        return format_html(
            '<div style="background: #eff6ff; color: #2563eb; padding: 4px 12px; border-radius: 20px; font-weight: 700; font-size: 0.7rem; display: inline-block; border: 1px solid #dbeafe;">'
            '{} EQUIPOS'
            '</div>', count
        )
    total_count.short_description = 'Equipos'

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _activos_count=Count('activos')
        ).select_related('categoria')

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name == 'nombre':
            formfield.widget.attrs.update({'style': 'width: 250px;'})
        elif db_field.name == 'orden':
            formfield.widget.attrs.update({'style': 'width: 60px;'})
        elif db_field.name == 'descripcion':
            from django.forms import TextInput
            formfield.widget = TextInput(attrs={'style': 'width: 100%; min-width: 300px;', 'placeholder': 'Opcional...'})
        return formfield

class PlanoInline(admin.StackedInline):
    model = Plano
    extra = 0
    show_change_link = True
    fields = ('nombre', 'documento', 'archivo', 'descripcion', 'ver_visores')
    readonly_fields = ('ver_visores',)
    autocomplete_fields = ['documento']

    def ver_visores(self, obj):
        if obj.pk:
            # Aprovecha el prefetch_related('visores') del get_queryset
            visores = obj.visores.all()
            if visores:
                html = '<div style="display: flex; gap: 5px; flex-wrap: wrap;">'
                for v in visores:
                     html += f'<a href="/activos/visor/{v.pk}/" target="_blank" class="button" style="background-color: #447e9b; color: white; padding: 5px 10px; border-radius: 4px; text-decoration: none; font-size: 0.8rem;">👁️ {v.nombre}</a>'
                html += '</div>'
                return format_html(html)
            return format_html('<span style="color: #64748b; font-style: italic;">No hay visores configurados. Guarde el plano y agregue uno desde la administración de planos.</span>')
        return "-"
    ver_visores.short_description = "Visores Interactivos"

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('visores', 'documento')

class UbicacionEnPlanosInline(admin.TabularInline):
    """
    Muestra los planos donde esta ubicación ha sido dibujada/marcada (como zona hijo).
    """
    model = PinPlano
    fk_name = 'ubicacion'
    extra = 0
    verbose_name = "Aparición en Plano"
    verbose_name_plural = "Planos donde aparece esta ubicación (Zonas/Pines)"
    fields = ('link_plano', 'visor', 'preview_zona', 'abrir_visor')
    readonly_fields = ('link_plano', 'visor', 'preview_zona', 'abrir_visor')
    can_delete = False
    max_num = 0

    def link_plano(self, obj):
        if obj.visor and obj.visor.plano:
            return format_html(
                '<a href="/admin/activos/plano/{0}/change/" target="_blank" style="font-weight:bold;">📄 {1}</a>'
                '<br><span style="color:#64748b; font-size:0.8em;">Ubicación Padre: {2}</span>',
                obj.visor.plano.id,
                obj.visor.plano.nombre,
                obj.visor.plano.ubicacion.nombre if obj.visor.plano.ubicacion else "N/A"
            )
        return "-"
    link_plano.short_description = "Plano Contenedor"

    def preview_zona(self, obj):
        if obj.ancho > 0:
            return format_html(f'<span style="color:var(--primary); font-weight:600;">⬚ Zona ({int(obj.ancho)}x{int(obj.alto)}px)</span>')
        return "📍 Punto (Pin)"
    preview_zona.short_description = "Tipo Marcador"

    def abrir_visor(self, obj):
        return format_html(
            '<a href="/activos/visor/{0}/" target="_blank" class="button" style="background:#447e9b; color:white; padding:4px 10px; border-radius:4px; text-decoration:none;">'
            '👁️ Ver en Plano'
            '</a>',
            obj.visor.id
        )
    abrir_visor.short_description = "Acción"
    
    def has_add_permission(self, request, obj=None):
        return False

@admin.register(Ubicacion)
class UbicacionAdmin(ImportExportMixin, admin.ModelAdmin):
    """
    Admin para ubicaciones jerárquicas con estructura premium.
    """
    list_per_page = 50
    list_display = ('nombre_con_indentacion', 'tipo', 'padre', 'orden', 'total_hijos')
    list_display_links = ('nombre_con_indentacion',)
    list_editable = ('orden', 'tipo')
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
            'fields': (('nombre', 'tipo'), ('padre', 'orden'), 'categoria')
        }),
        ('Detalles', {
            'fields': ('descripcion',)
        }),
        ('Mantenimiento Programado', {
            'fields': ('rutinas_mantenimiento',),
            'description': 'Rutinas de mantenimiento asociadas a la categoría de esta ubicación.'
        }),
    )

    def rutinas_mantenimiento(self, obj):
        if not obj.categoria:
            return format_html('<span style="color: #94a3b8; font-style: italic;">No hay categoría asignada. Asigne una categoría (ej: "Quirófano", "Subestación") para ver las rutinas.</span>')
        
        # Buscar la categoría de mantenimiento vinculada
        m_cat = getattr(obj.categoria, 'mantenimiento_categoria', None)
        
        if not m_cat:
            return format_html(
                '<div style="background: #fff1f2; color: #be123c; padding: 10px; border-radius: 6px; border: 1px solid #fecaca;">'
                '<strong style="display:block; margin-bottom:4px;">Sin vinculación de Mantenimiento</strong>'
                'La categoría de activo <em>"{}"</em> no está vinculada a ninguna categoría de mantenimiento. '
                '<a href="/admin/mantenimiento/categoria/" target="_blank">Configure esto aquí</a>.'
                '</div>', 
                obj.categoria.nombre
            )

        from mantenimiento.models import Rutina
        # Obtener ancestros de la categoría de mantenimiento para herencia de rutinas
        m_cats_ids = []
        curr = m_cat
        while curr:
            m_cats_ids.append(curr.id)
            curr = curr.padre
            
        rutinas = Rutina.objects.filter(categoria_id__in=m_cats_ids).select_related('frecuencia', 'categoria', 'puesto_trabajo')
        
        if not rutinas.exists():
            return format_html('<span style="color: #94a3b8; font-style: italic;">No hay rutinas definidas para la categoría "{}" ni sus superiores.</span>', m_cat.nombre)
            
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
                html += f'<div style="font-size: 0.70rem; color: #94a3b8;">Heredada de: {r.categoria.nombre}</div>'
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
        return format_html(html)
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
            return format_html('<span style="color: #cbd5e1; font-size: 0.8rem;">Vacio</span>')
        return format_html('<span style="background: #f1f5f9; color: #475569; padding: 2px 10px; border-radius: 12px; font-weight: 700; font-size: 0.75rem;">{} sub-niveles</span>', count)
    total_hijos.short_description = 'Estructura'

    def total_activos(self, obj):
        # Contar activos en esta ubicación y todas sus descendientes
        from .models import Activo
        ubicaciones_ids = obj.get_descendants().values_list('id', flat=True)
        total = Activo.objects.filter(ubicacion_id__in=ubicaciones_ids).count()
        
        if total == 0:
            return format_html('<span style="color: #cbd5e1; font-size: 0.8rem;">Sin equipos</span>')
        return format_html('<span style="background: #eff6ff; color: #1d4ed8; padding: 2px 10px; border-radius: 12px; font-weight: 700; font-size: 0.75rem;">{} equipos</span>', total)
    total_activos.short_description = 'Carga de Activos'


class SmartUbicacionWidget(ForeignKeyWidget):
    """
    Widget optimizado que utiliza el caché del Resource para evitar consultas N+1.
    """
    def clean(self, value, row=None, **kwargs):
        if not value:
            return None
        
        value_str = str(value).strip()
        resource = kwargs.get('resource')
        
        # 1. Normalizar separadores y espacios (soporta: " → ", "->", " > ", "|")
        import re
        # Reemplazar cualquier flecha o pipe con espacios opcionales por un pipe limpio
        normalized_val = re.sub(r'\s*([→|>]|->)\s*', '|', value_str).strip()
        val_upper = normalized_val.upper()
        
        # 2. Intentar resolver por Clave Única (Ruta Completa) desde caché
        if resource and hasattr(resource, 'ubicacion_clave_cache'):
            if val_upper in resource.ubicacion_clave_cache:
                return resource.ubicacion_clave_cache[val_upper]
        
        # 3. Intentar resolver por Nombre Simple (solo si es único) desde caché
        if resource and hasattr(resource, 'ubicacion_nombre_cache'):
            if value_str.upper() in resource.ubicacion_nombre_cache:
                return resource.ubicacion_nombre_cache[value_str.upper()]

        # 4. Fallback: Resolución manual si el caché no lo tiene o el valor tiene jerarquía
        if '|' in normalized_val:
            parts = [p.strip() for p in normalized_val.split('|')]
            nombre_final = parts[-1]
            # Búsqueda insensible a mayúsculas
            candidatos = Ubicacion.objects.filter(nombre__iexact=nombre_final)
            for cand in candidatos:
                if cand.get_clave_unica().upper() == val_upper:
                    return cand
        
        # Fallback final: buscar por nombre simple en la DB
        return Ubicacion.objects.filter(nombre__iexact=value_str).first()

class ActivoResource(resources.ModelResource):
    marca_nombre = fields.Field(
        column_name='marca_nombre',
        attribute='modelo__marca__nombre',
        readonly=True
    )
    modelo_nombre = fields.Field(
        column_name='modelo_nombre',
        attribute='modelo',
        widget=SmartModeloWidget(Modelo, field='nombre')
    )
    categoria_nombre = fields.Field(
        column_name='categoria_nombre',
        attribute='modelo__categoria',
        widget=ForeignKeyWidget(Categoria, field='nombre'),
        readonly=True
    )
    ubicacion_nombre = fields.Field(
        column_name='ubicacion_nombre',
        attribute='ubicacion',
        widget=SmartUbicacionWidget(Ubicacion, field='nombre')
    )
    responsable_username = fields.Field(
        column_name='responsable_username',
        attribute='responsable',
        widget=SmartUserWidget(User, field='username')
    )
    padre_codigo = fields.Field(
        column_name='padre_codigo',
        attribute='padre',
        widget=SmartActivoWidget(Activo, field='codigo_interno')
    )
    familia_nombre = fields.Field(
        column_name='familia_nombre',
        attribute='familia',
        widget=SmartFamiliaWidget(Familia, field='nombre')
    )
    plano_nombre = fields.Field(
        column_name='plano_nombre',
        attribute='plano',
        widget=SmartPlanoWidget(Plano, field='nombre')
    )

    def import_field(self, field, obj, row, is_m2m=False, **kwargs):
        """Simplificado para velocidad: Solo omite si es realmente vacío"""
        value = row.get(field.column_name)
        if value is None or str(value).strip() == '':
            return
        super().import_field(field, obj, row, is_m2m=is_m2m, **kwargs)

    class Meta:
        model = Activo
        import_id_fields = ('codigo_interno',)
        fields = (
            'id', 'nombre', 'codigo_interno', 'epc', 'serie', 'referencia', 'marca_nombre', 'modelo_nombre', 
            'categoria_nombre', 'familia_nombre', 'plano_nombre', 'estado', 'ubicacion_nombre', 'responsable_username',
            'padre_codigo', 'descripcion', 'fecha_compra', 'costo', 'ubicacion_legacy', 'creado_en', 'actualizado_en'
        )
        export_order = fields
        skip_unchanged = True
        report_skipped = False  # Optimización: No cargar el reporte con miles de filas omitidas
        use_bulk = True
        batch_size = 1000  # Volvemos a un tamaño de lote más seguro y manejable
        use_transactions = True 

    def skip_row(self, instance, original, row, import_validation_errors=None, **kwargs):
        """Lógica rápida para omitir filas irrelevantes"""
        if not any(row.values()): return True
        
        # Si no hay nombre ni código, no podemos hacer nada
        nombre = str(row.get('nombre') or '').strip()
        codigo = str(row.get('codigo_interno') or '').strip()
        if not nombre and not codigo:
            return True

        # Si el objeto es nuevo (no hay original), no omitimos
        if not original:
            return False

        return super().skip_row(instance, original, row, import_validation_errors, **kwargs)

    def get_queryset(self, request):
        """Eager loading para que skip_row y exportación sean rápidos"""
        return super().get_queryset(request).select_related(
            'modelo__marca', 'modelo__categoria', 'ubicacion', 'responsable', 'familia', 'plano'
        )

    def get_bulk_update_fields(self):
        """Mapea nombres de campos del Resource a atributos reales del Modelo para Bulk Update"""
        actual_fields = {f.name for f in self._meta.model._meta.get_fields()}
        resource_fields = self.get_fields()
        
        update_fields = set()
        for f_name in super().get_bulk_update_fields():
            # Buscar el campo en el resource para ver qué atributo de modelo impacta
            res_field = next((rf for rf in resource_fields if rf.attribute and rf.column_name == f_name or rf.attribute == f_name), None)
            
            attr = res_field.attribute if res_field else f_name
            # Manejar atributos anidados (ej: modelo__nombre -> solo nos interesa 'modelo')
            base_attr = attr.split('__')[0] if attr else None
            
            if base_attr in actual_fields and base_attr != 'id':
                update_fields.add(base_attr)
                
        return list(update_fields)

    def before_import(self, dataset, *args, **kwargs):
        """Precarga cachés para velocidad y precisión en jerarquías"""
        from django.core.cache import cache
        from .models import Marca, Modelo, Categoria, Ubicacion
        from django.db.models import Count
        
        # 0. Inicializar progreso detallado
        user = kwargs.get('user')
        self._import_user = user
        self._ids_creados = [] # Para rastrear y permitir reversión
        if user:
            cache.set(f"import_progress_{user.id}", 0, 600)
            cache.set(f"import_progress_{user.id}_count", 0, 600)
            cache.set(f"import_progress_{user.id}_current", 'Preparando datos...', 600)
            cache.set(f"import_progress_{user.id}_stats", {'new': 0, 'update': 0, 'skip': 0, 'error': 0}, 600)
            cache.set(f"import_progress_{user.id}_start", __import__('time').time(), 600)
            self.total_rows = len(dataset)

        # 1. Caché Ubicaciones (Iterativo para evitar RecursionError)
        self.ubicacion_clave_cache = {}
        self.ubicacion_nombre_cache = {}
        
        all_locs = {loc.id: loc for loc in Ubicacion.objects.all()}
        nombres_count = {}
        
        for loc_id, loc in all_locs.items():
            curr_path = []
            curr = loc
            visited = set()
            while curr:
                if curr.id in visited: break # Ciclo detectado
                visited.add(curr.id)
                curr_path.append(curr.nombre)
                curr = all_locs.get(curr.padre_id)
            
            path = "|".join(reversed(curr_path)).upper()
            self.ubicacion_clave_cache[path] = loc
            nombres_count[loc.nombre.upper()] = nombres_count.get(loc.nombre.upper(), 0) + 1
        
        for loc_id, loc in all_locs.items():
            if nombres_count.get(loc.nombre.upper()) == 1:
                self.ubicacion_nombre_cache[loc.nombre.upper()] = loc
        
        self.fields['ubicacion_nombre'].widget.resource = self
        self.fields['modelo_nombre'].widget.resource = self

        # 2. Caché Marcas/Modelos/Categorías
        self.marca_cache = {m.nombre.upper(): m for m in Marca.objects.all()}
        self.modelo_cache = {m.nombre.upper(): m for m in Modelo.objects.all().select_related('marca', 'categoria')}
        self.categoria_cache = {c.nombre.upper(): c for c in Categoria.objects.all()}

        # 3. Pre-procesar Dataset para creación masiva de Marcas/Modelos
        marcas_to_create = set()
        modelos_data = {} # {mod_name: (mar_name, cat_name)}
        categorias_to_create = set()
        
        def normalize_name(name):
            if not name: return ""
            s = str(name).strip()
            if s.upper() in ('NONE', 'NULL', 'N/A'): return ""
            return s

        for row in dataset.dict:
            mod_name = normalize_name(row.get('modelo_nombre'))
            mar_name = normalize_name(row.get('marca_nombre'))
            cat_name = normalize_name(row.get('categoria_nombre'))
            
            if mod_name:
                mod_key = mod_name.upper()
                if mod_key not in self.modelo_cache:
                    modelos_data[mod_key] = (mod_name, mar_name, cat_name)
                    if mar_name and mar_name.upper() not in self.marca_cache:
                        marcas_to_create.add(mar_name)
                    if cat_name and cat_name.upper() not in self.categoria_cache:
                        categorias_to_create.add(cat_name)

        # Crear Marcas faltantes
        if marcas_to_create:
            Marca.objects.bulk_create([Marca(nombre=m) for m in marcas_to_create], ignore_conflicts=True)
            self.marca_cache = {m.nombre.upper(): m for m in Marca.objects.all()}
            
        # Crear Categorías faltantes
        if categorias_to_create:
            Categoria.objects.bulk_create([Categoria(nombre=c) for c in categorias_to_create], ignore_conflicts=True)
            self.categoria_cache = {c.nombre.upper(): c for c in Categoria.objects.all()}

        # Crear Modelos faltantes
        if modelos_data:
            new_models = []
            # Asegurar que existe GENERICO
            if "GENERICO" not in self.marca_cache:
                gen, _ = Marca.objects.get_or_create(nombre="GENERICO")
                self.marca_cache["GENERICO"] = gen

            for mod_key, (m_name, mar_name, cat_name) in modelos_data.items():
                marca = self.marca_cache.get(mar_name.upper() if mar_name else "GENERICO")
                cat = self.categoria_cache.get(cat_name.upper()) if cat_name else None
                new_models.append(Modelo(nombre=m_name, marca=marca, categoria=cat))
            
            if new_models:
                Modelo.objects.bulk_create(new_models, ignore_conflicts=True)
                # Recargar memoria con todos los modelos
                self.modelo_cache = {m.nombre.upper(): m for m in Modelo.objects.all().select_related('marca', 'categoria')}

        # 4. Caché de IDs (Ligero: solo código -> ID) para evitar cargar 75k objetos completos en RAM
        self.activo_id_cache = dict(Activo.objects.values_list('codigo_interno', 'id').iterator())
        
        # Inicializar contadores
        self._row_counter = 0
        self._stats = {'new': 0, 'update': 0, 'skip': 0, 'error': 0}

    def after_import_row(self, row, row_result, **kwargs):
        """Reporte de progreso ultra-ligero (Cada 1000 filas)"""
        if not hasattr(self, '_row_counter'): self._row_counter = 0
        self._row_counter += 1
        
        if self._row_counter % 1000 == 0 or self._row_counter == self.total_rows:
            user = self._import_user
            if user:
                from django.core.cache import cache
                percent = min(int((self._row_counter / self.total_rows) * 100), 100)
                cache.set(f"import_progress_{user.id}", percent, 300)
                cache.set(f"import_progress_{user.id}_count", self._row_counter, 300)

    def dehydrate_ubicacion_nombre(self, activo):
        """Exportar la ruta completa para evitar ambigüedad en futuras importaciones"""
        if activo.ubicacion:
            return activo.ubicacion.get_ruta_completa()
        return ""

    def dehydrate_plano_nombre(self, activo):
        if activo.plano:
            return activo.plano.numero_documento or activo.plano.nombre
        return ""

    def get_instance(self, instance_loader, row):
        codigo = row.get('codigo_interno')
        if codigo:
            # Usar caché de IDs para ver si existe
            obj_id = self.activo_id_cache.get(str(codigo))
            if obj_id:
                # Ya que necesitamos el objeto completo para actualizar, lo traemos por ID (índice primario)
                # Esto es más rápido que filtrar por código cada vez
                return Activo.objects.filter(id=obj_id).first()
        return None




class ComponenteActivoInline(admin.TabularInline):
    model = Activo
    fk_name = 'padre'
    extra = 1
    verbose_name = "Componente / Sub-equipo"
    verbose_name_plural = "Componentes / Sub-equipos (Hijos)"
    fields = ('nombre', 'codigo_interno', 'modelo', 'estado', 'ubicacion')
    autocomplete_fields = ('modelo', 'ubicacion')
    show_change_link = True

class PuntoMedicionInline(admin.TabularInline):
    model = PuntoMedicion
    extra = 1
    fields = ('nombre', 'codigo', 'unidad', 'es_acumulativo', 'valor_objetivo', 'get_valor_actual')
    readonly_fields = ('get_valor_actual',)

    @admin.display(description="Valor Actual")
    def get_valor_actual(self, obj):
        val = obj.valor_actual
        if val is not None:
            return f"{val} {obj.unidad}"
        return "---"

class DocumentoMedicionInline(admin.TabularInline):
    model = DocumentoMedicion
    extra = 1
    fields = ('punto', 'valor', 'fecha_lectura', 'tecnico', 'observaciones')
    autocomplete_fields = ('punto', 'tecnico')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "punto":
            # Si estamos en la vista de cambio de un activo (pk presente en URL)
            import re
            match = re.search(r'activo/(\d+)/change', request.path)
            if match:
                activo_id = match.group(1)
                kwargs["queryset"] = PuntoMedicion.objects.filter(activo_id=activo_id)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

class AuditoriasActivoInline(admin.TabularInline):
    model = ResultadoAuditoria
    extra = 0
    fields = ('auditoria', 'estado', 'get_ubicacion_esperada', 'get_ubicacion_encontrada', 'fecha_escaneo', 'get_sync_button')
    readonly_fields = ('auditoria', 'estado', 'get_ubicacion_esperada', 'get_ubicacion_encontrada', 'fecha_escaneo', 'get_sync_button')
    can_delete = False
    verbose_name = "Auditoría Realizada"
    verbose_name_plural = "Historial de Auditorías"

    def get_ubicacion_esperada(self, obj):
        if obj.ubicacion_esperada:
            return obj.ubicacion_esperada.ruta_completa
        return "---"
    get_ubicacion_esperada.short_description = "Ubicación Esperada"

    def get_ubicacion_encontrada(self, obj):
        if obj.ubicacion_encontrada:
            return obj.ubicacion_encontrada.ruta_completa
        return "---"
    get_ubicacion_encontrada.short_description = "Ubicación Encontrada"

    def get_sync_button(self, obj):
        if not obj.id or not obj.ubicacion_encontrada:
            return "---"
        
        # Verificar si la ubicación del activo ya coincide
        if obj.activo.ubicacion_id == obj.ubicacion_encontrada_id:
            info_sync = ""
            if obj.sincronizado:
                 info_sync = f'<div style="font-size: 0.75rem; color: #64748b; margin-top: 4px;">Por: <b>{obj.sincronizado_por.username if obj.sincronizado_por else "Sistema"}</b><br>El: {obj.fecha_sincronizacion.strftime("%d/%m/%Y %H:%M") if obj.fecha_sincronizacion else "-"}</div>'
            
            return format_html(f'<span style="color: #10b981; font-weight: bold;">✅ Sincronizado</span>{info_sync}')
        
        # Botón de acción
        url = reverse('admin:activos_activo_sync_audit_location', args=[obj.activo.id, obj.id])
        return format_html(
            '<a class="button" href="{}" style="background: #f59e0b; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold; text-decoration: none;">'
            '🔄 Actualizar Ubicación'
            '</a>',
            url
        )
    get_sync_button.short_description = "Acción de Mejora"



@admin.register(Activo)
class ActivoAdmin(ImportExportModelAdmin):
    list_per_page = 25  # Reducido para mejorar rendimiento
    resource_class = ActivoResource
    change_list_template = 'admin/activos/activo/change_list.html'

    # get_urls removed to disable Redis import


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



    
    list_display = ('nombre', 'codigo_interno', 'epc', 'descripcion', 'ultima_auditoria_display', 'get_marca_modelo', 'serie', 'get_plano_codigo', 'referencia', 'get_ubicacion_ruta')
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
    # Importar inline de Mayan
    from documentos.admin_mayan import MayanDocumentInline

    inlines = [ComponenteActivoInline, PuntoMedicionInline, DocumentoMedicionInline, AuditoriasActivoInline, MayanDocumentInline]
    readonly_fields = ('ultima_auditoria_display', 'get_marca', 'get_ubicacion_ruta', 'get_modelo_img', 'ver_en_plano', 'rutinas_aplicables', 'ordenes_programadas', 'historial_ordenes', 'crear_aviso_link', 'get_puntos_medicion_summary')
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
        from .models import Ubicacion

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
            return format_html('<span style="color: #94a3b8; font-style: italic;">No hay una categoría de activo definida para este modelo.</span>')
        
        # Buscar la categoría de mantenimiento vinculada
        m_cat = getattr(obj.modelo.categoria, 'mantenimiento_categoria', None)

        if not m_cat:
            return format_html('<span style="color: #94a3b8; font-style: italic;">La categoría "{0}" no tiene una categoría de mantenimiento vinculada.</span>', obj.modelo.categoria.nombre)

        from mantenimiento.models import Rutina
        # Obtener ancestros de la categoría de mantenimiento vinculada
        m_cats_ids = []
        curr = m_cat
        while curr:
            m_cats_ids.append(curr.id)
            curr = curr.padre
            
        rutinas = Rutina.objects.filter(categoria_id__in=m_cats_ids).select_related('frecuencia', 'categoria')
        
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
            html += f'<div style="font-size: 0.75rem; color: #64748b;">{r.categoria.nombre if r.categoria else "General"}</div>'
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
        return format_html(html)

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
            return format_html('<div style="color: #94a3b8; font-style: italic; padding: 10px; background: #f8fafc; border: 1px dashed #cbd5e1; border-radius: 8px;">No hay órdenes de trabajo programadas pendientes para este equipo.</div>')

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
        return format_html(html)
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
            return format_html('<div style="color: #94a3b8; font-style: italic; padding: 10px; background: #f8fafc; border: 1px dashed #cbd5e1; border-radius: 8px;">No hay historial de órdenes de trabajo para este equipo.</div>')

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
        return format_html(html)
    historial_ordenes.short_description = "Historial de Órdenes de Trabajo"

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
        return format_html('<span style="color: #94a3b8; font-style: italic;">El modelo no tiene imagen asociada</span>')
    get_modelo_img.short_description = 'Imagen del Modelo'

    def get_parent_info(self, obj):
        if obj.padre:
            return format_html('<span style="color: #64748b; font-size: 0.85rem;">↳ {}</span>', obj.padre.nombre)
        return format_html('<span style="color: #10b981; font-weight: bold; font-size: 0.75rem;">PRINCIPAL</span>')
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
            self.change_list_template = 'admin/activos/activo/change_list.html'
            
        return super().changelist_view(request, extra_context=extra_context)
    
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

    @admin.display(description="Código de Plano", ordering='plano__nombre')
    def get_plano_codigo(self, obj):
        if obj.plano:
            return obj.plano.numero_documento or obj.plano.nombre
        return "---"

    @admin.display(description="Última Auditoría", ordering='ultima_auditoria_fecha')
    def ultima_auditoria_display(self, obj):
        fecha = getattr(obj, 'ultima_auditoria_fecha', None)
        if not fecha:
            return format_html('<span style="color: #94a3b8; font-style: italic;">Nunca auditado</span>')
        
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
            return format_html('<span style="color: #999;">❌ No ubicado en planos</span>')
        
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
        return format_html(html)
    ver_en_plano.short_description = 'Ubicación en Planos'

    fieldsets = (
        ('Identificación', {
            'fields': ('nombre', ('codigo_interno', 'epc'), 'referencia', 'familia', ('get_marca', 'modelo'), ('serie', 'padre'), 'get_ubicacion_ruta', 'get_modelo_img')
        }),
        ('Detalles Técnicos', {
            'fields': ('descripcion', 'foto', 'marca_legacy', 'modelo_legacy')
        }),
        ('Estado y Ubicación', {
            'fields': ('estado', 'ubicacion', 'plano', 'ubicacion_legacy', 'responsable', 'ver_en_plano', 'crear_aviso_link', 'ultima_auditoria_display')
        }),
        ('Mantenimiento Preventivo', {
            'fields': ('rutinas_aplicables', 'ordenes_programadas', 'historial_ordenes'),
            'description': 'Información sobre rutinas aplicables, órdenes pendientes e historial de mantenimiento.'
        }),
    )

    change_form_template = 'admin/activos/activo/change_form.html'

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
            path('<int:activo_id>/sync-audit/<int:resultado_id>/', self.admin_site.admin_view(self.sync_audit_location), name='activos_activo_sync_audit_location'),
            path('import-background/', self.admin_site.admin_view(self.import_background), name='activos_activo_import_background'),
            path('import-process/', self.admin_site.admin_view(self.import_process), name='activos_activo_import_process'),
            path('import-progress/', self.admin_site.admin_view(self.import_progress), name='activos_activo_import_progress'),
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
            return format_html('<span style="color: #94a3b8; font-style: italic;">No hay puntos de medición configurados para este equipo.</span>')
        
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
        return format_html(html)

@admin.register(PuntoMedicion)
class PuntoMedicionAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'activo', 'codigo', 'unidad', 'es_acumulativo', 'valor_objetivo')
    list_filter = ('es_acumulativo', 'unidad')
    search_fields = ('nombre', 'codigo', 'activo__nombre', 'activo__codigo_interno')
    list_select_related = ('activo',)
    autocomplete_fields = ('activo',)

@admin.register(DocumentoMedicion)
class DocumentoMedicionAdmin(admin.ModelAdmin):
    list_display = ('punto', 'valor', 'fecha_lectura', 'tecnico', 'orden_trabajo')
    list_filter = ('fecha_lectura', 'tecnico')
    list_select_related = ('punto__activo', 'tecnico', 'orden_trabajo')
    search_fields = ('punto__nombre', 'punto__activo__nombre', 'observaciones')
    autocomplete_fields = ('punto', 'tecnico', 'orden_trabajo')


# Registro robusto para evitar AlreadyRegistered
class RegistroImportacionAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'fecha', 'usuario', 'estado', 'stats_summary', 'revert_button')
    list_filter = ('estado', 'fecha', 'usuario')
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
