from django.contrib import admin
from .models import (
    TipoIncidente, Incidente,
    TipoInspeccion, ItemInspeccion, Inspeccion, ResultadoInspeccion,
    AsignacionEPP,
    AnalisisRiesgo, PasoTrabajo, Riesgo, Control,
    TipoPermiso, RequisitoPermiso, PermisoTrabajo, VerificacionRequisito,
    ObjetoCatalogo, LevantamientoConfiscacion, ObjetoConfiscado, FotoObjetoConfiscado,
    PeligroCatalogo, MedidaControlCatalogo
)

class ItemInspeccionInline(admin.TabularInline):
    model = ItemInspeccion
    extra = 1

@admin.register(TipoInspeccion)
class TipoInspeccionAdmin(admin.ModelAdmin):
    inlines = [ItemInspeccionInline]
    list_display = ('nombre', 'descripcion')

class ResultadoInspeccionInline(admin.TabularInline):
    model = ResultadoInspeccion
    extra = 0
    can_delete = False

@admin.register(Inspeccion)
class InspeccionAdmin(admin.ModelAdmin):
    inlines = [ResultadoInspeccionInline]
    list_display = ('tipo', 'fecha', 'inspector', 'resultado_global', 'activo', 'ubicacion')
    list_filter = ('tipo', 'resultado_global', 'fecha')
    search_fields = ('inspector__username', 'activo__codigo', 'ubicacion__nombre')

@admin.register(TipoIncidente)
class TipoIncidenteAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'descripcion')

@admin.register(Incidente)
class IncidenteAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'tipo', 'fecha_ocurrencia', 'severidad', 'estado', 'reportado_por')
    list_filter = ('severidad', 'estado', 'tipo', 'fecha_ocurrencia')
    search_fields = ('titulo', 'descripcion')

@admin.register(AsignacionEPP)
class AsignacionEPPAdmin(admin.ModelAdmin):
    list_display = ('miembro', 'material', 'cantidad', 'fecha_entrega', 'fecha_proxima_entrega')
    list_filter = ('fecha_entrega', 'miembro', 'material')
    search_fields = ('miembro__first_name', 'miembro__last_name', 'material__nombre')
    autocomplete_fields = ['miembro', 'material']

class PasoTrabajoInline(admin.TabularInline):
    model = PasoTrabajo
    extra = 1

@admin.register(AnalisisRiesgo)
class AnalisisRiesgoAdmin(admin.ModelAdmin):
    inlines = [PasoTrabajoInline]
    list_display = ('descripcion_trabajo', 'fecha', 'ubicacion', 'lider', 'firmado')
    filter_horizontal = ('ejecutantes',)
    autocomplete_fields = ['ubicacion', 'lider', 'orden_trabajo']
    list_select_related = ('ubicacion', 'lider', 'orden_trabajo')
    search_fields = ('descripcion_trabajo', 'lider__username', 'lider__first_name', 'ubicacion__nombre')

# Nota: Riesgo y Control se registran por separado por ahora debido a la anidación
@admin.register(PasoTrabajo)
class PasoTrabajoAdmin(admin.ModelAdmin):
    list_display = ('analisis', 'orden', 'descripcion')
    list_filter = ('analisis',)

@admin.register(Riesgo)
class RiesgoAdmin(admin.ModelAdmin):
    list_display = ('paso', 'descripcion')

@admin.register(Control)
class ControlAdmin(admin.ModelAdmin):
    list_display = ('riesgo', 'descripcion')

class RequisitoPermisoInline(admin.TabularInline):
    model = RequisitoPermiso
    extra = 1
    fields = ('orden', 'texto', 'tipo_respuesta', 'es_critico', 'verificacion', 'unidad_medida', 'valor_objetivo', 'rango_min', 'rango_max')
    ordering = ['orden']

@admin.register(TipoPermiso)
class TipoPermisoAdmin(admin.ModelAdmin):
    inlines = [RequisitoPermisoInline]
    list_display = ('nombre', 'descripcion', 'count_requisitos')
    search_fields = ('nombre', 'descripcion')
    
    def count_requisitos(self, obj):
        return obj.requisitos.count()
    count_requisitos.short_description = 'Requisitos'

class VerificacionRequisitoInline(admin.TabularInline):
    model = VerificacionRequisito
    extra = 0
    can_delete = False

@admin.register(PermisoTrabajo)
class PermisoTrabajoAdmin(admin.ModelAdmin):
    inlines = [VerificacionRequisitoInline]
    list_display = ('tipo', 'estado', 'fecha_inicio', 'fecha_fin', 'solicitante', 'ubicacion')
    list_filter = ('estado', 'tipo', 'fecha_inicio')
    search_fields = ('descripcion_trabajo', 'solicitante__username')

# --- Confiscaciones Admin ---

@admin.register(ObjetoCatalogo)
class ObjetoCatalogoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'descripcion')
    search_fields = ('nombre',)

class FotoObjetoConfiscadoInline(admin.TabularInline):
    model = FotoObjetoConfiscado
    extra = 1

@admin.register(ObjetoConfiscado)
class ObjetoConfiscadoAdmin(admin.ModelAdmin):
    inlines = [FotoObjetoConfiscadoInline]
    list_display = ('catalogo_objeto', 'codigo_barras', 'levantamiento', 'status', 'fecha_confiscacion')
    list_filter = ('status', 'fecha_confiscacion', 'catalogo_objeto')
    search_fields = ('codigo_barras', 'descripcion', 'levantamiento__folio')
    autocomplete_fields = ['catalogo_objeto', 'levantamiento']

class ObjetoConfiscadoInline(admin.StackedInline):
    model = ObjetoConfiscado
    extra = 0
    show_change_link = True
    fields = ('catalogo_objeto', 'codigo_barras', 'status')

@admin.register(LevantamientoConfiscacion)
class LevantamientoConfiscacionAdmin(admin.ModelAdmin):
    inlines = [ObjetoConfiscadoInline]
    list_display = ('folio', 'fecha', 'ubicacion', 'inspector', 'count_objetos')
    list_filter = ('fecha', 'ubicacion', 'inspector')
    search_fields = ('folio', 'comentarios', 'ubicacion__nombre')
    date_hierarchy = 'fecha'
    
    def count_objetos(self, obj):
        return obj.objetos.count()
    count_objetos.short_description = 'Objetos'

class MedidaControlInline(admin.TabularInline):
    model = MedidaControlCatalogo.peligros_asociados.through
    extra = 1
    verbose_name = "Control Recomendado"
    verbose_name_plural = "Controles Recomendados"

@admin.register(PeligroCatalogo)
class PeligroCatalogoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'categoria')
    list_filter = ('categoria',)
    search_fields = ('nombre',)
    inlines = [MedidaControlInline]

@admin.register(MedidaControlCatalogo)
class MedidaControlCatalogoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'tipo')
    list_filter = ('tipo',)
    search_fields = ('nombre',)
    filter_horizontal = ('peligros_asociados',)
