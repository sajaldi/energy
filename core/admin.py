from django.contrib import admin
from django.utils.safestring import mark_safe
from import_export import resources, fields, widgets
from import_export.widgets import ForeignKeyWidget
from import_export.admin import ImportExportModelAdmin
from django.urls import path, reverse
from django.utils.html import format_html
from django.db import connection
import pandas as pd
import io
import base64
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from django.db import transaction

from .models import (
    Consumo, InterfaceConsumo, Medidor, PuntoMedicion, Equipo,
    CaracteristicaMedicion, CategoriaPuntoMedicion, DocumentoMedicion, RangoMedicion, TipoMedidor, UnidadMedida, VistaConsumoDiferencia,
    Servicio, KPI, PerfilUsuario
)

@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'visto_tutorial')
    list_filter = ('visto_tutorial',)
    search_fields = ('usuario__username', 'usuario__email')


from . import views

# ==============================================================================
# FUNCIÓN AUXILIAR PARA GENERAR EL GRÁFICO (la ponemos al principio)
# ==============================================================================
def generar_grafico_ultimos_6_meses(medidor):
    hoy = datetime.now()
    fecha_inicio = hoy - timedelta(days=180)
    tipo_normalizado = (medidor.tipo or "").strip().upper()

    query_mensual = ""
    if tipo_normalizado == 'PUNTUAL':
        query_mensual = f"""
            SELECT TO_CHAR(fecha, 'YYYY-MM') AS mes, SUM(consumo) AS consumo_mensual
            FROM core_consumo WHERE medidor_id = {medidor.id} AND fecha >= '{fecha_inicio.strftime('%Y-%m-%d')}'
            GROUP BY TO_CHAR(fecha, 'YYYY-MM') ORDER BY mes DESC LIMIT 6;
        """
    else:
        query_mensual = f"""
            SELECT mes, (consumo_actual - consumo_anterior) AS consumo_mensual FROM (
                SELECT TO_CHAR(fecha_final_mes, 'YYYY-MM') AS mes, consumo_final_mes AS consumo_actual,
                       LAG(consumo_final_mes) OVER (PARTITION BY medidor_id ORDER BY fecha_final_mes) AS consumo_anterior
                FROM (
                    SELECT medidor_id, MAX(fecha) AS fecha_final_mes,
                           (SELECT consumo FROM core_consumo WHERE medidor_id = c.medidor_id AND fecha = MAX(c.fecha)) AS consumo_final_mes
                    FROM core_consumo c WHERE medidor_id = {medidor.id} AND fecha >= '{fecha_inicio.strftime('%Y-%m-%d')}'
                    GROUP BY medidor_id, TO_CHAR(fecha, 'YYYY-MM')
                ) AS lecturas
            ) AS calculo WHERE consumo_anterior IS NOT NULL ORDER BY mes DESC LIMIT 6;
        """
    try:
        df = pd.read_sql(query_mensual, connection)
        if df.empty: return None

        df = df.sort_values('mes').reset_index(drop=True)
        fig, ax = plt.subplots(figsize=(10, 4))
        bars = ax.bar(df['mes'], df['consumo_mensual'])
        unidad_simbolo = medidor.unidad.simbolo if medidor.unidad and medidor.unidad.simbolo else 'unidades'
        ax.set_ylabel(f'Consumo ({unidad_simbolo})')
        ax.set_title('Consumo de los Últimos 6 Meses')
        ax.bar_label(bars, fmt=lambda x: f'{x:,.0f}'.replace(',', '.'), padding=3)
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        img_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        plt.close(fig)
        return img_base64
    except Exception as e:
        print(f"Error generando gráfico para medidor {medidor.id}: {e}")
        return None

# ==============================================================================
# CLASES DE RECURSOS PARA IMPORT/EXPORT (sin cambios)
# ==============================================================================
class ConsumoResource(resources.ModelResource):
    # ... (tu código de ConsumoResource sin cambios) ...
    pass

class FixedImportExportAdmin(ImportExportModelAdmin):
    # ... (tu código de FixedImportExportAdmin sin cambios) ...
    pass

# ==============================================================================
# CLASES DE ADMINISTRACIÓN
# ==============================================================================

@admin.register(Consumo)
class ConsumoAdmin(FixedImportExportAdmin):
    resource_class = ConsumoResource # Vinculamos el resource
    # Mantenemos el resto de tu configuración
    list_display = ['id','fecha', 'consumo', 'medidor']
    list_filter = ['fecha', 'medidor']
    raw_id_fields = ['medidor']
    date_hierarchy = 'fecha'
    list_per_page = 10
    search_fields = ['id','medidor__nombre', 'consumo']
    
    # El resto de tus métodos para ConsumoAdmin (get_urls, changelist_view, etc.)
    # ... (van aquí si los tenías, si no, puedes omitirlos)

@admin.register(TipoMedidor)
class TipoMedidorAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'descripcion']
    search_fields = ['nombre']
    list_filter = ['nombre']
    ordering = ['nombre']
    list_per_page = 10
    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('medidores')

class MedidorInline(admin.TabularInline):
    model = Medidor
    fk_name = 'medidor_padre'
    extra = 0
    fields = ['nombre', 'tipo', 'tipo_medidor']
    readonly_fields = ['nombre', 'tipo', 'tipo_medidor']
    show_change_link = True
    ordering = ['nombre']
    

class ConsumoInline(admin.TabularInline):
    model = Consumo
    extra = 0
    fields = ['fecha', 'consumo']
    readonly_fields = ['fecha', 'consumo']
    show_change_link = True
    # Dejamos el ordering aquí para que el admin lo conozca
    ordering = ['-fecha'] 
    
    # --- SOLUCIÓN DEFINITIVA A PRUEBA DE FILTROS ---
    def get_queryset(self, request, obj=None):
        # 1. Obtenemos el queryset base, que ya está filtrado por el medidor padre.
        qs = super().get_queryset(request)

        # 2. Si no estamos en la página de un objeto existente, no mostramos nada.
        if not obj:
            return qs.none()

        # 3. Obtenemos los IDs de los 10 registros más recientes que queremos mostrar.
        #    'values_list' es muy eficiente, solo trae los IDs de la base de datos.
        #    'flat=True' nos da una lista simple de IDs: [101, 95, 88, ...]
        latest_consumo_ids = qs.order_by('-fecha')[:10].values_list('id', flat=True)

        # 4. Filtramos el queryset original por esta lista de IDs.
        #    Esto devuelve un QuerySet PEREZOSO (no evaluado) y filtrable, 
        #    sobre el que el admin puede añadir más filtros si lo necesita
        #    sin causar el error de "slice".
        return qs.filter(pk__in=list(latest_consumo_ids))

    def has_add_permission(self, request, obj=None):
        return False
    
    
@admin.register(Medidor)
class MedidorAdmin(admin.ModelAdmin):
    list_display = ['id','nombre', 'tipo', 'tipo_medidor', 'medidor_padre','unidad']
    search_fields = ['nombre']
    list_filter = ['tipo', 'tipo_medidor']
    ordering = ['nombre']
    list_per_page = 10
    inlines = [MedidorInline, ConsumoInline] # Agregamos ambos inlines

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('tipo_medidor', 'medidor_padre', 'unidad')

    # --- MÉTODO SOBRESCRITO PARA AÑADIR EL GRÁFICO ---
    def change_view(self, request, object_id, form_url='', extra_context=None):
        medidor = self.get_object(request, object_id)
        extra_context = extra_context or {}
        if medidor:
            extra_context['grafico_consumo'] = generar_grafico_ultimos_6_meses(medidor)
        return super().change_view(
            request, object_id, form_url, extra_context=extra_context,
        )


@admin.register(UnidadMedida)
class UnidadMedidaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'simbolo', 'descripcion']
    search_fields = ['nombre', 'simbolo']

# --- REGISTRO DEL RESTO DE MODELOS ---
admin.site.register(InterfaceConsumo)
admin.site.register(PuntoMedicion)
admin.site.register(Equipo)
admin.site.register(CaracteristicaMedicion)
admin.site.register(CategoriaPuntoMedicion)
admin.site.register(DocumentoMedicion)
admin.site.register(RangoMedicion)
class ServicioResource(resources.ModelResource):
    class Meta:
        model = Servicio
        fields = ('id', 'nombre', 'descripcion')
        export_order = ('id', 'nombre', 'descripcion')
        skip_unchanged = True
        report_skipped = True

@admin.register(Servicio)
class ServicioAdmin(ImportExportModelAdmin):
    resource_class = ServicioResource
    list_display = ('nombre', 'descripcion')
    search_fields = ('nombre',)

class KPIResource(resources.ModelResource):
    servicio_nombre = fields.Field(
        column_name='servicio_nombre',
        attribute='servicio',
        widget=ForeignKeyWidget(Servicio, field='nombre')
    )

    class Meta:
        model = KPI
        fields = ('id', 'kpi', 'descripcion', 'servicio_nombre')
        export_order = ('id', 'kpi', 'servicio_nombre', 'descripcion')
        skip_unchanged = True
        report_skipped = True

@admin.register(KPI)
class KPIAdmin(ImportExportModelAdmin):
    resource_class = KPIResource
    list_display = ('kpi', 'servicio', 'descripcion')
    list_filter = ('servicio',)
    search_fields = ('kpi', 'descripcion', 'servicio__nombre')

@admin.register(VistaConsumoDiferencia)
class VistaConsumoDiferenciaAdmin(admin.ModelAdmin):
    list_display = ['fecha', 'medidor_id', 'consumo', 'consumo_anterior', 'diferencia_consumo']
    list_filter = ['fecha', 'medidor_id']
    search_fields = ['medidor_id']
    readonly_fields = [f.name for f in VistaConsumoDiferencia._meta.fields]
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False