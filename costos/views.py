from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from .models import AnalisisCostoUnitario, DetalleCostoUnitario, FactorCosto
from .forms import (
    AnalisisCostoUnitarioForm,
    AnalisisCostoUnitarioCreateForm,
    DetalleCostoUnitarioForm,
    FactorCostoForm,
)


class AnalisisListView(PermissionRequiredMixin, ListView):
    model = AnalisisCostoUnitario
    permission_required = 'costos.view_analisiscostounitario'
    template_name = 'costos/analisis_list.html'
    context_object_name = 'analisis_list'
    paginate_by = 25

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(nombre__icontains=q) | qs.filter(codigo__icontains=q)
        return qs.select_related('unidad', 'proyecto')


class AnalisisDetailView(PermissionRequiredMixin, DetailView):
    model = AnalisisCostoUnitario
    permission_required = 'costos.view_analisiscostounitario'
    template_name = 'costos/analisis_detail.html'
    context_object_name = 'analisis'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['detalles'] = self.object.detalles.select_related('material', 'unidad').order_by('orden', 'id')
        ctx['factores'] = self.object.factores.all().order_by('orden', 'id')
        return ctx


class AnalisisCreateView(PermissionRequiredMixin, CreateView):
    model = AnalisisCostoUnitario
    permission_required = 'costos.add_analisiscostounitario'
    template_name = 'costos/analisis_form.html'
    form_class = AnalisisCostoUnitarioCreateForm

    def form_valid(self, form):
        form.instance.creado_por = self.request.user
        return super().form_valid(form)


class AnalisisUpdateView(PermissionRequiredMixin, UpdateView):
    model = AnalisisCostoUnitario
    permission_required = 'costos.change_analisiscostounitario'
    template_name = 'costos/analisis_form.html'
    form_class = AnalisisCostoUnitarioForm


class AnalisisDeleteView(PermissionRequiredMixin, DeleteView):
    model = AnalisisCostoUnitario
    permission_required = 'costos.delete_analisiscostounitario'
    template_name = 'costos/analisis_confirm_delete.html'
    success_url = reverse_lazy('costos:analisis_list')


class AprobarAnalisisView(PermissionRequiredMixin, View):
    permission_required = 'costos.change_analisiscostounitario'

    def post(self, request, pk):
        analisis = get_object_or_404(AnalisisCostoUnitario, pk=pk)
        if analisis.estado == 'BORRADOR':
            if analisis.detalles.count() == 0:
                messages.error(request, 'No se puede aprobar un ACU sin recursos directos.')
                return redirect('costos:analisis_detail', pk=pk)
            analisis.estado = 'APROBADO'
            analisis.aprobado_por = request.user
            analisis.fecha_aprobacion = timezone.now()
            analisis.save()
            messages.success(request, f'ACU {analisis.codigo} aprobado correctamente.')
        else:
            messages.warning(request, f'El ACU ya está en estado "{analisis.get_estado_display()}".')
        return redirect('costos:analisis_detail', pk=pk)


class ClonarAnalisisView(PermissionRequiredMixin, View):
    permission_required = 'costos.add_analisiscostounitario'

    def post(self, request, pk):
        original = get_object_or_404(
            AnalisisCostoUnitario.objects.prefetch_related('detalles', 'factores'),
            pk=pk,
        )
        with transaction.atomic():
            clone = AnalisisCostoUnitario.objects.create(
                nombre=f'{original.nombre} (copia)',
                descripcion=original.descripcion,
                unidad=original.unidad,
                proyecto=original.proyecto,
                creado_por=request.user,
            )
            for det in original.detalles.all():
                DetalleCostoUnitario.objects.create(
                    analisis=clone,
                    tipo_recurso=det.tipo_recurso,
                    material=det.material,
                    descripcion=det.descripcion,
                    unidad=det.unidad,
                    cantidad=det.cantidad,
                    precio_unitario=det.precio_unitario,
                    factor_rendimiento=det.factor_rendimiento,
                    orden=det.orden,
                )
            for fac in original.factores.all():
                FactorCosto.objects.create(
                    analisis=clone,
                    nombre=fac.nombre,
                    tipo=fac.tipo,
                    valor=fac.valor,
                    orden=fac.orden,
                )
        messages.success(request, f'ACU clonado como {clone.codigo}.')
        return redirect('costos:analisis_detail', pk=clone.pk)


class DetalleCreateView(PermissionRequiredMixin, CreateView):
    model = DetalleCostoUnitario
    permission_required = 'costos.add_detallecostounitario'
    template_name = 'costos/detalle_form.html'
    form_class = DetalleCostoUnitarioForm

    def dispatch(self, *args, **kwargs):
        self.analisis = get_object_or_404(AnalisisCostoUnitario, pk=kwargs['pk'])
        return super().dispatch(*args, **kwargs)

    def form_valid(self, form):
        form.instance.analisis = self.analisis
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('costos:analisis_detail', kwargs={'pk': self.analisis.pk})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['analisis'] = self.analisis
        return ctx


class DetalleUpdateView(PermissionRequiredMixin, UpdateView):
    model = DetalleCostoUnitario
    permission_required = 'costos.change_detallecostounitario'
    template_name = 'costos/detalle_form.html'
    pk_url_kwarg = 'detalle_pk'
    form_class = DetalleCostoUnitarioForm

    def get_success_url(self):
        return reverse_lazy('costos:analisis_detail', kwargs={'pk': self.object.analisis.pk})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['analisis'] = self.object.analisis
        return ctx


class DetalleDeleteView(PermissionRequiredMixin, DeleteView):
    model = DetalleCostoUnitario
    permission_required = 'costos.delete_detallecostounitario'
    pk_url_kwarg = 'detalle_pk'
    template_name = 'costos/detalle_confirm_delete.html'

    def get_success_url(self):
        return reverse_lazy('costos:analisis_detail', kwargs={'pk': self.object.analisis.pk})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['analisis'] = self.object.analisis
        return ctx


class FactorCreateView(PermissionRequiredMixin, CreateView):
    model = FactorCosto
    permission_required = 'costos.add_factorcosto'
    template_name = 'costos/factor_form.html'
    form_class = FactorCostoForm

    def dispatch(self, *args, **kwargs):
        self.analisis = get_object_or_404(AnalisisCostoUnitario, pk=kwargs['pk'])
        return super().dispatch(*args, **kwargs)

    def form_valid(self, form):
        form.instance.analisis = self.analisis
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('costos:analisis_detail', kwargs={'pk': self.analisis.pk})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['analisis'] = self.analisis
        return ctx


class FactorUpdateView(PermissionRequiredMixin, UpdateView):
    model = FactorCosto
    permission_required = 'costos.change_factorcosto'
    template_name = 'costos/factor_form.html'
    pk_url_kwarg = 'factor_pk'
    form_class = FactorCostoForm

    def get_success_url(self):
        return reverse_lazy('costos:analisis_detail', kwargs={'pk': self.object.analisis.pk})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['analisis'] = self.object.analisis
        return ctx


class FactorDeleteView(PermissionRequiredMixin, DeleteView):
    model = FactorCosto
    permission_required = 'costos.delete_factorcosto'
    pk_url_kwarg = 'factor_pk'
    template_name = 'costos/factor_confirm_delete.html'

    def get_success_url(self):
        return reverse_lazy('costos:analisis_detail', kwargs={'pk': self.object.analisis.pk})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['analisis'] = self.object.analisis
        return ctx
