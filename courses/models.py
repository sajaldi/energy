from django.db import models
from django.contrib.auth.models import User, Group
from django.utils import timezone


class Curso(models.Model):
    titulo = models.CharField(max_length=255, verbose_name="Título")
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    imagen = models.ImageField(upload_to='cursos/', null=True, blank=True, verbose_name="Imagen de portada")
    padre = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='hijos', verbose_name="Curso padre (pensum)")
    orden = models.PositiveIntegerField(default=0, verbose_name="Orden dentro del pensum")
    activo = models.BooleanField(default=True, verbose_name="Activo")
    disponible_para_todos = models.BooleanField(default=False, verbose_name="Disponible para todos",
        help_text="Cualquier usuario puede acceder sin necesidad de asignación")
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Curso"
        verbose_name_plural = "Cursos"
        ordering = ['-creado_en']

    def __str__(self):
        return self.titulo

    def es_pensum(self):
        return self.hijos.exists()

    def total_secciones(self):
        return self.secciones.count()

    def duracion_estimada(self):
        if self.es_pensum():
            total = 0
            for hijo in self.hijos.all():
                total += hijo.duracion_estimada()
            return total
        secs = self.secciones.aggregate(total=models.Sum('duracion_minutos'))['total'] or 0
        pags = Pagina.objects.filter(seccion__curso=self).aggregate(total=models.Sum('duracion_minutos'))['total'] or 0
        return secs + pags

    def total_paginas(self):
        return Pagina.objects.filter(seccion__curso=self).count()


class Seccion(models.Model):
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='secciones', verbose_name="Curso")
    titulo = models.CharField(max_length=255, verbose_name="Título")
    orden = models.PositiveIntegerField(default=0, verbose_name="Orden")
    contenido_html = models.TextField(blank=True, verbose_name="Contenido HTML",
        help_text="Puedes usar HTML, incluir imágenes <img> y videos <iframe>")
    duracion_minutos = models.PositiveIntegerField(default=0, verbose_name="Duración (min)")
    obligatorio = models.BooleanField(default=True, verbose_name="Obligatorio")

    class Meta:
        verbose_name = "Sección"
        verbose_name_plural = "Secciones"
        ordering = ['orden']

    def __str__(self):
        return f"{self.orden}. {self.titulo}"

    def total_paginas(self):
        return self.paginas.count()


class Pagina(models.Model):
    seccion = models.ForeignKey(Seccion, on_delete=models.CASCADE, related_name='paginas', verbose_name="Sección")
    titulo = models.CharField(max_length=255, verbose_name="Título")
    orden = models.PositiveIntegerField(default=0, verbose_name="Orden")
    contenido_html = models.TextField(blank=True, verbose_name="Contenido HTML",
        help_text="Puedes usar HTML, incluir imágenes <img> y videos <iframe>")
    duracion_minutos = models.PositiveIntegerField(default=0, verbose_name="Duración (min)")
    obligatorio = models.BooleanField(default=True, verbose_name="Obligatorio")

    class Meta:
        verbose_name = "Página"
        verbose_name_plural = "Páginas"
        ordering = ['orden']

    def __str__(self):
        return f"{self.orden}. {self.titulo}"


class AsignacionCurso(models.Model):
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='asignaciones', verbose_name="Curso")
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='cursos_asignados', verbose_name="Usuario")
    grupo = models.ForeignKey(Group, on_delete=models.CASCADE, null=True, blank=True, related_name='cursos_asignados', verbose_name="Grupo de usuarios")
    asignado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='asignaciones_curso', verbose_name="Asignado por")
    fecha_asignacion = models.DateTimeField(default=timezone.now, verbose_name="Fecha de asignación")
    fecha_vencimiento = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de vencimiento")
    completado = models.BooleanField(default=False, verbose_name="Completado")
    fecha_completado = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de completado")

    class Meta:
        verbose_name = "Asignación de Curso"
        verbose_name_plural = "Asignaciones de Cursos"
        unique_together = [('curso', 'usuario'), ('curso', 'grupo')]

    def __str__(self):
        target = self.usuario or self.grupo
        return f"{self.curso.titulo} → {target}"

    def usuarios_destino(self):
        if self.usuario:
            return [self.usuario]
        if self.grupo:
            return list(self.grupo.user_set.all())
        return []

    def progreso_porcentaje(self, usuario):
        total = self.curso.total_secciones()
        if total == 0:
            return 100
        completadas = ProgresoSeccion.objects.filter(
            asignacion=self, usuario=usuario, completado=True
        ).count()
        return int((completadas / total) * 100)


class ProgresoSeccion(models.Model):
    asignacion = models.ForeignKey(AsignacionCurso, on_delete=models.CASCADE, related_name='progresos', verbose_name="Asignación")
    seccion = models.ForeignKey(Seccion, on_delete=models.CASCADE, related_name='progresos', verbose_name="Sección")
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='progreso_cursos', verbose_name="Usuario")
    completado = models.BooleanField(default=False, verbose_name="Completado")
    completado_en = models.DateTimeField(null=True, blank=True, verbose_name="Completado en")

    class Meta:
        verbose_name = "Progreso de Sección"
        verbose_name_plural = "Progresos de Secciones"
        unique_together = [('asignacion', 'seccion', 'usuario')]

    def __str__(self):
        return f"{self.usuario} - {self.seccion.titulo}: {'✓' if self.completado else '○'}"


class RegistroTiempo(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tiempo_cursos', verbose_name="Usuario")
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='tiempos', verbose_name="Curso")
    inicio = models.DateTimeField(verbose_name="Inicio")
    fin = models.DateTimeField(null=True, blank=True, verbose_name="Fin")
    duracion_segundos = models.PositiveIntegerField(default=0, verbose_name="Duración (segundos)")

    class Meta:
        verbose_name = "Registro de Tiempo"
        verbose_name_plural = "Registros de Tiempo"
        ordering = ['-inicio']

    def __str__(self):
        return f"{self.usuario} - {self.curso.titulo}: {self.duracion_segundos}s"
