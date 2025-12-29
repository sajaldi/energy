from django.db import models
from datetime import datetime, date, timedelta

from django.contrib.auth.models import User
from django.utils import timezone

class Categoria(models.Model):
    """
    Categoría jerárquica para clasificar rutinas de mantenimiento.
    Reemplaza el sistema anterior de Disciplina/SubDisciplina.
    """
    nombre = models.CharField(max_length=100)
    padre = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subcategorias')
    categoria_activo = models.OneToOneField('activos.Categoria', on_delete=models.SET_NULL, null=True, blank=True, related_name='mantenimiento_categoria', help_text="Vincular con una categoría de activo particular")
    descripcion = models.TextField(blank=True, null=True)
    
    def get_ruta_completa(self, separador=' → '):
        """
        Devuelve la ruta completa de la categoría en la jerarquía.
        Ej: 'Eléctrica → Subestaciones → Transformadores'
        """
        path = [self.nombre]
        curr = self.padre
        while curr:
            path.append(curr.nombre)
            curr = curr.padre
        return separador.join(reversed(path))
    
    def get_clave_unica(self):
        """Devuelve una clave única compuesta."""
        return self.get_ruta_completa(separador='|')

    def get_root(self):
        """Devuelve el nodo raíz de la jerarquía (Disciplina)."""
        curr = self
        while curr.padre:
            curr = curr.padre
        return curr

    def get_descendants(self, include_self=True):
        """Retorna un QuerySet con todos los descendientes."""
        descendants_ids = []
        if include_self:
            descendants_ids.append(self.id)
        
        def _get_children(parent):
            for child in parent.subcategorias.all():
                descendants_ids.append(child.id)
                _get_children(child)
        
        _get_children(self)
        return Categoria.objects.filter(id__in=descendants_ids)
    
    @property
    def ruta_completa(self):
        """Propiedad para acceso rápido a la ruta completa"""
        return self.get_ruta_completa()

    @property
    def level(self):
        """Calcula el nivel de profundidad (0 para raíz)."""
        count = 0
        curr = self.padre
        while curr:
            count += 1
            curr = curr.padre
        return count
    
    def __str__(self):
        return self.get_ruta_completa()
    
    class Meta:
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"

class Frecuencia(models.Model):
    nombre = models.CharField(max_length=100, unique=True, help_text="Ej: Diario, Semanal, Mensual")
    dias = models.PositiveIntegerField(help_text="Cantidad de días para el intervalo")

    def __str__(self):
        return f"{self.nombre} ({self.dias} días)"

    class Meta:
        verbose_name = "Frecuencia"
        verbose_name_plural = "Frecuencias"
        ordering = ['dias']

class Procedimiento(models.Model):
    nombre = models.CharField(max_length=200, unique=True)
    descripcion = models.TextField(blank=True, null=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Procedimiento"
        verbose_name_plural = "Procedimientos"

class PasoProcedimiento(models.Model):
    procedimiento = models.ForeignKey(Procedimiento, on_delete=models.CASCADE, related_name='pasos')
    orden = models.PositiveIntegerField(default=0)
    descripcion = models.TextField(help_text="Descripción de la tarea a realizar")
    verificacion = models.CharField(max_length=100, blank=True, null=True, help_text="¿Qué debe verificar el técnico?")
    
    class Meta:
        verbose_name = "Paso de Procedimiento"
        verbose_name_plural = "Pasos de Procedimiento"
        ordering = ['procedimiento', 'orden']

    def __str__(self):
        return f"{self.orden}. {self.descripcion[:50]}"

class Rutina(models.Model):
    nombre = models.CharField(max_length=200)
    categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True, blank=True, related_name='rutinas', 
                                  help_text="Clasificación de mantenimiento (ej: Mecánica, Eléctrica)")
    descripcion = models.TextField(blank=True, null=True)

    frecuencia = models.ForeignKey(Frecuencia, on_delete=models.SET_NULL, null=True, related_name='rutinas')
    
    # Tiempo de ejecución
    tiempo_estimado = models.DurationField(null=True, blank=True, help_text="Tiempo estimado para completar la rutina (ej: 02:00:00)")
    cantidad_tecnicos = models.IntegerField(default=1, help_text="Número de técnicos requeridos")
    procedimiento_estandar = models.ForeignKey(Procedimiento, on_delete=models.SET_NULL, null=True, blank=True, related_name='rutinas',
                                               help_text="Elija el manual de pasos a seguir")
    herramientas = models.TextField(blank=True, null=True, help_text="Herramientas y materiales necesarios")
    
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        """
        Auto-genera el nombre siguiendo el formato:
        ACTIVIDADES [Frecuencia] - [Categoría]
        """
        frec_name = self.frecuencia.nombre if self.frecuencia else "Sin Frecuencia"
        cat_name = self.categoria.nombre if self.categoria else "General"
        self.nombre = f"ACTIVIDADES {frec_name} - {cat_name}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Rutina"
        verbose_name_plural = "Rutinas"

class Horario(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True)

    def total_horas_semanales(self):
        total_seconds = 0
        for dia in self.dias.all():
            if dia.hora_inicio and dia.hora_fin:
                start = datetime.combine(date.min, dia.hora_inicio)
                end = datetime.combine(date.min, dia.hora_fin)
                diff = end - start
                total_seconds += diff.total_seconds()
        
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        return f"{hours}h {minutes}m"

    def resumen_corto(self):
        dias_abrev = {0: 'L', 1: 'M', 2: 'Mi', 3: 'J', 4: 'V', 5: 'S', 6: 'D'}
        dias = list(self.dias.all().order_by('dia'))
        if not dias: return "Sin horario"
        
        abrevs = [dias_abrev[d.dia] for d in dias]
        # Simplificación: tomar el horario del primer día
        p = dias[0]
        time_range = f"{p.hora_inicio.strftime('%H:%M')} - {p.hora_fin.strftime('%H:%M')}"
        return f"{','.join(abrevs)} {time_range}"

    def __str__(self):
        return f"{self.nombre} ({self.total_horas_semanales()})"

    class Meta:
        verbose_name = "Horario"
        verbose_name_plural = "Horarios"

class DiaHorario(models.Model):
    DIAS_SEMANA = [
        (0, 'Lunes'),
        (1, 'Martes'),
        (2, 'Miércoles'),
        (3, 'Jueves'),
        (4, 'Viernes'),
        (5, 'Sábado'),
        (6, 'Domingo'),
    ]
    
    horario = models.ForeignKey(Horario, on_delete=models.CASCADE, related_name='dias')
    dia = models.IntegerField(choices=DIAS_SEMANA)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()

    class Meta:
        verbose_name = "Día de Horario"
        verbose_name_plural = "Días de Horario"
        unique_together = ['horario', 'dia']
        ordering = ['dia', 'hora_inicio']

    def __str__(self):
        return f"{self.get_dia_display()}: {self.hora_inicio} - {self.hora_fin}"

class RestriccionCalendario(models.Model):
    fecha = models.DateField(unique=True, help_text="Fecha no laborable o restringida")
    motivo = models.CharField(max_length=200, help_text="Razón de la restricción (ej. Feriado, Vacaciones)")

    class Meta:
        verbose_name = "Restricción de Calendario"
        verbose_name_plural = "Restricciones de Calendario"
        ordering = ['fecha']

    def __str__(self):
        return f"{self.fecha} - {self.motivo}"

class PlanificacionMensual(models.Model):
    ESTADOS = [
        ('BORRADOR', 'Borrador'),
        ('APROBADO', 'Aprobado'),
        ('EJECUCION', 'En Ejecución'),
        ('CERRADO', 'Cerrado'),
    ]
    
    mes = models.PositiveIntegerField(choices=[(i, datetime(2000, i, 1).strftime('%B')) for i in range(1, 13)])
    anio = models.PositiveIntegerField(default=datetime.now().year)
    nombre = models.CharField(max_length=200, help_text="Ej: Mantenimiento Preventivo Enero 2024")
    estado = models.CharField(max_length=20, choices=ESTADOS, default='BORRADOR', db_index=True)
    responsable = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='planificaciones')
    notas = models.TextField(blank=True, null=True)
    
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Planificación Mensual"
        verbose_name_plural = "Planificaciones Mensuales"
        unique_together = ('mes', 'anio')

    def __str__(self):
        return f"{self.nombre} ({self.get_estado_display()})"

class Programacion(models.Model):
    rutina = models.ForeignKey(Rutina, on_delete=models.CASCADE, related_name='programaciones')
    horario = models.ForeignKey(Horario, on_delete=models.SET_NULL, null=True, related_name='programaciones')
    
    # Areas y Activos
    areas = models.ManyToManyField('activos.Ubicacion', blank=True, related_name='programaciones', help_text="Seleccione las áreas para filtrar los activos")
    activos = models.ManyToManyField('activos.Activo', blank=True, related_name='programaciones', help_text="Seleccione los activos específicos a programar")
    
    fecha_inicio = models.DateField(help_text="Fecha de inicio para la generación de órdenes")
    fecha_fin = models.DateField(blank=True, null=True, help_text="Opcional: Fecha límite (un año por defecto si está vacío)")
    procesada = models.BooleanField(default=False, help_text="Indica si ya se han generado las órdenes para esta programación")
    
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Programación"
        verbose_name_plural = "Programaciones"

    def __str__(self):
        return f"Prog: {self.rutina.nombre}"

    def generar_ordenes(self):
        """
        Genera órdenes de trabajo secuenciales expandiendo las áreas seleccionadas
        a todos sus niveles (descendientes) y buscando activos que coincidan con la
        categoría de la rutina. Crea una orden por cada activo encontrado.
        """
        if self.procesada:
            return 0
            
        from activos.models import Ubicacion, Activo
        
        limite = self.fecha_fin or (self.fecha_inicio + timedelta(days=365))
        restricciones = set(RestriccionCalendario.objects.values_list('fecha', flat=True))
        
        # 1. Expandir áreas a sus descendientes
        areas_iniciales = self.areas.all()
        if not areas_iniciales.exists() or not self.horario:
            return 0
            
        todas_las_areas = set()
        for area in areas_iniciales:
            descendientes = area.get_descendants(include_self=True)
            for d in descendientes:
                todas_las_areas.add(d)
        
        # Ordenar áreas jerárquicamente
        areas_a_programar = sorted(list(todas_las_areas), key=lambda x: (getattr(x, 'level', 0), getattr(x, 'orden', 0), getattr(x, 'nombre', '')))
            
        frecuencia_dias = self.rutina.frecuencia.dias
        tiempo_rutina = self.rutina.tiempo_estimado or timedelta(hours=1)
        
        # 2. Determinar categorías de activos aplicables base a la vinculación 1:1
        from activos.models import Categoria as CategoriaActivo
        cat_mantenimiento = self.rutina.categoria
        asset_cats = CategoriaActivo.objects.none()
        if cat_mantenimiento:
            # Buscamos categorías de activos vinculadas a esta categoría de mantenimiento o sus descendientes
            m_cats = cat_mantenimiento.get_descendants(include_self=True)
            asset_cats_ids = [c.categoria_activo_id for c in m_cats if c.categoria_activo_id]
            asset_cats = CategoriaActivo.objects.filter(id__in=asset_cats_ids)
            
        ordenes_creadas = 0
        
        fecha_ciclo = self.fecha_inicio
        while fecha_ciclo <= limite:
            # Inicializar el cursor global para este ciclo de mantenimiento
            # Esto serializa el trabajo a través de las áreas
            fecha_actual = fecha_ciclo
            cursor_dt = None
            
            for area in areas_a_programar:
                # 3. Buscar activos que coincidan con las categorías de activo vinculadas
                activos_pendientes = []
                if asset_cats.exists():
                    activos_pendientes = list(Activo.objects.filter(ubicacion=area, modelo__categoria__in=asset_cats))
                else:
                    # Si no hay categorías vinculadas, generamos una orden vacía para el área 
                    # si es que la rutina es genérica para el área
                    activos_pendientes = [None]


                while activos_pendientes:
                    # 1. Encontrar el siguiente día válido (laboral y sin restricciones)
                    # Loop de avance de días
                    while True:
                        if fecha_actual > limite:
                            activos_pendientes = [] # Romper loop externo
                            break
                            
                        # Chequear restricciones (feriados, etc)
                        if fecha_actual in restricciones:
                            fecha_actual += timedelta(days=1)
                            cursor_dt = None
                            continue
                            
                        # Chequear si hay horario para este día de la semana
                        horario_dia = self.horario.dias.filter(dia=fecha_actual.weekday()).first()
                        if not horario_dia:
                            fecha_actual += timedelta(days=1)
                            cursor_dt = None
                            continue
                        
                        # Si pasa todo, es un día válido
                        break
                    
                    if fecha_actual > limite:
                        break

                    # 2. Configurar tiempos del día (Timezone Aware)
                    try:
                        inicio_laboral = timezone.make_aware(datetime.combine(fecha_actual, horario_dia.hora_inicio))
                        fin_laboral = timezone.make_aware(datetime.combine(fecha_actual, horario_dia.hora_fin))
                    except ValueError:
                        inicio_laboral = datetime.combine(fecha_actual, horario_dia.hora_inicio)
                        fin_laboral = datetime.combine(fecha_actual, horario_dia.hora_fin)
                    
                    # 3. Determinar hora de inicio de trabajo (cursor vs inicio jornada)
                    ready_dt = max(cursor_dt, inicio_laboral) if cursor_dt else inicio_laboral
                    
                    # 4. Calcular capacidad restante
                    tiempo_disponible = fin_laboral - ready_dt
                    
                    # Si ya no queda tiempo (o el cursor se pasó), avanzar al siguiente día
                    if tiempo_disponible.total_seconds() <= 0:
                        fecha_actual += timedelta(days=1)
                        cursor_dt = None
                        continue
                        
                    max_activos = int(tiempo_disponible / tiempo_rutina)
                    
                    if max_activos <= 0:
                        # No cabe ni un activo completo, avanzar al siguiente día
                        fecha_actual += timedelta(days=1)
                        cursor_dt = None
                        continue

                    # 5. Tomar lote y Crear Orden
                    lote = activos_pendientes[:max_activos]
                    activos_pendientes = activos_pendientes[max_activos:]
                    
                    duracion_total = tiempo_rutina * len([a for a in lote if a is not None])
                    if duracion_total == timedelta(0): duracion_total = tiempo_rutina # Caso preventivo sin activos

                    ot = OrdenTrabajo.objects.create(
                        programacion=self,
                        ubicacion=area,
                        inicio_programado=ready_dt,
                        fin_programado=ready_dt + duracion_total,
                        rutina=self.rutina,
                        tipo='PREVENTIVA',
                        prioridad='MEDIA'
                    )
                    
                    activos_reales = [a for a in lote if a is not None]
                    if activos_reales:
                        ot.activos.set(activos_reales)
                    
                    # Avanzar el cursor intra-día
                    cursor_dt = ready_dt + duracion_total
                    ordenes_creadas += 1
            
            fecha_ciclo += timedelta(days=frecuencia_dias)
            
        self.procesada = True
        self.save()
        return ordenes_creadas

class Aviso(models.Model):
    PRIORIDAD_CHOICES = [
        ('BAJA', 'Baja'),
        ('MEDIA', 'Media'),
        ('ALTA', 'Alta'),
        ('CRITICA', 'Crítica'),
    ]
    
    ESTADO_CHOICES = [
        ('ABIERTO', 'Abierto'),
        ('PROCESO', 'En Proceso'),
        ('CERRADO', 'Cerrado'),
        ('CANCELADO', 'Cancelado'),
    ]

    activo = models.ForeignKey('activos.Activo', on_delete=models.SET_NULL, null=True, blank=True, related_name='avisos')
    ubicacion = models.ForeignKey('activos.Ubicacion', on_delete=models.CASCADE, related_name='avisos')
    descripcion = models.TextField(help_text="Descripción detallada de la falla o solicitud")
    prioridad = models.CharField(max_length=10, choices=PRIORIDAD_CHOICES, default='MEDIA', db_index=True)
    estado = models.CharField(max_length=10, choices=ESTADO_CHOICES, default='ABIERTO', db_index=True)
    
    solicitante = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='avisos_reportados')
    foto = models.ImageField(upload_to='avisos/', null=True, blank=True)
    
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"AV-{self.id}: {self.descripcion[:30]} ({self.estado})"

    class Meta:
        verbose_name = "Aviso"
        verbose_name_plural = "Avisos"
        ordering = ['-creado_en']

class OrdenTrabajo(models.Model):
    ESTADO_CHOICES = [
        ('PROGRAMADA', 'Programada'),
        ('EJECUCION', 'En Ejecución'),
        ('REALIZADA', 'Realizada'),
        ('CANCELADA', 'Cancelada'),
    ]

    TIPO_CHOICES = [
        ('PREVENTIVA', 'Preventiva'),
        ('CORRECTIVA', 'Correctiva'),
    ]
    
    PRIORIDAD_CHOICES = [
        ('BAJA', 'Baja'),
        ('MEDIA', 'Media'),
        ('ALTA', 'Alta'),
        ('CRITICA', 'Crítica'),
    ]
    
    tipo = models.CharField(max_length=15, choices=TIPO_CHOICES, default='PREVENTIVA', db_index=True)
    prioridad = models.CharField(max_length=10, choices=PRIORIDAD_CHOICES, default='MEDIA', db_index=True)
    rutina = models.ForeignKey(Rutina, on_delete=models.CASCADE, related_name='ordenes', null=True, blank=True)
    aviso = models.ForeignKey(Aviso, on_delete=models.SET_NULL, null=True, blank=True, related_name='ordenes')
    tecnico = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='ordenes_asignadas')
    
    ubicacion = models.ForeignKey('activos.Ubicacion', on_delete=models.CASCADE, related_name='ordenes_trabajo', null=True, blank=True)
    activos = models.ManyToManyField('activos.Activo', related_name='ordenes_trabajo', blank=True)
    programacion = models.ForeignKey(Programacion, on_delete=models.CASCADE, null=True, blank=True, related_name='ordenes')
    planificacion = models.ForeignKey(PlanificacionMensual, on_delete=models.SET_NULL, null=True, blank=True, related_name='ordenes', verbose_name="Plan Mensual")
    
    inicio_programado = models.DateTimeField(help_text="Fecha y hora de inicio prevista", db_index=True)
    fin_programado = models.DateTimeField(help_text="Fecha y hora de fin prevista")
    
    fecha_ejecucion = models.DateTimeField(null=True, blank=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='PROGRAMADA', db_index=True)
    
    notas = models.TextField(blank=True, null=True)
    
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Orden de Trabajo"
        verbose_name_plural = "Órdenes de Trabajo"
        ordering = ['inicio_programado', 'ubicacion']

    def __str__(self):
        nombre = self.rutina.nombre if self.rutina else (self.aviso.descripcion[:30] if self.aviso else "OT Correctiva")
        lugar = self.ubicacion.nombre if self.ubicacion else "S/U"
        return f"{self.tipo[:3]} OT-{self.id}: {nombre} - {lugar} ({self.inicio_programado.date()})"
