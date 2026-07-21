from django.db import models
from django.contrib.auth.models import User, Group
from django.conf import settings
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


class ImagenInteractiva(models.Model):
    """Imagen con hotspots interactivos para una sección o página."""
    seccion = models.ForeignKey(Seccion, on_delete=models.CASCADE, null=True, blank=True,
        related_name='imagenes_interactivas', verbose_name="Sección")
    pagina = models.ForeignKey(Pagina, on_delete=models.CASCADE, null=True, blank=True,
        related_name='imagenes_interactivas', verbose_name="Página")
    imagen = models.ImageField(upload_to='cursos/interactivas/', verbose_name="Imagen base")
    titulo = models.CharField(max_length=255, blank=True, verbose_name="Título descriptivo")
    orden = models.PositiveIntegerField(default=0, verbose_name="Orden")

    class Meta:
        verbose_name = "Imagen Interactiva"
        verbose_name_plural = "Imágenes Interactivas"
        ordering = ['orden']

    def __str__(self):
        return self.titulo or f"Imagen {self.id}"


class Hotspot(models.Model):
    """Punto interactivo (burbuja) sobre una imagen interactiva."""
    imagen = models.ForeignKey(ImagenInteractiva, on_delete=models.CASCADE,
        related_name='hotspots', verbose_name="Imagen")
    numero = models.PositiveIntegerField(default=1, verbose_name="Número de burbuja")
    pos_x = models.FloatField(verbose_name="Posición X (%)",
        help_text="Porcentaje horizontal (0-100)")
    pos_y = models.FloatField(verbose_name="Posición Y (%)",
        help_text="Porcentaje vertical (0-100)")
    titulo = models.CharField(max_length=255, verbose_name="Título del hotspot")
    contenido_html = models.TextField(blank=True, verbose_name="Contenido HTML",
        help_text="Contenido que se muestra al hacer clic en la burbuja")

    class Meta:
        verbose_name = "Hotspot"
        verbose_name_plural = "Hotspots"


class Acordeon(models.Model):
    """Elemento expandible (accordion) dentro de una sección o página."""
    seccion = models.ForeignKey(Seccion, on_delete=models.CASCADE, null=True, blank=True,
        related_name='acordeones', verbose_name="Sección")
    pagina = models.ForeignKey(Pagina, on_delete=models.CASCADE, null=True, blank=True,
        related_name='acordeones', verbose_name="Página")
    titulo = models.CharField(max_length=255, verbose_name="Título")
    contenido_html = models.TextField(blank=True, verbose_name="Contenido HTML",
        help_text="Contenido que se muestra al expandir")
    orden = models.PositiveIntegerField(default=0, verbose_name="Orden")

    class Meta:
        verbose_name = "Acordeón"
        verbose_name_plural = "Acordeones"
        ordering = ['orden']

    def __str__(self):
        return self.titulo


class Carrusel(models.Model):
    """Carrusel horizontal de tarjetas dentro de una sección o página."""
    seccion = models.ForeignKey(Seccion, on_delete=models.CASCADE, null=True, blank=True,
        related_name='carruseles', verbose_name="Sección")
    pagina = models.ForeignKey(Pagina, on_delete=models.CASCADE, null=True, blank=True,
        related_name='carruseles', verbose_name="Página")
    titulo = models.CharField(max_length=255, blank=True, verbose_name="Título del carrusel")
    orden = models.PositiveIntegerField(default=0, verbose_name="Orden")

    class Meta:
        verbose_name = "Carrusel"
        verbose_name_plural = "Carruseles"
        ordering = ['orden']

    def __str__(self):
        return self.titulo or f"Carrusel {self.id}"


class TarjetaCarrusel(models.Model):
    """Tarjeta individual dentro de un carrusel."""
    carrusel = models.ForeignKey(Carrusel, on_delete=models.CASCADE,
        related_name='tarjetas', verbose_name="Carrusel")
    titulo = models.CharField(max_length=255, verbose_name="Título")
    contenido_html = models.TextField(blank=True, verbose_name="Contenido HTML")
    imagen = models.ImageField(upload_to='cursos/carrusel/', null=True, blank=True, verbose_name="Imagen")
    orden = models.PositiveIntegerField(default=0, verbose_name="Orden")

    class Meta:
        verbose_name = "Tarjeta de Carrusel"
        verbose_name_plural = "Tarjetas de Carrusel"
        ordering = ['orden']

    def __str__(self):
        return self.titulo
        ordering = ['numero']

    def __str__(self):
        return f"#{self.numero} - {self.titulo}"


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


class Evaluacion(models.Model):
    TIPOS = (
        ('MULTIPLE', 'Opción Múltiple'),
        ('V_F', 'Verdadero/Falso'),
        ('MIXTA', 'Mixta'),
    )
    curso = models.ForeignKey('Curso', on_delete=models.CASCADE, related_name='evaluaciones', verbose_name="Curso")
    seccion = models.ForeignKey('Seccion', on_delete=models.SET_NULL, null=True, blank=True, related_name='evaluaciones', verbose_name="Sección")
    pagina = models.ForeignKey('Pagina', on_delete=models.SET_NULL, null=True, blank=True, related_name='evaluaciones', verbose_name="Página")
    titulo = models.CharField(max_length=255, verbose_name="Título")
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    tipo = models.CharField(max_length=10, choices=TIPOS, default='MULTIPLE', verbose_name="Tipo")
    puntaje_maximo = models.DecimalField(max_digits=8, decimal_places=2, default=0, verbose_name="Puntaje máximo")
    puntaje_aprobacion = models.DecimalField(max_digits=8, decimal_places=2, default=0, verbose_name="Puntaje para aprobar")
    tiempo_limite_minutos = models.PositiveIntegerField(default=0, verbose_name="Tiempo límite (min)", help_text="0 = sin límite")
    orden = models.PositiveIntegerField(default=0, verbose_name="Orden")
    activo = models.BooleanField(default=True, verbose_name="Activo")
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['orden']
        verbose_name = "Evaluación"
        verbose_name_plural = "Evaluaciones"

    def __str__(self):
        return f"{self.titulo} ({self.curso.titulo})"


class Pregunta(models.Model):
    TIPOS = (
        ('MULTIPLE', 'Opción Múltiple'),
        ('V_F', 'Verdadero/Falso'),
    )
    evaluacion = models.ForeignKey('Evaluacion', on_delete=models.CASCADE, related_name='preguntas', verbose_name="Evaluación")
    texto = models.TextField(verbose_name="Texto de la pregunta")
    tipo = models.CharField(max_length=10, choices=TIPOS, default='MULTIPLE', verbose_name="Tipo de respuesta")
    puntaje = models.DecimalField(max_digits=6, decimal_places=2, default=1, verbose_name="Puntaje")
    orden = models.PositiveIntegerField(default=0, verbose_name="Orden")
    explicacion = models.TextField(blank=True, verbose_name="Explicación", help_text="Se muestra después de responder")
    obligatorio = models.BooleanField(default=True, verbose_name="Obligatorio")

    class Meta:
        ordering = ['orden']
        verbose_name = "Pregunta"
        verbose_name_plural = "Preguntas"

    def __str__(self):
        return self.texto[:80]


class Opcion(models.Model):
    pregunta = models.ForeignKey('Pregunta', on_delete=models.CASCADE, related_name='opciones', verbose_name="Pregunta")
    texto = models.CharField(max_length=500, verbose_name="Texto de la opción")
    es_correcta = models.BooleanField(default=False, verbose_name="Correcta")
    orden = models.PositiveIntegerField(default=0, verbose_name="Orden")

    class Meta:
        ordering = ['orden']
        verbose_name = "Opción"
        verbose_name_plural = "Opciones"

    def __str__(self):
        return self.texto[:60]


class IntentoEvaluacion(models.Model):
    evaluacion = models.ForeignKey('Evaluacion', on_delete=models.CASCADE, related_name='intentos', verbose_name="Evaluación")
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='intentos_evaluaciones', verbose_name="Usuario")
    asignacion = models.ForeignKey('AsignacionCurso', on_delete=models.SET_NULL, null=True, blank=True, related_name='intentos', verbose_name="Asignación")
    fecha_inicio = models.DateTimeField(auto_now_add=True, verbose_name="Inicio")
    fecha_fin = models.DateTimeField(null=True, blank=True, verbose_name="Fin")
    puntaje_obtenido = models.DecimalField(max_digits=8, decimal_places=2, default=0, verbose_name="Puntaje obtenido")
    puntaje_maximo = models.DecimalField(max_digits=8, decimal_places=2, default=0, verbose_name="Puntaje máximo")
    aprobado = models.BooleanField(default=False, verbose_name="Aprobado")
    intento_numero = models.PositiveIntegerField(default=1, verbose_name="Número de intento")
    completado = models.BooleanField(default=False, verbose_name="Completado")

    class Meta:
        ordering = ['-fecha_inicio']
        verbose_name = "Intento de Evaluación"
        verbose_name_plural = "Intentos de Evaluación"
        unique_together = ['evaluacion', 'usuario', 'intento_numero']

    def __str__(self):
        return f"{self.usuario} - {self.evaluacion.titulo} (#{self.intento_numero})"


class RespuestaUsuario(models.Model):
    intento = models.ForeignKey('IntentoEvaluacion', on_delete=models.CASCADE, related_name='respuestas', verbose_name="Intento")
    pregunta = models.ForeignKey('Pregunta', on_delete=models.CASCADE, related_name='respuestas_usuarios', verbose_name="Pregunta")
    opcion_seleccionada = models.ForeignKey('Opcion', on_delete=models.SET_NULL, null=True, blank=True, related_name='respuestas_usuarios', verbose_name="Opción seleccionada")
    es_correcta = models.BooleanField(default=False, verbose_name="Correcta")
    puntaje_obtenido = models.DecimalField(max_digits=6, decimal_places=2, default=0, verbose_name="Puntaje obtenido")

    class Meta:
        verbose_name = "Respuesta de Usuario"
        verbose_name_plural = "Respuestas de Usuarios"
        unique_together = ['intento', 'pregunta']

    def __str__(self):
        return f"{self.intento.usuario} - {self.pregunta.texto[:50]}"


class CursoExterno(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='cursos_externos', verbose_name="Usuario"
    )
    titulo = models.CharField(max_length=255, verbose_name="Título del curso")
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    institucion = models.CharField(max_length=255, blank=True, verbose_name="Institución / Plataforma")
    diploma = models.FileField(
        upload_to='diplomas/',
        null=True, blank=True,
        verbose_name="Diploma / Certificado"
    )
    fecha_diploma = models.DateField(verbose_name="Fecha del diploma")
    creado_en = models.DateTimeField(auto_now_add=True, verbose_name="Registrado el")

    class Meta:
        verbose_name = "Curso externo"
        verbose_name_plural = "Cursos externos"
        ordering = ['-fecha_diploma']

    def __str__(self):
        return f"{self.titulo} - {self.usuario}"
