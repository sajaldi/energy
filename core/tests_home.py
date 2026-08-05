from django.contrib.auth.models import Group, User
from django.test import Client, TestCase
from django.urls import reverse

from core.models import AdminNavItem, AdminNavMenu, PerfilUsuario


class HomePageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="home_tester", password="pass1234", is_staff=True
        )
        PerfilUsuario.objects.get_or_create(usuario=cls.user)
        cls.menu = AdminNavMenu.objects.create(
            name="Mantenimiento",
            icon="fas fa-tools",
            color="#f97316",
            order=1,
            descripcion="Prueba",
        )
        cls.grupo = Group.objects.create(name="Mantenimiento")
        cls.menu.grupos.add(cls.grupo)
        AdminNavItem.objects.create(
            menu=cls.menu, name="Mis OT", url="/admin/mantenimiento/ordentrabajo/"
        )

    def test_anonymous_redirects_to_login(self):
        r = Client().get(reverse("core:home"))
        self.assertEqual(r.status_code, 302)
        self.assertIn("/admin/login/", r.url)

    def test_admin_login_redirects_to_home_by_default(self):
        c = Client()
        r = c.post(
            "/admin/login/",
            {"username": "home_tester", "password": "pass1234"},
        )
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, "/inicio/")

    def test_admin_login_ignores_admin_index_next(self):
        c = Client()
        r = c.post(
            "/admin/login/?next=/admin/",
            {"username": "home_tester", "password": "pass1234"},
        )
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, "/inicio/")

    def test_admin_login_preserves_deep_link(self):
        c = Client()
        r = c.post(
            "/admin/login/?next=/admin/core/consumo/",
            {"username": "home_tester", "password": "pass1234"},
        )
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, "/admin/core/consumo/")

    def test_home_renders_for_staff(self):
        c = Client()
        self.assertTrue(c.login(username="home_tester", password="pass1234"))
        r = c.get(reverse("core:home"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "window.__HOME_DATA__")

    def test_guardar_config_persists(self):
        c = Client()
        c.login(username="home_tester", password="pass1234")
        payload = '{"hidden_menus": ["Mantenimiento"], "custom_menus": []}'
        r = c.post(
            reverse("core:guardar_home_config"), data=payload, content_type="application/json"
        )
        self.assertEqual(r.status_code, 200)
        perfil = PerfilUsuario.objects.get(usuario=self.user)
        self.assertIn("Mantenimiento", perfil.nav_config["hidden_menus"])

    def test_menu_hidden_for_user_without_group(self):
        other = User.objects.create_user(
            username="sin_grupo", password="pass1234", is_staff=True
        )
        PerfilUsuario.objects.get_or_create(usuario=other)
        names = [m["name"] for m in AdminNavMenu.menus_base(other)]
        self.assertNotIn("Mantenimiento", names)

    def test_menu_visible_for_user_with_group(self):
        self.user.groups.add(self.grupo)
        names = [m["name"] for m in AdminNavMenu.menus_base(self.user)]
        self.assertIn("Mantenimiento", names)

    def test_menu_visible_for_superuser(self):
        admin = User.objects.create_superuser(
            username="home_admin", password="pass1234"
        )
        names = [m["name"] for m in AdminNavMenu.menus_base(admin)]
        self.assertIn("Mantenimiento", names)
