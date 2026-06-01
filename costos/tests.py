from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from decimal import Decimal
from .models import AnalisisCostoUnitario, DetalleCostoUnitario, FactorCosto
from .forms import (
    AnalisisCostoUnitarioForm,
    AnalisisCostoUnitarioCreateForm,
    DetalleCostoUnitarioForm,
    FactorCostoForm,
)
from inventarios.models import UnidadMedida


class UnidadMedidaFactory:
    @staticmethod
    def create(nombre="Metro", abreviatura="m"):
        return UnidadMedida.objects.create(nombre=nombre, abreviatura=abreviatura)


class TestModels(TestCase):
    def setUp(self):
        self.unidad = UnidadMedidaFactory.create()
        self.user = User.objects.create_user(username="testuser", password="testpass")

    def test_codigo_auto_generado(self):
        acu = AnalisisCostoUnitario.objects.create(
            nombre="Prueba", unidad=self.unidad, creado_por=self.user
        )
        self.assertTrue(acu.codigo.startswith("ACU-"))
        self.assertIn(str(acu.codigo), str(acu))

    def test_costo_directo_total_vacio(self):
        acu = AnalisisCostoUnitario.objects.create(
            nombre="Test", unidad=self.unidad, creado_por=self.user
        )
        self.assertEqual(acu.costo_directo_total, Decimal("0"))

    def test_costo_directo_total_con_detalles(self):
        acu = AnalisisCostoUnitario.objects.create(
            nombre="Test", unidad=self.unidad, creado_por=self.user
        )
        DetalleCostoUnitario.objects.create(
            analisis=acu, unidad=self.unidad,
            cantidad=Decimal("2"), precio_unitario=Decimal("100"),
            factor_rendimiento=Decimal("1"),
        )
        DetalleCostoUnitario.objects.create(
            analisis=acu, unidad=self.unidad,
            cantidad=Decimal("3"), precio_unitario=Decimal("50"),
            factor_rendimiento=Decimal("1"),
        )
        expected = Decimal("2") * Decimal("100") * Decimal("1") + Decimal("3") * Decimal("50") * Decimal("1")
        self.assertEqual(acu.costo_directo_total, expected)

    def test_indirectos_porcentaje(self):
        acu = AnalisisCostoUnitario.objects.create(
            nombre="Test", unidad=self.unidad, creado_por=self.user
        )
        DetalleCostoUnitario.objects.create(
            analisis=acu, unidad=self.unidad,
            cantidad=Decimal("1"), precio_unitario=Decimal("1000"),
            factor_rendimiento=Decimal("1"),
        )
        FactorCosto.objects.create(
            analisis=acu, nombre="Indirectos", tipo="PORCENTAJE", valor=Decimal("15")
        )
        self.assertEqual(acu.total_indirectos, Decimal("150"))
        self.assertEqual(acu.costo_total, Decimal("1150"))
        self.assertEqual(acu.factor_total_porcentaje, Decimal("15"))

    def test_indirectos_monto_fijo(self):
        acu = AnalisisCostoUnitario.objects.create(
            nombre="Test", unidad=self.unidad, creado_por=self.user
        )
        DetalleCostoUnitario.objects.create(
            analisis=acu, unidad=self.unidad,
            cantidad=Decimal("1"), precio_unitario=Decimal("1000"),
            factor_rendimiento=Decimal("1"),
        )
        FactorCosto.objects.create(
            analisis=acu, nombre="Fijo", tipo="MONTO_FIJO", valor=Decimal("200")
        )
        self.assertEqual(acu.total_indirectos, Decimal("200"))
        self.assertEqual(acu.costo_total, Decimal("1200"))

    def test_indirectos_cero_sin_directos(self):
        acu = AnalisisCostoUnitario.objects.create(
            nombre="Test", unidad=self.unidad, creado_por=self.user
        )
        FactorCosto.objects.create(
            analisis=acu, nombre="Indirectos", tipo="PORCENTAJE", valor=Decimal("15")
        )
        self.assertEqual(acu.total_indirectos, Decimal("0"))
        self.assertEqual(acu.factor_total_porcentaje, Decimal("0"))

    def test_detalle_total_parcial(self):
        acu = AnalisisCostoUnitario.objects.create(
            nombre="Test", unidad=self.unidad, creado_por=self.user
        )
        det = DetalleCostoUnitario.objects.create(
            analisis=acu, unidad=self.unidad,
            cantidad=Decimal("5.5"), precio_unitario=Decimal("120"),
            factor_rendimiento=Decimal("0.9"),
            tipo_recurso="MATERIAL",
            descripcion="Material de prueba",
        )
        expected = Decimal("5.5") * Decimal("120") * Decimal("0.9")
        self.assertEqual(det.total_parcial, expected)
        self.assertEqual(det.display_nombre, "Material de prueba")

    def test_factor_str(self):
        acu = AnalisisCostoUnitario.objects.create(
            nombre="Test", unidad=self.unidad, creado_por=self.user
        )
        fp = FactorCosto.objects.create(
            analisis=acu, nombre="Herramientas", tipo="PORCENTAJE", valor=Decimal("5")
        )
        self.assertEqual(str(fp), "Herramientas: 5%")
        ff = FactorCosto.objects.create(
            analisis=acu, nombre="Fijo", tipo="MONTO_FIJO", valor=Decimal("100")
        )
        self.assertEqual(str(ff), "Fijo: 100")


class TestForms(TestCase):
    def setUp(self):
        self.unidad = UnidadMedidaFactory.create()

    def test_analisis_create_form_valido(self):
        form = AnalisisCostoUnitarioCreateForm(data={
            "nombre": "Prueba",
            "descripcion": "Descripción",
            "unidad": self.unidad.pk,
        })
        self.assertTrue(form.is_valid())

    def test_analisis_create_form_requiere_nombre(self):
        form = AnalisisCostoUnitarioCreateForm(data={
            "unidad": self.unidad.pk,
        })
        self.assertFalse(form.is_valid())
        self.assertIn("nombre", form.errors)

    def test_analisis_update_form_incluye_estado(self):
        form = AnalisisCostoUnitarioForm(data={
            "nombre": "Prueba",
            "unidad": self.unidad.pk,
            "estado": "BORRADOR",
        })
        self.assertTrue(form.is_valid())

    def test_detalle_form_valido(self):
        form = DetalleCostoUnitarioForm(data={
            "tipo_recurso": "MATERIAL",
            "descripcion": "Arena",
            "unidad": self.unidad.pk,
            "cantidad": "2.5000",
            "precio_unitario": "150.00",
            "factor_rendimiento": "1.0500",
        })
        self.assertTrue(form.is_valid())

    def test_detalle_form_cantidad_cero_invalido(self):
        form = DetalleCostoUnitarioForm(data={
            "tipo_recurso": "MATERIAL",
            "descripcion": "Arena",
            "unidad": self.unidad.pk,
            "cantidad": "0",
            "precio_unitario": "150.00",
            "factor_rendimiento": "1.0500",
        })
        self.assertFalse(form.is_valid())

    def test_factor_form_valido(self):
        form = FactorCostoForm(data={
            "nombre": "Herramientas",
            "tipo": "PORCENTAJE",
            "valor": "5.00",
        })
        self.assertTrue(form.is_valid())


class TestViews(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.unidad = UnidadMedidaFactory.create()
        ct_acu = ContentType.objects.get_for_model(AnalisisCostoUnitario)
        ct_det = ContentType.objects.get_for_model(DetalleCostoUnitario)
        ct_fac = ContentType.objects.get_for_model(FactorCosto)
        cls.user = User.objects.create_user(username="analista", password="testpass")
        for perm in Permission.objects.filter(
            content_type__in=[ct_acu, ct_det, ct_fac]
        ):
            cls.user.user_permissions.add(perm)

    def setUp(self):
        self.client.login(username="analista", password="testpass")

    def test_list_view(self):
        resp = self.client.get(reverse("costos:analisis_list"))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "costos/analisis_list.html")

    def test_create_view(self):
        resp = self.client.post(reverse("costos:analisis_create"), {
            "nombre": "ACU de prueba",
            "unidad": self.unidad.pk,
        }, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(AnalisisCostoUnitario.objects.filter(nombre="ACU de prueba").exists())

    def test_detail_view(self):
        acu = AnalisisCostoUnitario.objects.create(
            nombre="Detalle test", unidad=self.unidad, creado_por=self.user
        )
        resp = self.client.get(reverse("costos:analisis_detail", kwargs={"pk": acu.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, acu.codigo)

    def test_update_view(self):
        acu = AnalisisCostoUnitario.objects.create(
            nombre="Original", unidad=self.unidad, creado_por=self.user
        )
        resp = self.client.post(
            reverse("costos:analisis_update", kwargs={"pk": acu.pk}),
            {"nombre": "Actualizado", "unidad": self.unidad.pk, "estado": "BORRADOR"},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        acu.refresh_from_db()
        self.assertEqual(acu.nombre, "Actualizado")

    def test_delete_view(self):
        acu = AnalisisCostoUnitario.objects.create(
            nombre="A eliminar", unidad=self.unidad, creado_por=self.user
        )
        resp = self.client.post(
            reverse("costos:analisis_delete", kwargs={"pk": acu.pk}), follow=True
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(AnalisisCostoUnitario.objects.filter(pk=acu.pk).exists())

    def test_aprobar_view(self):
        acu = AnalisisCostoUnitario.objects.create(
            nombre="A aprobar", unidad=self.unidad, creado_por=self.user
        )
        DetalleCostoUnitario.objects.create(
            analisis=acu, unidad=self.unidad,
            cantidad=Decimal("1"), precio_unitario=Decimal("100"),
            factor_rendimiento=Decimal("1"),
        )
        resp = self.client.post(
            reverse("costos:analisis_aprobar", kwargs={"pk": acu.pk}), follow=True
        )
        self.assertEqual(resp.status_code, 200)
        acu.refresh_from_db()
        self.assertEqual(acu.estado, "APROBADO")
        self.assertEqual(acu.aprobado_por, self.user)

    def test_aprobar_sin_recursos_rechaza(self):
        acu = AnalisisCostoUnitario.objects.create(
            nombre="Sin recursos", unidad=self.unidad, creado_por=self.user
        )
        resp = self.client.post(
            reverse("costos:analisis_aprobar", kwargs={"pk": acu.pk}), follow=True
        )
        self.assertEqual(resp.status_code, 200)
        acu.refresh_from_db()
        self.assertEqual(acu.estado, "BORRADOR")

    def test_clonar_view(self):
        acu = AnalisisCostoUnitario.objects.create(
            nombre="Original", unidad=self.unidad, creado_por=self.user
        )
        DetalleCostoUnitario.objects.create(
            analisis=acu, unidad=self.unidad,
            cantidad=Decimal("2"), precio_unitario=Decimal("50"),
            factor_rendimiento=Decimal("1"),
        )
        FactorCosto.objects.create(
            analisis=acu, nombre="Indirecto", tipo="PORCENTAJE", valor=Decimal("10"),
        )
        resp = self.client.post(
            reverse("costos:analisis_clonar", kwargs={"pk": acu.pk}), follow=True
        )
        self.assertEqual(resp.status_code, 200)
        clones = AnalisisCostoUnitario.objects.filter(nombre="Original (copia)")
        self.assertEqual(clones.count(), 1)
        clone = clones.first()
        self.assertEqual(clone.detalles.count(), 1)
        self.assertEqual(clone.factores.count(), 1)
        self.assertEqual(clone.detalles.first().cantidad, Decimal("2"))
        self.assertEqual(clone.factores.first().valor, Decimal("10"))

    def test_detalle_create_view(self):
        acu = AnalisisCostoUnitario.objects.create(
            nombre="Con detalle", unidad=self.unidad, creado_por=self.user
        )
        resp = self.client.post(
            reverse("costos:detalle_create", kwargs={"pk": acu.pk}),
            {
                "tipo_recurso": "MATERIAL",
                "descripcion": "Cemento",
                "unidad": self.unidad.pk,
                "cantidad": "1.0000",
                "precio_unitario": "200.00",
                "factor_rendimiento": "1.0000",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            DetalleCostoUnitario.objects.filter(descripcion="Cemento").exists()
        )

    def test_factor_create_view(self):
        acu = AnalisisCostoUnitario.objects.create(
            nombre="Con factor", unidad=self.unidad, creado_por=self.user
        )
        resp = self.client.post(
            reverse("costos:factor_create", kwargs={"pk": acu.pk}),
            {"nombre": "Indirectos", "tipo": "PORCENTAJE", "valor": "15.00"},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            FactorCosto.objects.filter(nombre="Indirectos").exists()
        )

    def test_list_search(self):
        acu = AnalisisCostoUnitario.objects.create(
            nombre="Busqueda test", unidad=self.unidad, creado_por=self.user
        )
        resp = self.client.get(reverse("costos:analisis_list"), {"q": "Busqueda"})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, acu.codigo)

    def test_permission_denied_sin_login(self):
        self.client.logout()
        resp = self.client.get(reverse("costos:analisis_list"))
        self.assertEqual(resp.status_code, 302)
