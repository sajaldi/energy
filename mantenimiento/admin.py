from datetime import datetime, timedelta
import time
import os
import sys
from django.db import models
from django.db.models import Count
from django.contrib import admin, messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from import_export.admin import ImportExportModelAdmin
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget, DurationWidget
from .models import Tipo, Frecuencia, Rutina, PasoRutina, Horario, DiaHorario, RestriccionCalendario, Programacion, OrdenTrabajo, Aviso, PlanificacionMensual, CierreOrdenTrabajo, PuestoTrabajo, TecnicoPuesto, ValorPasoOrden, Falla, FotoAviso
from activos.models import Categoria as CategoriaActivo
from django.utils.safestring import mark_safe
from django.urls import reverse, path
from django.contrib.auth.models import User
from inventarios.models import MovimientoInventario
import datetime as dt_python
from import_export.widgets import ForeignKeyWidget, DurationWidget, ManyToManyWidget, DateTimeWidget
from activos.models import Activo, Ubicacion
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.core.cache import cache

class ProgressResourceMixin:
    """
    Mixin para que el Resource pueda reportar progreso a Celery y Caché.
    """
    celery_task = None
    cache_key = None
    total_rows = 0
    current_row = 0

    def after_import_row(self, row, row_result, row_number=None, **kwargs):
        self.current_row += 1
        # Log to terminal for user to see in Celery logs
        if self.current_row <= 5 or self.current_row % 10 == 0 or self.current_row == self.total_rows:
             print(f"[DEBUG] [Resource] Procesada fila {self.current_row}/{self.total_rows}")
        
        # Reportar cada 10 filas o al final
        if self.celery_task and (self.current_row <= 5 or self.current_row % 10 == 0 or self.current_row == self.total_rows):
            percent = int((self.current_row / self.total_rows) * 100) if self.total_rows > 0 else 0
            progress_info = {
                'current': self.current_row,
                'total': self.total_rows,
                'percent': percent,
                'status': f'Importando fila {self.current_row}/{self.total_rows}...'
            }
            if self.cache_key:
                cache.set(self.cache_key, progress_info, 3600)
            self.celery_task.update_state(state='PROGRESS', meta=progress_info)
            sys.stdout.flush()
        super().after_import_row(row, row_result, **kwargs)

class TipoHierarchicalWidget(ForeignKeyWidget):
    """
    Widget para Tipo que resuelve jerárquicamente por nombre.
    Soporta: "Padre -> Hijo", "Padre | Hijo", "Nombre Simple".
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cache = {}

    def clean(self, value, row=None, *args, **kwargs):
        val_str = str(value).strip()
        if not val_str: return None
        
        # Cache simple para evitar re-consultar el mismo nombre exacto en el mismo import
        if val_str in self._cache:
            return self._cache[val_str]

        import re
        parts = [p.strip() for p in re.split(r'\s*(?:->|\||-)\s*', val_str) if p.strip()]
        if not parts: return None
        
        leaf_name = parts[-1]
        candidates = self.model.objects.filter(nombre__iexact=leaf_name)
        count = candidates.count()
        
        result = None
        if count == 0:
            raise ValueError(f"No existe Tipo con nombre '{leaf_name}'")
        elif count == 1:
            result = candidates.first()
        elif len(parts) > 1:
            parent_name = parts[-2]
            filtered = candidates.filter(padre__nombre__iexact=parent_name)
            if filtered.count() == 1:
                result = filtered.first()
            elif filtered.count() > 1:
                raise ValueError(f"Ambigüedad: Múltiples '{leaf_name}' tienen padre '{parent_name}'.")
            else:
                raise ValueError(f"Conflicto: Se encontró '{leaf_name}' pero ninguno pertenece a '{parent_name}'.")
        else:
            names = [f"{c.nombre} (Padre: {c.padre})" for c in candidates[:3]]
            raise ValueError(f"Ambigüedad: '{leaf_name}' existe {count} veces. Usa 'Padre -> Hijo'. Ej: {', '.join(names)}")
            
        self._cache[val_str] = result
        return result

class TipoResource(ProgressResourceMixin, resources.ModelResource):
    """
    Resource para import/export de tipos jerárquicos.
    Permite importar usando el nombre del padre para mayor facilidad.
    """
    padre = fields.Field(
        column_name='padre',
        attribute='padre',
        widget=TipoHierarchicalWidget(Tipo, field='nombre')
    )
    
    categoria_activo = fields.Field(
        column_name='categoria_activo',
        attribute='categoria_activo',
        widget=ForeignKeyWidget(CategoriaActivo, field='nombre')
    )
    
    ruta_completa = fields.Field(
        column_name='ruta_completa',
        attribute='ruta_completa',
        readonly=True
    )
    
    class Meta:
        model = Tipo
        fields = ('id', 'codigo', 'ruta_completa', 'nombre', 'padre', 'categoria_activo', 'descripcion')
        export_order = ('id', 'codigo', 'ruta_completa', 'nombre', 'padre', 'categoria_activo', 'descripcion')
        readonly_fields = ('ruta_completa',)
        skip_unchanged = True
        report_skipped = True
        use_transactions = False # Desactivado para evitar bloqueos en SQLite con Celery
        import_id_fields = ('id', 'codigo')

    def before_import_row(self, row, **kwargs):
        """
        Lógica personalizada para:
        1. Priorizar ID si viene en el archivo.
        2. Limpiar nombres de padres.
        """
        # Si viene ID, nos aseguramos que sea el primer campo de búsqueda
        # Aunque django-import-export ya maneja import_id_fields en orden.
        pass

    def get_instance(self, instance_loader, row):
        """
        Sobrescribe la búsqueda de instancia para priorizar ID, 
        y si no, usar Código. Útil para actualizaciones sparse.
        """
        obj_id = row.get('id')
        if obj_id:
            try:
                return self.get_queryset().get(id=obj_id)
            except (Tipo.DoesNotExist, ValueError):
                pass
        
        codigo = row.get('codigo')
        if codigo:
            try:
                return self.get_queryset().get(codigo=codigo)
            except (Tipo.DoesNotExist, ValueError):
                pass
        
        return None

    def import_field(self, field, obj, row, is_m2m=False, **kwargs):
        """
        Sobrescribimos para obviar campos vacíos en la importación (Sparse Update).
        Si el valor en el row está vacío/None, no se toca el atributo del objeto.
        """
        # Si el campo está en el row pero viene vacío, lo ignoramos para no sobreescribir con null/blanco
        column_name = field.column_name
        
        # El ID y el Código si podemos permitirlos (aunque usualmente ya estarán)
        if column_name in ['id', 'codigo']:
            return super().import_field(field, obj, row, is_m2m, **kwargs)

        if column_name in row:
            value = row.get(column_name)
            if value is None or str(value).strip() == '':
                return # No hacer nada si viene vacío (Sparse Update)
        
        super().import_field(field, obj, row, is_m2m, **kwargs)

from django import forms

class SubtipoInline(admin.TabularInline):
    model = Tipo
    fk_name = 'padre'
    extra = 1
    verbose_name = "Subtipo"
    verbose_name_plural = "Subtipos"
    show_change_link = True
    fields = ('nombre', 'descripcion')
    # Forzar que la descripción sea un input de texto en lugar de un textarea para que quepa en la tabla
    formfield_overrides = {
        models.TextField: {'widget': forms.TextInput(attrs={'style': 'width: 100%; min-width: 400px;'})},
        models.CharField: {'widget': forms.TextInput(attrs={'style': 'width: 100%; min-width: 250px;'})},
    }
    
    class Media:
        css = {
            'all': ('admin/css/forms.css',) # Opcional, pero útil para cargar estilos base
        }

class RutinaInline(admin.TabularInline):
    model = Rutina
    extra = 1
    fields = ('nombre', 'frecuencia', 'tiempo_estimado', 'cantidad_tecnicos')
    readonly_fields = ('nombre',)
    autocomplete_fields = ('frecuencia',)
    show_change_link = True
    # classes = ('collapse',)  <-- Eliminado para que aparezca abierto por defecto

@admin.register(Tipo)
class TipoAdmin(ImportExportModelAdmin):
    """
    Admin para tipos jerárquicos con estructura simple.
    """
    list_per_page = 50
    resource_class = TipoResource
    change_list_template = "admin/mantenimiento/tipo/change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('import-celery/', self.admin_site.admin_view(self.import_celery_view), name='tipo_import_celery'),
        ]
        return custom_urls + urls

    def import_celery_view(self, request):
        from django.shortcuts import redirect
        return redirect('mantenimiento:tipo_import_background')

    list_display = ('codigo', 'nombre', 'padre', 'categoria_activo', 'descripcion')
    search_fields = ('codigo', 'nombre')
    list_filter = ('padre', 'categoria_activo')
    autocomplete_fields = ('padre', 'categoria_activo')
    inlines = [SubtipoInline, RutinaInline]


@admin.register(Frecuencia)
class FrecuenciaAdmin(admin.ModelAdmin):
    list_per_page = 50
    list_display = ('nombre', 'dias')
    ordering = ('dias',)
    search_fields = ('nombre',)

@admin.register(PuestoTrabajo)
class PuestoTrabajoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'descripcion', 'ver_dashboard_link')
    search_fields = ('nombre',)

    def ver_dashboard_link(self, obj):
        url = reverse('mantenimiento:dashboard_cargas')
        return mark_safe(f'<a class="button" href="{url}" style="background: #4f46e5; color: white; font-weight: 700;">📊 VER DASHBOARD DE CARGAS</a>')
    ver_dashboard_link.short_description = 'Dashboard'

from .models import Tipo, Frecuencia, Rutina, PasoRutina, Horario, DiaHorario, RestriccionCalendario, Programacion, OrdenTrabajo, Aviso, PlanificacionMensual, CierreOrdenTrabajo, PuestoTrabajo, TecnicoPuesto, ValorPasoOrden, Falla, FotoAviso, Empresa

class EmpresaResource(resources.ModelResource):
    class Meta:
        model = Empresa
        fields = ('id', 'nombre', 'descripcion', 'activo', 'creado_en')
        export_order = ('id', 'nombre', 'descripcion', 'activo', 'creado_en')
        skip_unchanged = True
        report_skipped = True
        import_id_fields = ('id',)

class PersonalInline(admin.TabularInline):
    model = TecnicoPuesto
    extra = 0
    fields = ('get_nombre_completo', 'puesto', 'dni', 'disponible')
    readonly_fields = ('get_nombre_completo',)
    show_change_link = True
    verbose_name = "Miembro"
    verbose_name_plural = "Miembros de la Empresa"

    def get_nombre_completo(self, obj):
        if not obj.pk: return "-"
        if obj.user:
            return obj.user.get_full_name() or obj.user.username
        return f"{obj.nombre} {obj.apellido}".strip() or "Sin nombre"
    get_nombre_completo.short_description = 'Nombre'

@admin.register(Empresa)
class EmpresaAdmin(ImportExportModelAdmin):
    resource_class = EmpresaResource
    list_display = ('nombre', 'activo', 'creado_en')
    search_fields = ('nombre',)
    list_filter = ('activo',)
    inlines = [PersonalInline]

# --- RESOURCE PERSONALIZADO PARA TÉCNICOS ---
class TecnicoPuestoResource(resources.ModelResource):
    """
    IMPORTACIÓN DE PERSONAL (Técnicos)
    
    Crea automáticamente el Usuario de Django si no existe (basado en 'username' o 'email').
    Busca/Asigna PuestoTrabajo y Empresa por nombre.
    """
    # Campos directos de TecnicoPuesto
    nombre = fields.Field(attribute='nombre', column_name='nombre')
    apellido = fields.Field(attribute='apellido', column_name='apellido')
    dni = fields.Field(attribute='dni', column_name='dni')
    fecha_nacimiento = fields.Field(attribute='fecha_nacimiento', column_name='fecha_nacimiento')
    tipo_sangre = fields.Field(attribute='tipo_sangre', column_name='tipo_sangre')
    horas_semanales_max = fields.Field(attribute='horas_semanales_max', column_name='horas_semanales_max')
    disponible = fields.Field(attribute='disponible', column_name='disponible')
    
    # Relaciones FK (Búsqueda por nombre)
    puesto_nombre = fields.Field(
        column_name='puesto',
        attribute='puesto',
        widget=ForeignKeyWidget(PuestoTrabajo, field='nombre')
    )
    empresa_nombre = fields.Field(
        column_name='empresa',
        attribute='empresa',
        widget=ForeignKeyWidget(Empresa, field='nombre')
    )
    
    # Campos virtuales para vincular el USER (Opcional)
    username = fields.Field(column_name='username', attribute='user', widget=ForeignKeyWidget(User, 'username'))
    email = fields.Field(column_name='email') # Se maneja manualmente en before_import_row
    password = fields.Field(column_name='password') # Se maneja manualmente en before_import_row

    class Meta:
        model = TecnicoPuesto
        import_id_fields = ('dni',) # Usamos DNI como clave principal de actualización si existe
        fields = ('dni', 'username', 'nombre', 'apellido', 'email', 'puesto_nombre', 'empresa_nombre', 
                  'fecha_nacimiento', 'tipo_sangre', 'horas_semanales_max', 'disponible', 'password')
        export_order = fields
        skip_unchanged = True
        report_skipped = True

    def before_import_row(self, row, **kwargs):
        """
        Lógica CRÍTICA: 
        1. Asegurar que el USER exista o crearlo antes de que import-export intente asignar la FK.
        2. ACTUALIZACIÓN PARCIAL: Eliminar campos vacíos para que solo se actualicen los que tienen valor.
        """
        # PASO 0: Limpiar campos vacíos para permitir actualizaciones parciales
        # Esto permite que si una celda está vacía, NO se sobrescriba el valor existente
        empty_values = ['', 'None', 'nan', 'NULL', None]
        keys_to_remove = []
        for key, value in row.items():
            if value in empty_values or (isinstance(value, str) and value.strip() in empty_values):
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del row[key]
        
        username = str(row.get('username') or '').strip()
        email = str(row.get('email') or '').strip()
        dni = str(row.get('dni') or '').strip()
        
        # 1. Si no hay username, simplemente aseguramos que el campo 'user' esté nulo en el row
        # para que el ForeignKeyWidget lo limpie o lo deje nulo.
        if not username or username.lower() in ['none', 'nan', 'null', '']:
            row['username'] = None
            # No retornamos, para que se procesen el resto de los campos (nombre, apellido, etc)
            user = None
        else:
            # 2. Buscar/Crear Usuario
            user = User.objects.filter(username=username).first()
            if not user and email:
                user = User.objects.filter(email=email).first()
                
            if not user:
                # CREAR USUARIO NUEVO
                try:
                    first_name = row.get('nombre') or ''
                    last_name = row.get('apellido') or ''
                    password = row.get('password') or dni or '123456'
                    
                    user = User.objects.create_user(
                        username=username, 
                        email=email, 
                        password=str(password),
                        first_name=str(first_name),
                        last_name=str(last_name)
                    )
                    user.is_staff = True
                    user.save()
                    print(f"[Import Personal] Usuario creado: {username}")
                except Exception as e:
                    print(f"[Import Personal] Error creando usuario {username}: {e}")
                    user = None

        # 3. Sincronización de datos del usuario si existe
        if user:
            changed = False
            nombre_row = row.get('nombre')
            apellido_row = row.get('apellido')
            email_row = row.get('email')
            
            if nombre_row and user.first_name != str(nombre_row):
                user.first_name = str(nombre_row)
                changed = True
            if apellido_row and user.last_name != str(apellido_row):
                user.last_name = str(apellido_row)
                changed = True
            if email_row and user.email != str(email_row):
                user.email = str(email_row)
                changed = True
            
            if changed:
                user.save()
            
            # Inyectar el username real por si acaso el widget lo necesita
            row['username'] = user.username

    def get_instance(self, instance_loader, row):
        # Intentar coincidencia por DNI primero (más seguro)
        dni = row.get('dni')
        if dni:
            return TecnicoPuesto.objects.filter(dni=dni).first()
            
        # Si no hay DNI, intentar por Usuario
        username = row.get('username')
        if username:
            return TecnicoPuesto.objects.filter(user__username=username).first()
            
        return None

@admin.register(TecnicoPuesto)
class TecnicoPuestoAdmin(ImportExportModelAdmin):
    resource_class = TecnicoPuestoResource
    change_list_template = 'admin/mantenimiento/tecnicopuesto/change_list.html' # Template custom con botón

    list_display = ('get_nombre_completo', 'puesto', 'empresa', 'dni', 'get_carga_semanal', 'disponible')
    list_filter = ('empresa', 'puesto', 'disponible', 'tipo_sangre')
    search_fields = ('nombre', 'apellido', 'user__username', 'user__first_name', 'user__last_name', 'puesto__nombre', 'dni', 'empresa__nombre')
    autocomplete_fields = ('user', 'puesto', 'empresa')
    
    fieldsets = (
        ('Información de Identidad', {
            'fields': ('user', 'nombre', 'apellido', 'dni')
        }),
        ('Información Profesional', {
            'fields': ('puesto', 'empresa', 'disponible')
        }),
        ('Información Personal', {
            'fields': ('fecha_nacimiento', 'tipo_sangre', 'fecha_alta')
        }),
        ('Capacidad', {
            'fields': ('horas_semanales_max',)
        }),
    )

    def get_nombre_completo(self, obj):
        if obj.user:
            return obj.user.get_full_name() or obj.user.username
        return f"{obj.nombre} {obj.apellido}".strip() or "Sin nombre"
    get_nombre_completo.short_description = 'Nombre Completo'
    get_nombre_completo.admin_order_field = 'nombre'

    def get_carga_semanal(self, obj):
        from .models import OrdenTrabajo
        from django.utils import timezone
        
        now = timezone.now()
        monday = now - timedelta(days=now.weekday())
        sunday = monday + timedelta(days=6)
        
        # Convertir fechas a datetimes conscientes
        q_start = timezone.make_aware(datetime.combine(monday, datetime.min.time()))
        q_end = timezone.make_aware(datetime.combine(sunday, datetime.max.time()))
        
        ots = OrdenTrabajo.objects.filter(
            tecnico=obj.user,
            inicio_programado__gte=q_start,
            inicio_programado__lte=q_end
        )
        
        total_horas = 0
        for ot in ots:
            if ot.inicio_programado and ot.fin_programado:
                total_horas += (ot.fin_programado - ot.inicio_programado).total_seconds() / 3600
        
        pct = (total_horas / float(obj.horas_semanales_max) * 100) if obj.horas_semanales_max > 0 else 0
        
        color = '#10b981' # Success green
        if pct > 100: color = '#ef4444' # Danger red
        elif pct > 80: color = '#f59e0b' # Warning orange
        
        return mark_safe(f'<b style="color: {color}; font-size: 13px;">{pct:.1f}%</b> <small style="color: #64748b;">({total_horas:.1f}h / {obj.horas_semanales_max}h)</small>')
    get_carga_semanal.short_description = 'Carga esta Semana'

    def get_urls(self):
        urls = super().get_urls()
        from .views import import_personal
        custom_urls = [
            path('import-background/', self.admin_site.admin_view(import_personal.import_personal_background), name='mantenimiento_tecnicopuesto_import_background'),
            path('import-background/process/', csrf_exempt(self.admin_site.admin_view(import_personal.import_personal_process)), name='mantenimiento_tecnicopuesto_import_process'),
            path('import-background/progress/', self.admin_site.admin_view(import_personal.import_personal_progress), name='mantenimiento_tecnicopuesto_import_progress'),
            path('import-background/template/', self.admin_site.admin_view(self.download_template_view), name='mantenimiento_tecnicopuesto_import_template'),
        ]
        return custom_urls + urls

    def download_template_view(self, request):
        """Genera un archivo Excel vacío con las cabeceras correoctas"""
        dataset = TecnicoPuestoResource().export(queryset=TecnicoPuesto.objects.none())
        response = HttpResponse(dataset.xlsx, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="plantilla_importacion_personal.xlsx"'
        return response

class FlexibleDurationWidget(DurationWidget):
    """
    Widget de duración ultra-flexible que soporta:
    - Formatos HH:MM (ej: 08:00 -> 8 horas)
    - Objetos datetime.time de Excel
    - Números decimales (ej: 1.5 -> 1.5 horas)
    - Formato estándar de Django (D HH:MM:SS)
    """
    def clean(self, value, row=None, *args, **kwargs):
        if not value:
            return None
        
        # 1. Si ya es un objeto timedelta o similar, dejarlo pasar
        if isinstance(value, dt_python.timedelta):
            return value
            
        # 2. Si es un objeto time de Python (común en imports de Excel/tablib)
        if isinstance(value, dt_python.time):
            return dt_python.timedelta(hours=value.hour, minutes=value.minute, seconds=value.second)

        val_str = str(value).strip()
        
        # 3. Caso HH:MM (muy común en Excel)
        if ":" in val_str and val_str.count(":") == 1:
            try:
                h, m = val_str.split(":")
                return dt_python.timedelta(hours=int(h), minutes=int(m))
            except (ValueError, TypeError):
                pass
        
        # 4. Caso HH:MM:SS
        if ":" in val_str and val_str.count(":") == 2:
            try:
                h, m, s = val_str.split(":")
                return dt_python.timedelta(hours=int(h), minutes=int(m), seconds=int(s))
            except (ValueError, TypeError):
                pass

        # 5. Caso número decimal (asumimos que son HORAS)
        try:
            return dt_python.timedelta(hours=float(val_str))
        except (ValueError, TypeError):
            pass

        # Fallback al widget original de import-export
        return super().clean(value, row, *args, **kwargs)

class RutinaResource(ProgressResourceMixin, resources.ModelResource):
    """
    Resource personalizado para exportar/importar rutinas.
    
    IMPORTACIÓN: nombre, tipo_nombre, frecuencia_nombre, descripcion, tiempo_estimado, cantidad_tecnicos
    EXPORTACIÓN: Incluye todos los campos con nombres legibles + ruta completa del tipo
    """
    nombre = fields.Field(
        column_name='nombre',
        attribute='nombre'
    )
    
    codigo_rutina = fields.Field(
        column_name='codigo_rutina',
        attribute='codigo_rutina'
    )
    
    tipo_nombre = fields.Field(
        column_name='tipo_nombre',
        attribute='tipo',
        widget=TipoHierarchicalWidget(Tipo, field='nombre')
    )
    
    tipo_ruta = fields.Field(
        column_name='tipo_ruta',
        readonly=True
    )
    
    frecuencia_nombre = fields.Field(
        column_name='frecuencia_nombre',
        attribute='frecuencia',
        widget=ForeignKeyWidget(Frecuencia, field='nombre')
    )
    
    def get_instance(self, instance_loader, row):
        """
        Prioriza búsqueda por ID, luego por codigo_rutina.
        """
        obj_id = row.get('id')
        if obj_id:
            try:
                return self.get_queryset().get(id=obj_id)
            except (Rutina.DoesNotExist, ValueError):
                pass

        codigo = row.get('codigo_rutina')
        if codigo:
            try:
                return self.get_queryset().get(codigo_rutina=str(codigo).strip())
            except (Rutina.DoesNotExist, ValueError):
                pass
        return None
    
    tiempo_estimado = fields.Field(
        column_name='tiempo_estimado',
        attribute='tiempo_estimado',
        widget=FlexibleDurationWidget()
    )
    
    def skip_row(self, instance, original, row, import_validation_errors=None, **kwargs):
        """
        Omitir el registro si no tiene código de rutina.
        """
        codigo = row.get('codigo_rutina')
        if not codigo or str(codigo).strip() in ['None', 'nan', 'NULL', '']:
            return True
        return super().skip_row(instance, original, row, import_validation_errors, **kwargs)

    def before_import_row(self, row, **kwargs):
        """Limpia los valores 'None' y quita espacios de los campos clave"""
        for key in list(row.keys()):
            val = row.get(key)
            if val is None:
                continue
            
            val_str = str(val).strip()
            # Limpiar nulos de Excel/CSV
            if val_str.lower() in ['none', 'nan', 'null', '']:
                row[key] = None
            else:
                # Quitar espacios al inicio y final de los strings
                if isinstance(val, str):
                    row[key] = val.strip()
                else:
                    row[key] = val_str

    def import_field(self, field, obj, row, is_m2m=False, **kwargs):
        """
        Sparse Update: No sobrescribir con valores vacíos.
        """
        column_name = field.column_name
        
        # El ID y el Código si podemos permitirlos
        if column_name in ['id', 'codigo_rutina']:
            return super().import_field(field, obj, row, is_m2m, **kwargs)

        if column_name in row:
            value = row.get(column_name)
            if value is None or str(value).strip() == '':
                return # No hacer nada si viene vacío (Sparse Update)
        
        super().import_field(field, obj, row, is_m2m, **kwargs)

    class Meta:
        model = Rutina
        import_id_fields = ('id', 'codigo_rutina')
        fields = ('id', 'codigo_rutina', 'nombre', 'tipo_nombre', 'tipo_ruta', 
                  'frecuencia_nombre', 'descripcion', 
                  'tiempo_estimado', 'cantidad_tecnicos', 'herramientas', 'es_invasiva')
        export_order = ('id', 'codigo_rutina', 'nombre', 'tipo_nombre', 'tipo_ruta',
                       'frecuencia_nombre', 'tiempo_estimado', 
                       'cantidad_tecnicos', 'herramientas', 'es_invasiva', 'descripcion')
        skip_unchanged = True
        report_skipped = True
        use_transactions = False # Desactivado para evitar bloqueos en SQLite con Celery
        # use_bulk = False  # Quitado para que use el default (True) igual que TipoResource
    
    def dehydrate_tipo_ruta(self, rutina):
        """Exporta la ruta completa del tipo"""
        if rutina.tipo:
            return rutina.tipo.get_ruta_completa()
        return ''

class CachedForeignKeyWidget(ForeignKeyWidget):
    """
    ForeignKeyWidget que usa un caché en memoria para evitar queries por fila.
    El caché se inyecta externamente via set_cache().
    """
    _cache = None

    def set_cache(self, cache_dict):
        self._cache = cache_dict

    def clean(self, value, row=None, *args, **kwargs):
        if not value:
            return None
        val = str(value).strip()
        if not val or val.lower() in ('none', 'nan', 'null'):
            return None
        if self._cache is not None:
            result = self._cache.get(val) or self._cache.get(val.lower())
            if result:
                return result
            raise ValueError(f"'{val}' no encontrado en {self.model.__name__}")
        return super().clean(value, row, *args, **kwargs)


class CachedManyToManyCodeWidget(ManyToManyWidget):
    """
    Widget M2M que usa caché en memoria para resolver codigos_internos.
    """
    _cache = None

    def set_cache(self, cache_dict):
        self._cache = cache_dict

    def clean(self, value, row=None, *args, **kwargs):
        if not value:
            return self.model.objects.none()
        
        import unicodedata
        def _normalize_key(text):
            if not text: return ""
            # Quita acentos y pasa a minúsculas
            text = unicodedata.normalize('NFD', str(text))
            text = "".join([c for c in text if unicodedata.category(c) != 'Mn'])
            return text.lower().strip()

        codes = [c.strip() for c in str(value).split(',') if c.strip()]
        if self._cache is not None:
            pks = []
            for c in codes:
                c_norm = _normalize_key(c)
                if c_norm in self._cache:
                    pks.append(self._cache[c_norm].pk)
                else:
                    # Intento secundario si llega un ID directamente?
                    # No necesario en este momento, fallback cubre
                    pass
            return self.model.objects.filter(pk__in=pks)
        
        # Fallback query si no hay caché (Menos preciso con acentos)
        from django.db.models import Q
        q_objs = Q()
        for c in codes:
            q_objs |= Q(codigo_interno__iexact=c) | Q(nombre__iexact=c)
        return self.model.objects.filter(q_objs)

    def render(self, value, obj=None):
        if not value:
            return ""
        return ", ".join([str(o.codigo_interno) for o in value.all()])


class ManyToManyCodeWidget(ManyToManyWidget):
    """
    Widget para ManyToMany que usa codigo_interno en lugar de ID.
    Soporta múltiples códigos separados por coma.
    """
    def clean(self, value, row=None, *args, **kwargs):
        if not value:
            return self.model.objects.none()
        
        codes = [c.strip() for c in str(value).split(',') if c.strip()]
        return self.model.objects.filter(codigo_interno__in=codes)

    def render(self, value, obj=None):
        if not value:
            return ""
        return ", ".join([str(obj.codigo_interno) for obj in value.all()])

class CachedHierarchicalWidget(ForeignKeyWidget):
    """
    Widget de ubicación con caché. Pre-carga todas las ubicaciones y resuelve
    jerárquicamente sin queries adicionales.
    """
    _cache_by_name = None  # nombre_lower -> [lista de ubicaciones]
    _parent_map = None     # ubicacion_id -> nombre_padre

    def set_cache(self, ubicaciones_by_name, parent_map):
        self._cache_by_name = ubicaciones_by_name
        self._parent_map = parent_map

    def clean(self, value, row=None, *args, **kwargs):
        val_str = str(value).strip()
        if not val_str:
            return None
        
        # Si no hay caché, fallback a query directa
        if self._cache_by_name is None:
            return super().clean(value, row, *args, **kwargs)
            
        import re
        parts = [p.strip() for p in re.split(r'\s*(?:->|\||-)\s*', val_str) if p.strip()]
        
        if not parts:
            return None
            
        leaf_name = parts[-1].lower()
        candidates = self._cache_by_name.get(leaf_name, [])
        
        if not candidates:
            raise ValueError(f"No existe ubicación con nombre '{parts[-1]}'")
            
        if len(candidates) == 1:
            return candidates[0]
            
        # Desambiguación por padre
        if len(parts) > 1:
            parent_name = parts[-2].lower()
            filtered = [c for c in candidates if self._parent_map.get(c.id, '').lower() == parent_name]
            if len(filtered) == 1:
                return filtered[0]
            if len(filtered) > 1:
                raise ValueError(f"Ambigüedad persistente: {len(filtered)} ubicaciones '{parts[-1]}' tienen padre '{parts[-2]}'.")
            raise ValueError(f"Conflicto: Se encontró '{parts[-1]}' pero ninguno pertenece a '{parts[-2]}'.")
            
        names = [f"{c.nombre} (Padre: {self._parent_map.get(c.id, 'N/A')})" for c in candidates[:3]]
        raise ValueError(f"Ambigüedad: '{parts[-1]}' existe {len(candidates)} veces. Usa formato 'Padre -> Hijo'. Ejemplos: {', '.join(names)}...")


class SmartHierarchicalWidget(ForeignKeyWidget):
    """
    Widget inteligente que resuelve ubicaciones jerárquicas desambiguando por el padre.
    Soporta formatos: "Padre -> Hijo", "Padre | Hijo", "Padre - Hijo".
    """
    def clean(self, value, row=None, *args, **kwargs):
        val_str = str(value).strip()
        if not val_str:
            return None
            
        import re
        # Dividir por separadores comunes
        parts = [p.strip() for p in re.split(r'\s*(?:->|\||-)\s*', val_str) if p.strip()]
        
        if not parts:
            return None
            
        leaf_name = parts[-1]
        
        # 1. Búsqueda por nombre exacto (case-insensitive)
        candidates = self.model.objects.filter(nombre__iexact=leaf_name)
        
        count = candidates.count()
        if count == 0:
            raise ValueError(f"No existe ubicación con nombre '{leaf_name}'")
            
        if count == 1:
            return candidates.first()
            
        # 2. Desambiguación usando el padre inmediato (si existe en el string)
        if len(parts) > 1:
            parent_name = parts[-2]
            # Filtrar aquellos candidatos cuyo padre llame igual
            filtered = candidates.filter(padre__nombre__iexact=parent_name)
            
            if filtered.count() == 1:
                return filtered.first()
                
            if filtered.count() > 1:
                raise ValueError(f"Ambigüedad persistente: {filtered.count()} ubicaciones '{leaf_name}' tienen padre '{parent_name}'.")
                
            # Si no coincide el padre directo, reportar error claro
            raise ValueError(f"Conflicto: Se encontró '{leaf_name}' pero ninguno pertenece a '{parent_name}'.")
            
        # Si hay duplicados y no se dio contexto de padre
        names = [f"{c.nombre} (Padre: {c.padre})" for c in candidates[:3]]
        raise ValueError(f"Ambigüedad: '{leaf_name}' existe {count} veces. Usa formato 'Padre -> Hijo'. Ejemplos: {', '.join(names)}...")

class OrdenTrabajoResource(ProgressResourceMixin, resources.ModelResource):
    rutina_codigo = fields.Field(
        column_name='rutina_codigo',
        attribute='rutina',
        widget=CachedForeignKeyWidget(Rutina, field='codigo_rutina')
    )
    ubicacion_nombre = fields.Field(
        column_name='ubicacion_nombre',
        attribute='ubicacion',
        widget=CachedHierarchicalWidget(Ubicacion, field='nombre')
    )
    tecnico_usuario = fields.Field(
        column_name='tecnico_usuario',
        attribute='tecnico',
        widget=CachedForeignKeyWidget(User, field='username')
    )
    activos_codigos = fields.Field(
        column_name='activos_codigos',
        attribute='activos',
        widget=CachedManyToManyCodeWidget(Activo, field='codigo_interno')
    )
    
    inicio_programado = fields.Field(
        column_name='inicio_programado',
        attribute='inicio_programado',
        widget=DateTimeWidget(format='%Y-%m-%d %H:%M:%S')
    )
    fin_programado = fields.Field(
        column_name='fin_programado',
        attribute='fin_programado',
        widget=DateTimeWidget(format='%Y-%m-%d %H:%M:%S')
    )

    # Cachés internas (se llenan en before_import)
    _rutina_cache = None       # codigo_rutina -> Rutina
    _ot_cache = None           # codigo_de_orden -> OrdenTrabajo

    def get_instance(self, instance_loader, row):
        """Coincidencia por codigo_de_orden usando caché pre-cargado"""
        codigo = row.get('codigo_de_orden')
        if codigo:
            codigo = str(codigo).strip()
            if self._ot_cache is not None:
                return self._ot_cache.get(codigo)
            return self.Meta.model.objects.filter(codigo_de_orden=codigo).first()
        return None

    def before_import(self, dataset, *args, **kwargs):
        """Normalizar cabeceras + PRE-CARGAR todos los lookups en memoria"""
        import sys
        if not dataset.headers:
            return

        import unicodedata
        import re

        def normalize(text):
            if not text: return ""
            text = unicodedata.normalize('NFD', str(text))
            text = "".join([c for c in text if unicodedata.category(c) != 'Mn'])
            text = text.lower().strip()
            text = re.sub(r'[\s-]+', '_', text)
            return text

        header_map = {
            'codigo': 'codigo_de_orden',
            'orden': 'codigo_de_orden',
            'ot': 'codigo_de_orden',
            'tipo_orden': 'tipo',
            'rutina': 'rutina_codigo',
            'codigo_rutina': 'rutina_codigo',
            'ubicacion': 'ubicacion_nombre',
            'area': 'ubicacion_nombre',
            'tecnico': 'tecnico_usuario',
            'usuario': 'tecnico_usuario',
            'activos': 'activos_codigos',
            'equipos': 'activos_codigos',
            'inicio': 'inicio_programado',
            'fecha_inicio': 'inicio_programado',
            'fin': 'fin_programado',
            'fecha_fin': 'fin_programado',
        }

        new_headers = []
        for h in dataset.headers:
            norm_h = normalize(h)
            mapped_h = header_map.get(norm_h, norm_h)
            new_headers.append(mapped_h)

        dataset.headers = new_headers
        print(f"[DEBUG] [Import OT] Headers normalizados: {dataset.headers}")

        # === PRE-CARGA MASIVA DE LOOKUPS ===
        total = len(dataset)
        print(f"[DEBUG] [Import OT] Pre-cargando cachés para {total} filas...")
        sys.stdout.flush()

        # 1. Caché de Rutinas (codigo_rutina -> Rutina con tiempo_estimado)
        self._rutina_cache = {}
        for r in Rutina.objects.only('id', 'codigo_rutina', 'tiempo_estimado'):
            self._rutina_cache[r.codigo_rutina] = r
        # Inyectar en el widget
        rutina_field = self.fields.get('rutina_codigo')
        if rutina_field and hasattr(rutina_field.widget, 'set_cache'):
            rutina_field.widget.set_cache(self._rutina_cache)
        print(f"[DEBUG] [Import OT]   Rutinas cacheadas: {len(self._rutina_cache)}")

        # 2. Caché de Usuarios (username -> User)
        user_cache = {u.username: u for u in User.objects.only('id', 'username')}
        tecnico_field = self.fields.get('tecnico_usuario')
        if tecnico_field and hasattr(tecnico_field.widget, 'set_cache'):
            tecnico_field.widget.set_cache(user_cache)
        print(f"[DEBUG] [Import OT]   Usuarios cacheados: {len(user_cache)}")

        # 3. Caché de Ubicaciones (jerárquica, con padre)
        from collections import defaultdict
        ubicaciones_by_name = defaultdict(list)
        parent_map = {}
        for ub in Ubicacion.objects.select_related('padre').only('id', 'nombre', 'padre__id', 'padre__nombre'):
            ubicaciones_by_name[ub.nombre.lower()].append(ub)
            parent_map[ub.id] = ub.padre.nombre if ub.padre else ''
        ubicacion_field = self.fields.get('ubicacion_nombre')
        if ubicacion_field and hasattr(ubicacion_field.widget, 'set_cache'):
            ubicacion_field.widget.set_cache(dict(ubicaciones_by_name), parent_map)
        print(f"[DEBUG] [Import OT]   Ubicaciones cacheadas: {sum(len(v) for v in ubicaciones_by_name.values())}")

        # 4. Caché de Activos (codigo_interno -> Activo AND nombre -> Activo)
        activo_cache = {}
        for a in Activo.objects.only('id', 'codigo_interno', 'nombre'):
            if a.codigo_interno:
                code_norm = normalize(a.codigo_interno)
                # El normalize de import ya reemplaza espacios por '_', mantendremos una key extra directa
                activo_cache[code_norm] = a
                # Guardar tambien lower y acentos quitados pero con espacios originales
                code_clean = unicodedata.normalize('NFD', str(a.codigo_interno))
                code_clean = "".join([c for c in code_clean if unicodedata.category(c) != 'Mn']).lower().strip()
                activo_cache[code_clean] = a
                
            if a.nombre:
                name_norm = normalize(a.nombre)
                activo_cache[name_norm] = a
                # Guardar copia clean con espacios
                name_clean = unicodedata.normalize('NFD', str(a.nombre))
                name_clean = "".join([c for c in name_clean if unicodedata.category(c) != 'Mn']).lower().strip()
                activo_cache[name_clean] = a
                
        activos_field = self.fields.get('activos_codigos')
        if activos_field and hasattr(activos_field.widget, 'set_cache'):
            activos_field.widget.set_cache(activo_cache)
        print(f"[DEBUG] [Import OT]   Activos cacheados (por código y nombre): {len(activo_cache)}")

        # 5. Caché de OTs existentes (codigo_de_orden -> OrdenTrabajo) para get_instance
        self._ot_cache = {}
        for ot in OrdenTrabajo.objects.only('id', 'codigo_de_orden'):
            if ot.codigo_de_orden:
                self._ot_cache[ot.codigo_de_orden] = ot
        print(f"[DEBUG] [Import OT]   OTs existentes cacheadas: {len(self._ot_cache)}")

        print(f"[DEBUG] [Import OT] Cachés listas. Iniciando importación de {total} filas...")
        sys.stdout.flush()

    class Meta:
        model = OrdenTrabajo
        # Mantenemos codigo_de_orden como identificador. Al quitar 'id' de 'fields', 
        # evitamos que el widget intente setearlo y active force_update erróneamente.
        import_id_fields = ('codigo_de_orden',)
        fields = ('codigo_de_orden', 'tipo', 'prioridad', 'rutina_codigo', 'ubicacion_nombre', 
                  'tecnico_usuario', 'activos_codigos', 'inicio_programado', 'fin_programado', 
                  'descripcion_corta', 'descripcion_detallada', 'estado', 'notas')
        export_order = ('id', 'codigo_de_orden', 'tipo', 'prioridad', 'rutina_codigo', 'ubicacion_nombre', 
                        'tecnico_usuario', 'activos_codigos', 'inicio_programado', 'fin_programado', 
                        'descripcion_corta', 'descripcion_detallada', 'estado', 'notas')

    def import_field(self, field, obj, row, is_m2m=False, **kwargs):
        """
        Sparse Update: No sobrescribir con valores vacíos para OTs.
        """
        column_name = field.column_name
        
        # El código base siempre debe evaluarse para matching
        if column_name in ['id', 'codigo_de_orden']:
            return super().import_field(field, obj, row, is_m2m, **kwargs)

        if column_name in row:
            value = row.get(column_name)
            if value is None or str(value).strip() == '':
                return # No hacer nada si viene vacío (Sparse Update)
        
        super().import_field(field, obj, row, is_m2m, **kwargs)

    def before_import_row(self, row, **kwargs):
        """Limpieza de datos y cálculo automático de campos faltantes (optimizado)"""
        # 1. Limpieza básica de strings y nulos
        for key in list(row.keys()):
            val = row.get(key)
            if val is not None:
                val_str = str(val).strip()
                if val_str in ['None', 'nan', 'NULL', '']:
                    row[key] = None
                elif isinstance(val, str):
                    row[key] = val_str

        # 1.5. Valores por defecto
        if not row.get('tipo'):
            row['tipo'] = 'PREVENTIVA'
        if not row.get('prioridad'):
            row['prioridad'] = 'MEDIA'
        if not row.get('estado'):
            row['estado'] = 'ESPERA'

        # 2. Cálculo automático de fin_programado (usando caché de rutinas)
        inicio_val = row.get('inicio_programado')
        fin_val = row.get('fin_programado')
        rutina_code = row.get('rutina_codigo')

        if inicio_val and not fin_val:
            try:
                from datetime import datetime, timedelta
                inicio_dt = None
                
                if isinstance(inicio_val, datetime):
                    inicio_dt = inicio_val
                elif isinstance(inicio_val, str):
                    for fmt in ['%Y-%m-%d %H:%M:%S', '%d/%m/%Y %H:%M:%S',
                                '%Y-%m-%d %H:%M', '%d/%m/%Y %H:%M',
                                '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S.%f']:
                        try:
                            inicio_dt = datetime.strptime(inicio_val.strip(), fmt)
                            break
                        except ValueError:
                            continue
                
                if inicio_dt:
                    duration = timedelta(hours=1)
                    # Usar caché en vez de query
                    if rutina_code and self._rutina_cache:
                        rutina = self._rutina_cache.get(str(rutina_code).strip())
                        if rutina and rutina.tiempo_estimado:
                            duration = rutina.tiempo_estimado
                    
                    row['fin_programado'] = inicio_dt + duration
                    
            except Exception as e:
                print(f"[DEBUG] [Import OT] Error calculando fin_programado: {str(e)}")

    def after_import(self, dataset, result, using_transactions, *args, **kwargs):
        """Generar códigos de orden faltantes usando bulk_update (solo si no es dry_run)"""
        
        # 1. DETECCIÓN ULTRA-DEFENSIVA DE DRY RUN
        is_dry_run = kwargs.get('dry_run')
        if is_dry_run is None:
            is_dry_run = getattr(result, 'dry_run', False)
        
        if is_dry_run:
            print("[DEBUG] [Import OT] Saltando bulk_update de códigos: Es fase de análisis (dry_run=True)")
            return

        from django.db import transaction
        new_instances = []
        for row in result.rows:
            if hasattr(row, 'instance') and row.instance:
                # Solo procesar si el objeto parece tener una PK válida
                if row.instance.pk is not None:
                    new_instances.append(row.instance)
        
        # 2. Filtrar solo los que NO tienen código
        ot_without_code = [ot for ot in new_instances if not ot.codigo_de_orden]
        
        if ot_without_code:
            print(f"[DEBUG] [Import OT] Generando códigos para {len(ot_without_code)} OTs guardadas...")
            for ot in ot_without_code:
                # Usar .pk garantizado
                ot.codigo_de_orden = f"OT-{str(ot.pk).zfill(9)}"
            
            try:
                # Importación directa del modelo para evitar fallos de referencia
                from .models import OrdenTrabajo
                with transaction.atomic():
                    OrdenTrabajo.objects.bulk_update(ot_without_code, ['codigo_de_orden'], batch_size=500)
                print(f"[DEBUG] [Import OT] bulk_update completado exitosamente.")
            except Exception as e:
                print(f"[DEBUG] [Import OT] Error en bulk_update de códigos: {str(e)}")

class PasoRutinaInline(admin.TabularInline):
    model = PasoRutina
    extra = 1
    fields = ('orden', 'descripcion', 'tipo_respuesta', 'unidad_medida', 'valor_objetivo', 'rango_min', 'rango_max', 'punto_medicion_exacto', 'punto_medicion_codigo')

class OrdenTrabajoInline(admin.TabularInline):
    model = OrdenTrabajo
    extra = 0
    raw_id_fields = ('rutina', 'aviso', 'tecnico', 'ubicacion')
    fields = ('tipo', 'prioridad', 'rutina', 'ubicacion', 'get_activos_list', 'tecnico', 'equipo', 'inicio_programado', 'estado')
    readonly_fields = ('tipo', 'prioridad', 'rutina', 'ubicacion', 'get_activos_list', 'inicio_programado')
    can_delete = True
    show_change_link = True
    
    def get_activos_list(self, obj):
        # Al usar prefetch_related('activos'), esto no genera queries N+1
        return ", ".join([a.nombre for a in obj.activos.all()])
    get_activos_list.short_description = "Activos"

    def get_queryset(self, request):
        # Optimizamos ubicación profundamente para evitar N+1 en la reconstrucción de la ruta completa
        return super().get_queryset(request).select_related('rutina', 'ubicacion__padre__padre', 'tecnico', 'equipo').prefetch_related('activos')

class ProgramacionInline(admin.TabularInline):
    model = Programacion
    extra = 0
    readonly_fields = ('creado_en', 'horario', 'fecha_inicio', 'fecha_fin', 'procesada', 'ver_detalle_link')
    fields = ('creado_en', 'horario', 'fecha_inicio', 'fecha_fin', 'procesada', 'ver_detalle_link')
    ordering = ('-creado_en',)
    can_delete = False
    show_change_link = True
    
    def ver_detalle_link(self, obj):
        if obj.id:
            url = reverse('admin:mantenimiento_programacion_change', args=[obj.id])
            return mark_safe(f'<a href="{url}">🔍 Ver Detalle</a>')
        return "-"
    ver_detalle_link.short_description = 'Acciones'

@admin.register(Rutina)
class RutinaAdmin(ImportExportModelAdmin):
    change_list_template = 'admin/mantenimiento/rutina/change_list.html'
    list_per_page = 50
    resource_class = RutinaResource
    list_display = ('codigo_rutina', 'nombre', 'tipo', 'frecuencia', 'puesto_trabajo', 'tiempo_estimado', 'es_invasiva', 'cantidad_tecnicos', 'ver_dashboard_link', 'programar_rutina_link')
    list_filter = (('tipo', admin.RelatedOnlyFieldListFilter), 'frecuencia', 'puesto_trabajo', 'es_invasiva')
    search_fields = ('codigo_rutina', 'nombre', 'herramientas')
    autocomplete_fields = ('tipo', 'frecuencia', 'puesto_trabajo')
    readonly_fields = ('creado_en', 'actualizado_en', 'programar_rutina_link', 'ver_dashboard_link')
    list_select_related = True
    inlines = [PasoRutinaInline, ProgramacionInline] # Agregado historial de programaciones
    actions = ['exportar_seleccionadas_action']

    def programar_rutina_link(self, obj):
        if not obj.id: return "-"
        url = reverse('mantenimiento:programar_rutina_wizard') + f'?rutina={obj.id}'
        return mark_safe(f'<a class="button" href="{url}" style="background: #10b981; color: white; font-weight: 700; padding: 5px 15px; border-radius: 4px; text-decoration: none;">🗓️ PROGRAMAR ESTA RUTINA</a>')
    programar_rutina_link.short_description = 'Programación'

    def ver_dashboard_link(self, obj):
        url = reverse('mantenimiento:rutinas_dashboard')
        return mark_safe(f'<a class="button" href="{url}" style="background: #3b82f6; color: white; font-weight: 700; padding: 5px 10px; border-radius: 4px; text-decoration: none;">📊 DASHBOARD</a>')
    ver_dashboard_link.short_description = 'Dashboard'

    def get_queryset(self, request):
        # Optimización profunda para evitar N+1 en la renderización de la ruta de tipos (soporta hasta 6 niveles)
        return super().get_queryset(request).select_related(
            'tipo__padre__padre__padre__padre__padre', 
            'frecuencia', 
            'puesto_trabajo'
        )
    
    fieldsets = (
        ('Identificación', {
            'fields': ('codigo_rutina', ('nombre', 'programar_rutina_link'), 'tipo', 'frecuencia', 'puesto_trabajo')
        }),
        ('Manual de Pasos', {
            'fields': ('herramientas',)
        }),
        ('Detalles de Ejecución', {
            'fields': ('es_invasiva', 'tiempo_estimado', 'cantidad_tecnicos', 'descripcion')
        }),
    )

    def get_urls(self):
        urls = super().get_urls()
        from .views import import_rutinas
        custom_urls = [
            path('import-background/', self.admin_site.admin_view(import_rutinas.import_rutinas_background), name='mantenimiento_rutina_import_background'),
            path('import-background/process/', csrf_exempt(self.admin_site.admin_view(import_rutinas.import_rutinas_process)), name='mantenimiento_rutina_import_process'),
            path('import-background/progress/', self.admin_site.admin_view(import_rutinas.import_rutinas_progress), name='mantenimiento_rutina_import_progress'),
            path('import-background/template/', self.admin_site.admin_view(self.download_template_view), name='mantenimiento_rutina_import_template'),
        ]
        return custom_urls + urls

    def download_template_view(self, request):
        """Genera un archivo Excel vacío con las cabeceras del recurso de Rutinas"""
        dataset = RutinaResource().export(queryset=Rutina.objects.none())
        response = HttpResponse(dataset.xlsx, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="formato_importacion_rutinas.xlsx"'
        return response

    
    @admin.action(description="📥 Exportar seleccionadas a Excel")
    def exportar_seleccionadas_action(self, request, queryset):
        """
        Exporta solo las rutinas seleccionadas a un archivo Excel
        utilizando el RutinaResource configurado.
        """
        resource = self.resource_class()
        dataset = resource.export(queryset)
        
        response = HttpResponse(
            dataset.xlsx,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="rutinas_seleccionadas.xlsx"'
        
        self.message_user(
            request,
            f"Se han exportado {queryset.count()} rutinas seleccionadas.",
            messages.SUCCESS
        )
        
        return response


class DiaHorarioInline(admin.TabularInline):
    model = DiaHorario
    extra = 7
    max_num = 7

from django.utils.html import format_html
from django.urls import reverse

@admin.register(Horario)
class HorarioAdmin(admin.ModelAdmin):
    list_per_page = 50
    list_display = ('nombre', 'descripcion', 'color', 'total_horas_semanales', 'ver_calendario_link')
    search_fields = ('nombre',)
    inlines = [DiaHorarioInline]

    def ver_calendario_link(self, obj):
        url = reverse('mantenimiento:calendario')
        return format_html('<a class="button" href="{}" target="_blank">Ver Programación Anual</a>', url)
    ver_calendario_link.short_description = 'Calendario'


@admin.register(RestriccionCalendario)
class RestriccionCalendarioAdmin(admin.ModelAdmin):
    list_per_page = 50
    list_display = ('fecha', 'motivo')
    ordering = ('fecha',)
    search_fields = ('motivo',)


@admin.register(PlanificacionMensual)
class PlanificacionMensualAdmin(admin.ModelAdmin):
    list_per_page = 50
    list_display = ('nombre', 'mes', 'anio', 'estado', 'responsable', 'get_total_ordenes', 'get_total_horas')
    list_filter = ('estado', 'mes', 'anio')
    list_select_related = ('responsable',)
    search_fields = ('nombre', 'notas')
    inlines = [OrdenTrabajoInline]
    actions = ['poblar_plan_action']
    
    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            ordenes_count=Count('ordenes')
        ).prefetch_related('ordenes__rutina')

    def get_total_ordenes(self, obj):
        return getattr(obj, 'ordenes_count', obj.ordenes.count())
    get_total_ordenes.short_description = "N° OTs"
    get_total_ordenes.admin_order_field = 'ordenes_count'

    def get_total_horas(self, obj):
        # Al estar pre-cargado con prefetch_related('ordenes__rutina'), no hará nuevas queries
        total = 0
        for ot in obj.ordenes.all():
            if ot.rutina and ot.rutina.tiempo_estimado:
                total += ot.rutina.tiempo_estimado.total_seconds() / 3600
        return f"{total:.1f} hrs"
    get_total_horas.short_description = "Total HH"

    @admin.action(description="Poblar plan con OTs del mes/año")
    def poblar_plan_action(self, request, queryset):
        for plan in queryset:
            # Buscar OTs que no tengan plan y caigan en el mes/año
            ots = OrdenTrabajo.objects.filter(
                inicio_programado__month=plan.mes,
                inicio_programado__year=plan.anio,
                planificacion__isnull=True
            )
            count = ots.count()
            ots.update(planificacion=plan)
            self.message_user(request, f"Se han agregado {count} órdenes al plan {plan.nombre}.")

@admin.register(Programacion)
class ProgramacionAdmin(admin.ModelAdmin):
    list_per_page = 50
    list_display = ('id', 'rutina', 'get_areas', 'horario', 'procesada', 'ver_cronograma_visual_link')
    list_filter = ('rutina__frecuencia', 'procesada')
    list_select_related = ('rutina', 'horario')
    search_fields = ('id', 'rutina__nombre')
    fields = ('rutina', 'horario', 'areas', 'activos', 'fecha_inicio', 'fecha_fin', 'procesada')
    autocomplete_fields = ('rutina', 'horario', 'areas', 'activos')
    actions = ['generar_ordenes_action', 'reset_procesada_action', 'eliminar_ordenes_action']
    inlines = [OrdenTrabajoInline]

    def ver_calendario_link(self, obj):
        url = reverse('mantenimiento:calendario')
        return format_html('<a class="button" href="{}" target="_blank">Ver Programación Anual</a>', url)
    ver_calendario_link.short_description = 'Calendario'
    
    def ver_cronograma_visual_link(self, obj):
        url = reverse('mantenimiento:cronograma')
        return format_html('<a class="button" href="{}?programacion_id={}" target="_blank" style="background:#3b82f6; color:white;">Ver Cronograma</a>', url, obj.id)
    ver_cronograma_visual_link.short_description = 'Cronograma Visual'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('rutina', 'horario').prefetch_related('areas')

    def get_areas(self, obj):
        # Al usar prefetch_related('areas'), esto no genera queries N+1
        return ", ".join([a.nombre for a in obj.areas.all()])
    get_areas.short_description = 'Áreas'

    @admin.action(description="Generar Órdenes de Trabajo")
    def generar_ordenes_action(self, request, queryset):
        import threading
        from .models import NotificacionMantenimiento
        from django.db import connection

        user_id = request.user.id

        def worker(programacion_id, user_id):
            # En un hilo nuevo, debemos asegurarnos de cerrar la conexión al final
            from django.db import connections
            from .models import Programacion, NotificacionMantenimiento
            try:
                p = Programacion.objects.get(id=programacion_id)
                count = p.generar_ordenes()
                NotificacionMantenimiento.objects.create(
                    user_id=user_id,
                    mensaje=f"Generación completada: Se crearon {count} órdenes para {p.rutina.nombre}.",
                    tipo='SUCCESS'
                )
            except Exception as e:
                NotificacionMantenimiento.objects.create(
                    user_id=user_id,
                    mensaje=f"Error al generar órdenes para {p.rutina.nombre if 'p' in locals() else 'ID '+str(programacion_id)}: {str(e)}",
                    tipo='ERROR'
                )
            finally:
                # Cerrar conexiones en hilos secundarios para evitar fugas
                for conn in connections.all():
                    conn.close()

        for programacion in queryset:
            if programacion.procesada:
                self.message_user(
                    request,
                    f"La programación {programacion.rutina.nombre} ya fue procesada anteriormente.",
                    messages.WARNING
                )
                continue
            
            if programacion.fecha_inicio.year < 2000:
                self.message_user(
                    request,
                    f"La programación {programacion.id} tiene una fecha de inicio inválida ({programacion.fecha_inicio}). Por favor corrígala.",
                    messages.ERROR
                )
                continue
            
            # Lanzar hilo
            t = threading.Thread(target=worker, args=(programacion.id, user_id))
            t.setDaemon(True)
            t.start()

        self.message_user(
            request, 
            "Iniciando generación en segundo plano para las programaciones seleccionadas. Se te notificará al finalizar.",
            messages.INFO
        )

    @admin.action(description="Resetear estado (Permitir re-generar)")
    def reset_procesada_action(self, request, queryset):
        rows_updated = queryset.update(procesada=False)
        self.message_user(request, f"{rows_updated} programaciones han sido reseteadas.", messages.SUCCESS)

    @admin.action(description="ELIMINAR órdenes generadas")
    def eliminar_ordenes_action(self, request, queryset):
        for programacion in queryset:
            count = programacion.ordenes.count()
            programacion.ordenes.all().delete()
            programacion.procesada = False
            programacion.save()
            self.message_user(
                request, 
                f"Se han eliminado {count} órdenes de {programacion.rutina.nombre} y se ha reseteado su estado.",
                messages.SUCCESS
            )



class FallaInline(admin.TabularInline):
    model = Falla
    extra = 1
    fk_name = 'padre'
    fields = ('nombre', 'descripcion')
    verbose_name = "Sub-falla / Síntoma"
    verbose_name_plural = "Sub-fallas (Hijos)"

@admin.register(Falla)
class FallaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'padre', 'puesto_trabajo', 'get_ruta_completa')
    list_filter = ('padre', 'puesto_trabajo')
    search_fields = ('nombre',)
    raw_id_fields = ('padre', 'puesto_trabajo')
    inlines = [FallaInline]

    def get_ruta_completa(self, obj):
        return obj.get_ruta_completa()
    get_ruta_completa.short_description = 'Ruta Completa'

class FotoAvisoInline(admin.TabularInline):
    model = FotoAviso
    extra = 1


class AvisoResource(resources.ModelResource):
    activo = fields.Field(column_name='activo', attribute='activo', widget=ForeignKeyWidget(Activo, field='codigo_interno'))
    ubicacion = fields.Field(column_name='ubicacion', attribute='ubicacion', widget=ForeignKeyWidget(Ubicacion, field='nombre'))
    falla = fields.Field(column_name='falla', attribute='falla', widget=ForeignKeyWidget(Falla, field='nombre'))
    solicitante = fields.Field(column_name='solicitante', attribute='solicitante', widget=ForeignKeyWidget(User, field='username'))

    class Meta:
        model = Aviso
        fields = ('id', 'activo', 'ubicacion', 'falla', 'descripcion', 'prioridad', 'tipo', 'estado', 'solicitante', 'creado_en', 'actualizado_en')
        export_order = fields
        skip_unchanged = True
        report_skipped = True

@admin.register(Aviso)
class AvisoAdmin(ImportExportModelAdmin):
    resource_class = AvisoResource
    change_list_template = "admin/mantenimiento/procedimiento/change_list.html"
    list_per_page = 50
    list_display = ('id', 'tipo', 'prioridad', 'estado', 'falla', 'descripcion_corta', 'ubicacion', 'activo', 'solicitante', 'creado_en', 'enviar_whatsapp_button', 'import_link')
    list_filter = ('tipo', 'estado', 'prioridad', 'falla', 'creado_en')
    list_select_related = ('ubicacion', 'activo', 'solicitante', 'falla')
    search_fields = ('descripcion', 'ubicacion__nombre', 'activo__nombre')
    autocomplete_fields = ('activo', 'ubicacion', 'solicitante', 'falla')
    actions = ['generar_ot_action']
    raw_id_fields = ('activo', 'ubicacion', 'solicitante', 'falla')
    inlines = [FotoAvisoInline]

    def import_link(self, obj=None):
        url = reverse('admin:mantenimiento_aviso_import_background')
        return mark_safe(f'<a class="button" href="{url}" style="background: #2563eb; color: white; font-weight: 700;">📥 IMPORTAR MASIVO</a>')
    import_link.short_description = 'Acciones'

    # --- Funcionalidades Combinadas: Importación y WhatsApp ---

    def get_urls(self):
        urls = super().get_urls()
        from django.urls import path
        from .views.import_avisos import import_avisos_background, import_avisos_process, import_avisos_progress
        
        custom_urls = [
            # URLs de Importación
            path('import-background/', self.admin_site.admin_view(import_avisos_background), name='mantenimiento_aviso_import_background'),
            path('import-background/process/', csrf_exempt(self.admin_site.admin_view(import_avisos_process)), name='mantenimiento_aviso_import_process'),
            path('import-background/progress/', self.admin_site.admin_view(import_avisos_progress), name='mantenimiento_aviso_import_progress'),
            path('import-background/template/', self.admin_site.admin_view(self.download_template_view), name='mantenimiento_aviso_import_template'),
            
            # URL de WhatsApp
            path('enviar-whatsapp/<int:aviso_id>/', self.admin_site.admin_view(self.enviar_whatsapp_view), name='aviso_enviar_whatsapp'),
        ]
        return custom_urls + urls

    def download_template_view(self, request):
        dataset = AvisoResource().export(queryset=Aviso.objects.none())
        response = HttpResponse(dataset.xlsx, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="plantilla_importacion_avisos.xlsx"'
        return response

    def add_view(self, request, form_url='', extra_context=None):
        """Redirigir a la interfaz móvil renovada"""
        from django.shortcuts import redirect
        if request.GET.get('mode') != 'admin':
            return redirect('mantenimiento:mobile_crear_aviso')
        return super().add_view(request, form_url, extra_context)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "falla":
            puesto_tecnico = getattr(request.user, 'perfil_tecnico', None)
            if puesto_tecnico and not request.user.is_superuser:
                # Filtrar fallas que cuelgan de raíces del puesto
                roots = Falla.objects.filter(puesto_trabajo=puesto_tecnico.puesto)
                ids = []
                for r in roots:
                    def get_ids(n):
                        ids.append(n.id)
                        for h in n.hijos.all(): get_ids(h)
                    get_ids(r)
                kwargs["queryset"] = Falla.objects.filter(id__in=ids)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    @admin.display(description='Descripción')
    def descripcion_corta(self, obj):
        if not obj.descripcion: return "-"
        return obj.descripcion[:50] + "..." if len(obj.descripcion) > 50 else obj.descripcion

    @admin.action(description="Generar Orden de Trabajo Correctiva")
    def generar_ot_action(self, request, queryset):
        count = 0
        from datetime import timedelta
        # Aseguramos que messages esté disponible
        from django.contrib import messages
        
        for aviso in queryset:
            if OrdenTrabajo.objects.filter(aviso=aviso).exists():
                self.message_user(request, f"El aviso {aviso.id} ya tiene una OT asociada.", messages.WARNING)
                continue
                
            ot = OrdenTrabajo.objects.create(
                tipo='CORRECTIVA',
                prioridad=aviso.prioridad,
                aviso=aviso,
                falla=aviso.falla,
                ubicacion=aviso.ubicacion,
                inicio_programado=aviso.creado_en, 
                fin_programado=aviso.creado_en + timedelta(hours=2),
                notas=aviso.descripcion,
                estado='ESPERA'
            )
            if aviso.activo:
                ot.activos.add(aviso.activo)
            aviso.estado = 'PROCESO'
            aviso.save()
            count += 1
            
        if count:
            self.message_user(request, f"Se han generado {count} Órdenes de Trabajo Correctivas.", messages.SUCCESS)

    def enviar_whatsapp_button(self, obj):
        from django.urls import reverse
        from django.utils.safestring import mark_safe
        if not obj.id: return '-'
        # Usamos una URL personalizada dentro del admin
        url = reverse('admin:aviso_enviar_whatsapp', args=[obj.id])
        return mark_safe(f'<a class="button" href="{url}" style="background-color: #25D366; color: white; border-radius: 4px; padding: 5px 10px; font-weight: bold; text-decoration: none;">📱 Enviar WA</a>')
    enviar_whatsapp_button.short_description = 'WhatsApp'
    enviar_whatsapp_button.allow_tags = True

    def enviar_whatsapp_view(self, request, aviso_id):
        import requests
        from django.contrib import messages
        from django.http import HttpResponseRedirect
        from django.shortcuts import get_object_or_404
        
        aviso = get_object_or_404(Aviso, id=aviso_id)
            
        texto = f"*🚨 AVISO #{aviso.id} - Energy ERP*\n"
        texto += f"🗓️ *Fecha:* {aviso.creado_en.strftime('%d/%m/%Y %H:%M')}\n"
        texto += f"📍 *Ubicación:* {str(aviso.ubicacion)}\n"
        if aviso.activo:
            texto += f"⚙️ *Activo:* {str(aviso.activo)}\n"
        if aviso.falla:
            texto += f"🔧 *Falla:* {str(aviso.falla)}\n"
        
        emoji_p = "🔴" if aviso.prioridad == 'CRITICA' else ("🟠" if aviso.prioridad == 'ALTA' else "🟡")
        texto += f"{emoji_p} *Prioridad:* {aviso.get_prioridad_display()}\n"
        texto += f"📝 *Descripción:* {aviso.descripcion}\n"
        solicita = aviso.solicitante.username if aviso.solicitante else 'N/A'
        texto += f"👤 *Solicitante:* {solicita}\n"
        texto += f"📊 *Estado:* {aviso.get_estado_display()}"
        
        try:
            # Enviamos al servicio local de Node
            resp = requests.post('http://localhost:3005/send-message', json={
                'number': '50488113195',
                'message': texto
            }, timeout=5)
            
            if resp.status_code == 200:
                self.message_user(request, f"✅ Mensaje enviado correctamente al +50488113195 para Aviso #{aviso.id}")
            else:
                self.message_user(request, f"❌ Error del servicio WA: {resp.text}", level=messages.ERROR)
        except Exception as e:
            self.message_user(request, f"❌ Error conectando con servicio WA (¿está corriendo node index.js?): {str(e)}", level=messages.ERROR)
            
        return HttpResponseRedirect(request.META.get('HTTP_REFERER', '../'))

class CierreOrdenTrabajoInline(admin.StackedInline):
    model = CierreOrdenTrabajo
    extra = 0
    can_delete = False
    verbose_name = "Cierre Técnico de la Orden"
    verbose_name_plural = "Información de Cierre Técnico"
    # Campos organizados de forma premium
    fieldsets = (
        (None, {
            'fields': (('tecnico', 'horas_hombre'), ('fecha_inicio_real', 'fecha_fin_real'), 'comentarios', 'materiales_utilizados')
        }),
    )
    autocomplete_fields = ['tecnico']

class MovimientoInventarioInline(admin.TabularInline):
    model = MovimientoInventario
    extra = 1
    fields = ('material', 'tipo', 'cantidad', 'ubicacion_origen', 'comentarios')
    autocomplete_fields = ['material']
    
    def get_queryset(self, request):
        return super().get_queryset(request).filter(tipo='SALIDA')

class PermisosTrabajoInline(admin.TabularInline):
    from seguridad.models import PermisoTrabajo
    model = PermisoTrabajo
    extra = 0
    can_delete = False
    fields = ('tipo', 'estado', 'solicitante', 'fecha_inicio', 'ver_permiso_link')
    readonly_fields = ('tipo', 'estado', 'solicitante', 'fecha_inicio', 'ver_permiso_link')
    verbose_name = "Permiso de Trabajo Vinculado"
    verbose_name_plural = "Permisos de Trabajo"
    
    def ver_permiso_link(self, obj):
        if obj.id:
            from django.urls import reverse
            from django.utils.html import format_html
            url = reverse('seguridad:detalle_permiso', args=[obj.id])
            return format_html('<a href="{}" class="button" style="background-color: #8b5cf6; color: white; padding: 3px 8px; border-radius: 4px;" target="_blank">Ver Permiso</a>', url)
        return "-"
    ver_permiso_link.short_description = "Acciones"


class ValorPasoOrdenInline(admin.TabularInline):
    model = ValorPasoOrden
    extra = 0
    raw_id_fields = ('paso', 'capturado_por')
    fields = ('paso', 'valor_texto', 'valor_numerico', 'valor_bool', 'no_aplica', 'comentarios')
    readonly_fields = ('paso', 'capturado_por', 'creado_en')


@admin.register(OrdenTrabajo)
class OrdenTrabajoAdmin(admin.ModelAdmin):
    list_per_page = 50
    list_display = ('codigo_de_orden', 'tipo', 'prioridad', 'descripcion_corta', 'get_ubicacion_jerarquia', 'get_activos_format', 'inicio_programado', 'estado', 'registrar_salida_link')
    list_filter = ('tipo', 'prioridad', 'estado', 'inicio_programado', 'tecnico', 'equipo')
    readonly_fields = ('registrar_salida_link',)
    list_select_related = ('rutina', 'aviso', 'tecnico', 'equipo', 'ubicacion', 'programacion')
    search_fields = ('id', 'codigo_de_orden', 'descripcion_corta', 'descripcion_detallada', 'rutina__nombre', 'aviso__descripcion', 'ubicacion__nombre', 'activos__nombre', 'notas')
    autocomplete_fields = ('rutina', 'aviso', 'tecnico', 'equipo', 'ubicacion', 'programacion', 'activos')
    ordering = ('-inicio_programado',)
    date_hierarchy = 'inicio_programado'
    actions = ['generar_permiso_action', 'exportar_seleccionadas_action']

    @admin.action(description="📥 Exportar seleccionadas (Formato Importación)")
    def exportar_seleccionadas_action(self, request, queryset):
        """
        Exporta las OTs seleccionadas en el formato exacto requerido para la importación.
        """
        resource = OrdenTrabajoResource()
        dataset = resource.export(queryset)
        
        response = HttpResponse(
            dataset.xlsx,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="ordenes_trabajo_seleccionadas.xlsx"'
        
        return response


    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'rutina', 'aviso', 'tecnico', 'equipo', 'ubicacion', 'programacion'
        ).prefetch_related('activos')

    def get_activos_format(self, obj):
        # Usamos .all() que ya está prefetched en el queryset del admin
        activos_list = list(obj.activos.all())
        count = len(activos_list)
        if count == 0: return "-"
        if count == 1: return activos_list[0].nombre
        return f"{count} activos"
    get_activos_format.short_description = 'Activos'

    def get_ubicacion_jerarquia(self, obj):
        if obj.ubicacion:
            return obj.ubicacion.get_ruta_completa()
        return "-"
    get_ubicacion_jerarquia.short_description = 'Ubicación'
    get_ubicacion_jerarquia.admin_order_field = 'ubicacion__nombre'

    def get_descripcion(self, obj):
        if obj.rutina:
            return obj.rutina.nombre
        if obj.aviso:
            return f"CORR: {obj.aviso.descripcion[:30]}"
        return "OT Sin descripción"
    get_descripcion.short_description = 'Descripción/Rutina'

    def registrar_salida_link(self, obj):
        if obj.estado in ['PROGRAMADA', 'EJECUCION']:
            try:
                url = reverse('inventarios:registrar_salida')
                return mark_safe(f'<a class="button" href="{url}?ot={obj.id}" style="background: #6366f1; color: white; padding: 2px 8px; border-radius: 4px; font-weight: 600; text-decoration: none; font-size: 0.9em;">📦 Salida</a>')
            except Exception:
                # Fallback en caso de error de reversión (ej. migraciones o urls no cargadas)
                return "-"
        return "-"
    registrar_salida_link.short_description = "Acc."

    def generar_permiso_action(self, obj):
        from django.urls import reverse
        from django.utils.html import format_html
        if obj.permisos.exists():
            permiso = obj.permisos.first()
            url = reverse('seguridad:detalle_permiso', args=[permiso.id])
            return format_html('<a href="{}" class="button" style="background-color: #059669; color: white; padding: 3px 8px; border-radius: 4px;">Ver Permiso</a>', url)
        
        url = reverse('seguridad:generar_permiso_ot', args=[obj.id])
        return format_html('<a href="{}" class="button" style="background-color: #2563eb; color: white; padding: 3px 8px; border-radius: 4px;">Generar Permiso</a>', url)
    
    generar_permiso_action.short_description = "Permiso de Trabajo"
    generar_permiso_action.allow_tags = True

    def get_urls(self):
        urls = super().get_urls()
        from .views import import_ordenes
        custom_urls = [
            path('import-background/', self.admin_site.admin_view(import_ordenes.import_ordenes_background), name='mantenimiento_ordentrabajo_import_background'),
            path('import-background/process/', csrf_exempt(self.admin_site.admin_view(import_ordenes.import_ordenes_process)), name='mantenimiento_ordentrabajo_import_process'),
            path('import-background/progress/', self.admin_site.admin_view(import_ordenes.import_ordenes_progress), name='mantenimiento_ordentrabajo_import_progress'),
            path('import-background/template/', self.admin_site.admin_view(self.download_template_view), name='mantenimiento_ordentrabajo_import_template'),
        ]
        return custom_urls + urls

    def download_template_view(self, request):
        """Genera un archivo Excel vacío con las cabeceras del recurso"""
        dataset = OrdenTrabajoResource().export(queryset=OrdenTrabajo.objects.none())
        response = HttpResponse(dataset.xlsx, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="formato_importacion_ots.xlsx"'
        return response




