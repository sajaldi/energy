from django.contrib import admin
from django import forms
from django.shortcuts import get_object_or_404
from .models import (
    PerfilContratista, ExpedienteMensual, DocumentoOrdenCompra, DocumentoPersonal,
    TipoDocumentoPersonal, TipoEntregable, EntregableContratista, DocumentoEntregable,
    HistorialPersonal,
)


MESES_CHOICES = [(str(m), ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
                           'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'][m - 1]) for m in range(1, 13)]


class EntregableContratistaForm(forms.ModelForm):
    meses = forms.MultipleChoiceField(
        choices=MESES_CHOICES,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'meses-checkboxes'}),
        required=False,
        label='Meses de aplicación',
        help_text='Selecciona los meses en que aplica este entregable. Si no seleccionas ninguno, aplica todos.',
    )

    class Meta:
        model = EntregableContratista
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.meses_aplicacion:
            self.fields['meses'].initial = [str(m) for m in self.instance.get_meses()]
        self.fields['meses_aplicacion'].widget = forms.HiddenInput()

    def clean(self):
        cleaned = super().clean()
        meses = cleaned.get('meses')
        if meses:
            cleaned['meses_aplicacion'] = sorted(int(m) for m in meses)
        else:
            cleaned['meses_aplicacion'] = []
        return cleaned


@admin.register(PerfilContratista)
class PerfilContratistaAdmin(admin.ModelAdmin):
    list_display = ('user', 'empresa', 'cargo', 'activo', 'creado_en')
    list_filter = ('activo', 'empresa')
    search_fields = ('user__username', 'user__email', 'empresa__nombre')
    autocomplete_fields = ('user', 'empresa')


@admin.register(ExpedienteMensual)
class ExpedienteMensualAdmin(admin.ModelAdmin):
    list_display = ('empresa', 'mes', 'anio', 'estado', 'fecha_envio', 'fecha_revision')
    list_filter = ('estado', 'anio', 'mes')
    search_fields = ('empresa__nombre',)
    autocomplete_fields = ('empresa', 'revisado_por')
    date_hierarchy = 'fecha_envio'


@admin.register(DocumentoOrdenCompra)
class DocumentoOrdenCompraAdmin(admin.ModelAdmin):
    list_display = ('orden_compra', 'tipo', 'subido_por', 'es_valido', 'creado_en')
    list_filter = ('tipo', 'es_valido')
    search_fields = ('orden_compra__numero_oc', 'descripcion')
    autocomplete_fields = ('orden_compra', 'subido_por')


@admin.register(TipoDocumentoPersonal)
class TipoDocumentoPersonalAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'activo', 'orden')
    list_filter = ('activo',)
    search_fields = ('nombre',)
    list_editable = ('activo', 'orden')


@admin.register(DocumentoPersonal)
class DocumentoPersonalAdmin(admin.ModelAdmin):
    list_display = ('tecnico', 'tipo', 'es_valido', 'creado_en')
    list_filter = ('tipo', 'es_valido')
    search_fields = ('tecnico__nombre', 'tecnico__apellido', 'tecnico__dni')
    autocomplete_fields = ('tecnico', 'subido_por', 'tipo')


@admin.register(TipoEntregable)
class TipoEntregableAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'activo', 'creado_en')
    list_filter = ('activo',)
    search_fields = ('nombre',)


@admin.register(EntregableContratista)
class EntregableContratistaAdmin(admin.ModelAdmin):
    form = EntregableContratistaForm
    list_display = ('empresa', 'tipo_entregable', 'meses_resumen', 'obligatorio', 'activo')
    list_filter = ('obligatorio', 'activo', 'tipo_entregable')
    search_fields = ('empresa__nombre', 'tipo_entregable__nombre')
    autocomplete_fields = ('empresa', 'tipo_entregable')
    fieldsets = (
        (None, {
            'fields': ('empresa', 'tipo_entregable', 'obligatorio', 'activo')
        }),
        ('Meses de aplicación', {
            'fields': ('meses', 'meses_aplicacion'),
            'description': 'Marca los meses en que este entregable debe ser presentado. Si ninguno está marcado, aplica para todos los meses.',
        }),
    )

    class Media:
        css = {
            'all': ('admin/css/widgets.css',)
        }

    def meses_resumen(self, obj):
        meses = obj.get_meses()
        if not meses:
            return 'Todos'
        names = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
                 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
        return ', '.join(names[m - 1] for m in meses)
    meses_resumen.short_description = 'Meses'

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('matriz/', self.admin_site.admin_view(self.matriz_list), name='portalsub_entregablecontratista_matriz'),
            path('matriz/<int:empresa_id>/', self.admin_site.admin_view(self.matriz_edit), name='portalsub_entregablecontratista_matriz_edit'),
        ]
        return custom_urls + urls

    def matriz_list(self, request):
        from mantenimiento.models import Empresa
        from django.db.models import Count, Q
        from django.shortcuts import render

        empresas = Empresa.objects.filter(activo=True).annotate(
            total_configs=Count('entregables_config', filter=Q(entregables_config__activo=True)),
            total_tipos=Count('entregables_config'),
        ).order_by('nombre')

        context = {
            **self.admin_site.each_context(request),
            'title': 'Matriz de Entregables por Subcontratista',
            'empresas': empresas,
            'opts': self.model._meta,
        }
        return render(request, 'admin/portalsub/entregablecontratista/matriz_list.html', context)

    def matriz_edit(self, request, empresa_id):
        from mantenimiento.models import Empresa
        from django.shortcuts import render, redirect
        from django.contrib import messages
        from django.urls import reverse

        empresa = get_object_or_404(Empresa, pk=empresa_id)

        if request.method == 'POST':
            if request.POST.get('nuevo_nombre'):
                nombre = request.POST.get('nuevo_nombre', '').strip()
                if nombre:
                    tipo, created = TipoEntregable.objects.get_or_create(
                        nombre=nombre, defaults={'activo': True}
                    )
                    if created:
                        EntregableContratista.objects.get_or_create(
                            empresa=empresa, tipo_entregable=tipo,
                            defaults={'obligatorio': True}
                        )
                        messages.success(request, f'Entregable "{nombre}" creado.')
                    else:
                        messages.warning(request, f'El entregable "{nombre}" ya existe.')
                return redirect('admin:portalsub_entregablecontratista_matriz_edit', empresa_id=empresa_id)

            for t in TipoEntregable.objects.filter(activo=True):
                config, _ = EntregableContratista.objects.get_or_create(
                    empresa=empresa, tipo_entregable=t,
                    defaults={'obligatorio': True}
                )
                meses_key = f'meses_{t.id}'
                selected = request.POST.getlist(meses_key)
                config.meses_aplicacion = sorted(int(m) for m in selected) if selected else []
                config.obligatorio = request.POST.get(f'obligatorio_{t.id}') == 'on'
                config.activo = request.POST.get(f'activo_{t.id}') == 'on'
                config.save()

            messages.success(request, f'Matriz actualizada para {empresa.nombre}')
            return redirect('admin:portalsub_entregablecontratista_matriz')

        tipos = TipoEntregable.objects.filter(activo=True).order_by('nombre')
        configs = {
            c.tipo_entregable_id: c
            for c in EntregableContratista.objects.filter(empresa=empresa).select_related('tipo_entregable')
        }

        names = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
                 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
        rows = []
        for t in tipos:
            c = configs.get(t.id)
            if not c:
                c = EntregableContratista(empresa=empresa, tipo_entregable=t, meses_aplicacion=[])
            meses_set = set(c.get_meses())
            rows.append({
                'tipo': t,
                'config': c,
                'meses': [(m, m in meses_set, names[m - 1]) for m in range(1, 13)],
            })

        context = {
            **self.admin_site.each_context(request),
            'title': f'Matriz de Entregables — {empresa.nombre}',
            'empresa': empresa,
            'rows': rows,
            'opts': self.model._meta,
        }
        return render(request, 'admin/portalsub/entregablecontratista/matriz_edit.html', context)


@admin.register(DocumentoEntregable)
class DocumentoEntregableAdmin(admin.ModelAdmin):
    list_display = ('empresa', 'tipo_entregable', 'mes', 'anio', 'es_valido', 'creado_en')
    list_filter = ('es_valido', 'anio')
    search_fields = ('empresa__nombre', 'tipo_entregable__nombre')
    autocomplete_fields = ('empresa', 'tipo_entregable', 'subido_por')


@admin.register(HistorialPersonal)
class HistorialPersonalAdmin(admin.ModelAdmin):
    list_display = ('tecnico', 'tipo', 'fecha', 'usuario')
    list_filter = ('tipo',)
    search_fields = ('tecnico__nombre', 'tecnico__apellido', 'detalle')
    autocomplete_fields = ('tecnico', 'usuario')
    readonly_fields = ('tecnico', 'tipo', 'fecha', 'usuario', 'detalle')
