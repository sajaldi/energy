from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.shortcuts import render
from django.utils.html import format_html
from django.urls import reverse
from import_export.admin import ImportExportModelAdmin

from .models_riesgos import (
    Riesgo,
    EvaluacionRiesgo,
    PlanTratamiento,
    AccionTratamiento,
    ConfiguracionRiesgoServicio,
)
from .resources_riesgos import RiesgoResource

User = get_user_model()


class EvaluacionRiesgoInline(admin.StackedInline):
    model = EvaluacionRiesgo
    extra = 0
    fields = (
        'tipo',
        'probabilidad',
        'impacto',
        'nivel_riesgo',
        'zona_riesgo',
        'justificacion_probabilidad',
        'justificacion_impacto',
        'evaluado_por',
        'fecha_evaluacion',
    )
    readonly_fields = ('nivel_riesgo', 'zona_riesgo', 'fecha_evaluacion')


@admin.register(Riesgo)
class RiesgoAdmin(ImportExportModelAdmin):
    change_list_template = "admin/mantenimiento/procedimiento/change_list.html"
    list_display = (
        'codigo',
        'titulo',
        'servicio',
        'categoria',
        'estado',
        'estado_apetito',
        'estado_revision',
        'editar_fiori',
    )
    list_filter = ('servicio', 'categoria', 'estado', 'estado_apetito', 'estado_revision')
    search_fields = ('codigo', 'titulo', 'descripcion', 'servicio__nombre')
    ordering = ['-fecha_identificacion']
    readonly_fields = (
        'codigo',
        'fecha_identificacion',
        'creado_por',
        'fecha_actualizacion',
        'estado_apetito',
        'estado_revision',
        'kpis_vinculados_display',
    )
    inlines = [EvaluacionRiesgoInline]
    actions = ['reasignar_responsable', 'cambiar_ciclo_revision', 'exportar_seleccion_excel']

    def editar_fiori(self, obj):
        url = reverse('admin:servicios_riesgo_change', args=[obj.pk])
        return format_html(
            '<a href="{}" style="background:#0a6ed1;color:#fff;padding:5px 12px;border-radius:6px;'
            'font-size:12px;font-weight:600;text-decoration:none;display:inline-flex;align-items:center;gap:4px;">'
            '<i class="fas fa-pen" style="font-size:10px;"></i> Editar</a>', url
        )
    editar_fiori.short_description = "Acciones"

    def kpis_vinculados_display(self, obj):
        """
        Muestra los KPIs vinculados al Riesgo con badge de estado,
        ordenados por criticidad: INCUMPLIMIENTO > PARCIAL > CUMPLIMIENTO.
        Requirement 7.4.
        """
        if not obj.pk:
            return "-"

        from django.db.models import Case, When, IntegerField

        kpis = obj.kpis.annotate(
            criticidad_orden=Case(
                When(estado='INCUMPLIMIENTO', then=0),
                When(estado='PARCIAL', then=1),
                When(estado='CUMPLIMIENTO', then=2),
                default=3,
                output_field=IntegerField(),
            )
        ).order_by('criticidad_orden', 'nombre')

        if not kpis.exists():
            return format_html('<span style="color:#888;">Sin KPIs vinculados</span>')

        colores_estado = {
            'INCUMPLIMIENTO': '#dc3545',
            'PARCIAL': '#fd7e14',
            'CUMPLIMIENTO': '#28a745',
        }
        etiquetas_estado = {
            'INCUMPLIMIENTO': 'Incumplimiento',
            'PARCIAL': 'Parcial',
            'CUMPLIMIENTO': 'Cumplimiento',
        }

        items = []
        for kpi in kpis:
            color = colores_estado.get(kpi.estado, '#6c757d')
            etiqueta = etiquetas_estado.get(kpi.estado, kpi.estado)
            badge = (
                f'<span style="background:{color};color:#fff;padding:2px 6px;'
                f'border-radius:3px;font-size:10px;font-weight:600;">'
                f'{etiqueta}</span>'
            )
            items.append(
                f'<li style="margin-bottom:4px;">'
                f'{badge} '
                f'<span style="font-size:12px;">{kpi.nombre}</span>'
                f'</li>'
            )

        html = (
            f'<ul style="list-style:none;padding:0;margin:0;">'
            f'{"".join(items)}'
            f'</ul>'
        )
        return format_html(html)

    kpis_vinculados_display.short_description = "KPIs Vinculados"

    # ─── Bulk Actions ─────────────────────────────────────────────────────────

    @admin.action(description="👤 Reasignar Responsable")
    def reasignar_responsable(self, request, queryset):
        """
        Acción masiva para reasignar el responsable de los riesgos seleccionados.
        Usa una página intermedia con selección de usuario.
        Requirement 11.2, 11.6: cancelar si no se selecciona usuario válido.
        """
        if 'apply' in request.POST:
            responsable_id = request.POST.get('responsable')
            if not responsable_id:
                messages.error(
                    request,
                    "Se debe seleccionar un responsable válido."
                )
                return None

            try:
                nuevo_responsable = User.objects.get(pk=responsable_id)
            except User.DoesNotExist:
                messages.error(
                    request,
                    "Se debe seleccionar un responsable válido."
                )
                return None

            count = queryset.update(responsable=nuevo_responsable)
            messages.success(
                request,
                f"Se reasignó el responsable a "
                f"'{nuevo_responsable.get_full_name() or nuevo_responsable.username}' "
                f"en {count} riesgo(s)."
            )
            return None

        # Render intermediate page with user selection
        usuarios = User.objects.filter(is_active=True).order_by(
            'first_name', 'last_name', 'username'
        )
        context = {
            **self.admin_site.each_context(request),
            'title': 'Reasignar Responsable',
            'riesgos': queryset,
            'usuarios': usuarios,
            'opts': self.model._meta,
            'action_checkbox_name': admin.helpers.ACTION_CHECKBOX_NAME,
        }
        return render(
            request, 'admin/servicios/riesgo/reasignar_responsable.html', context
        )

    @admin.action(description="🔄 Cambiar Ciclo de Revisión")
    def cambiar_ciclo_revision(self, request, queryset):
        """
        Acción masiva para cambiar el ciclo de revisión de los riesgos seleccionados.
        Usa una página intermedia con selección de periodicidad.
        Requirement 11.2.
        """
        if 'apply' in request.POST:
            ciclo = request.POST.get('ciclo_revision')
            ciclos_validos = [c[0] for c in Riesgo.CICLO_CHOICES]

            if not ciclo or ciclo not in ciclos_validos:
                messages.error(
                    request,
                    "Se debe seleccionar un ciclo de revisión válido."
                )
                return None

            count = queryset.update(ciclo_revision=ciclo)
            ciclo_label = dict(Riesgo.CICLO_CHOICES).get(ciclo, ciclo)
            messages.success(
                request,
                f"Se cambió el ciclo de revisión a '{ciclo_label}' en {count} riesgo(s)."
            )
            return None

        # Render intermediate page with cycle selection
        context = {
            **self.admin_site.each_context(request),
            'title': 'Cambiar Ciclo de Revisión',
            'riesgos': queryset,
            'ciclo_choices': Riesgo.CICLO_CHOICES,
            'opts': self.model._meta,
            'action_checkbox_name': admin.helpers.ACTION_CHECKBOX_NAME,
        }
        return render(
            request, 'admin/servicios/riesgo/cambiar_ciclo_revision.html', context
        )

    @admin.action(description="📥 Exportar selección en Excel")
    def exportar_seleccion_excel(self, request, queryset):
        """
        Acción masiva para exportar los riesgos seleccionados en formato Excel (.xlsx)
        usando django-import-export y RiesgoResource.
        Requirement 11.2.
        """
        resource = RiesgoResource()
        dataset = resource.export(queryset)
        response = HttpResponse(
            dataset.xlsx,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = (
            'attachment; filename="riesgos_seleccionados.xlsx"'
        )
        return response


class AccionTratamientoInline(admin.TabularInline):
    model = AccionTratamiento
    fields = ('descripcion', 'fecha_limite', 'responsable', 'estado', 'fecha_completada')
    readonly_fields = ('fecha_completada',)
    extra = 1


@admin.register(PlanTratamiento)
class PlanTratamientoAdmin(ImportExportModelAdmin):
    change_list_template = "admin/mantenimiento/procedimiento/change_list.html"
    list_display = ('riesgo', 'estrategia', 'estado', 'responsable', 'fecha_inicio', 'fecha_limite')
    list_filter = ('estrategia', 'estado')
    search_fields = ('riesgo__codigo', 'riesgo__titulo')
    inlines = [AccionTratamientoInline]

    def save_model(self, request, obj, form, change):
        if obj.estado == 'APROBADO' and not request.user.has_perm('servicios.approve_plantratamiento'):
            messages.error(
                request,
                "No cuenta con permisos suficientes para aprobar planes de tratamiento."
            )
            return
        super().save_model(request, obj, form, change)


@admin.register(ConfiguracionRiesgoServicio)
class ConfiguracionRiesgoServicioAdmin(admin.ModelAdmin):
    list_display = ('servicio', 'apetito_riesgo', 'tolerancia_offset', 'modificado_por', 'fecha_modificacion')
    readonly_fields = ('fecha_modificacion',)

    def has_change_permission(self, request, obj=None):
        base_perm = super().has_change_permission(request, obj)
        return base_perm and request.user.has_perm('servicios.configure_apetito')
