from django.db import models
from datetime import datetime, date, timedelta
from colorfield.fields import ColorField

from django.contrib.auth.models import User, Group
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

class PuestoTrabajo(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Puesto de Trabajo"
        verbose_name_plural = "Puestos de Trabajo"

class TecnicoPuesto(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil_tecnico')
    puesto = models.ForeignKey(PuestoTrabajo, on_delete=models.PROTECT, related_name='tecnicos')
    disponible = models.BooleanField(default=True)
    horas_semanales_max = models.DecimalField(max_length=5, max_digits=5, decimal_places=2, default=40.00, help_text="Capacidad máxima de horas por semana")

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.puesto}"

    class Meta:
        verbose_name = "Personal de Mantenimiento"
        verbose_name_plural = "Personal de Mantenimiento"

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
    TIPO_RESPUESTA_CHOICES = [
        ('INSTRUCCION', 'Instrucción (Solo lectura)'),
        ('CHECK', 'Check (Si/No/NA)'),
        ('NUMERICO', 'Valor Numérico'),
        ('TEXTO', 'Texto Libre'),
        ('MEDICION', 'Punto de Medición (SAP)'),
    ]
    
    procedimiento = models.ForeignKey(Procedimiento, on_delete=models.CASCADE, related_name='pasos')
    orden = models.PositiveIntegerField(default=0)
    descripcion = models.TextField(help_text="Descripción de la tarea a realizar")
    
    tipo_respuesta = models.CharField(max_length=20, choices=TIPO_RESPUESTA_CHOICES, default='INSTRUCCION')
    verificacion = models.CharField(max_length=100, blank=True, null=True, help_text="¿Qué debe verificar el técnico?")
    
    # Metadata para validación
    unidad_medida = models.CharField(max_length=20, blank=True, null=True, help_text="Ej: Bar, °C, Amperios")
    valor_objetivo = models.FloatField(blank=True, null=True, help_text="Valor ideal esperado")
    rango_min = models.FloatField(blank=True, null=True)
    rango_max = models.FloatField(blank=True, null=True)

    # Vinculación con Puntos de Medición
    punto_medicion_exacto = models.ForeignKey('activos.PuntoMedicion', on_delete=models.SET_NULL, null=True, blank=True, 
                                               related_name='pasos_procedimiento', help_text="Vincular a un punto específico (procedimientos detallados)")
    punto_medicion_codigo = models.CharField(max_length=50, blank=True, null=True, 
                                             help_text="Vincular por código (ej: 'NIVEL_ACEITE') para procedimientos genéricos")
    
    class Meta:
        verbose_name = "Paso de Procedimiento"
        verbose_name_plural = "Pasos de Procedimiento"
        ordering = ['procedimiento', 'orden']

    def __str__(self):
        return f"{self.orden}. {self.descripcion[:50]} ({self.get_tipo_respuesta_display()})"

class Rutina(models.Model):
    codigo_rutina = models.CharField(max_length=50, blank=True, null=True, unique=True, help_text="Código identificador de la rutina")
    nombre = models.CharField(max_length=200, blank=True, help_text="Deje vacío para generar un nombre automático basado en frecuencia y categoría")
    categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True, blank=True, related_name='rutinas', 
                                  help_text="Clasificación de mantenimiento (ej: Mecánica, Eléctrica)")
    descripcion = models.TextField(blank=True, null=True)

    frecuencia = models.ForeignKey(Frecuencia, on_delete=models.SET_NULL, null=True, related_name='rutinas')
    puesto_trabajo = models.ForeignKey(PuestoTrabajo, on_delete=models.SET_NULL, null=True, blank=True, related_name='rutinas',
                                      help_text="Puesto de trabajo responsable de esta rutina")
    
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
        Auto-genera el nombre solo si está vacío.
        Formato: ACTIVIDADES [Frecuencia] - [Categoría]
        """
        if not self.nombre:
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
    color = ColorField(default='#3b82f6', help_text="Color para identificar este horario en el cronograma")
    descripcion = models.TextField(blank=True, null=True)

    def total_horas_semanales(self):
        total_seconds = 0
        for dia in self.dias.all():
            if dia.hora_inicio and dia.hora_fin:
                start = datetime.combine(date.min, dia.hora_inicio)
                end = datetime.combine(date.min, dia.hora_fin)
                if end < start:
                    end += timedelta(days=1)
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

    def generar_ordenes(self, fecha_corte=None):
        """
        Genera órdenes de trabajo secuenciales expandiendo las áreas seleccionadas
        a todos sus niveles (descendientes) y buscando activos que coincidan con la
        categoría de la rutina. Crea una orden por cada activo encontrado.
        
        :param fecha_corte: (date/datetime) Si se especifica, genera solo hasta esta fecha (inclusive).
        """
        if self.procesada and not fecha_corte:
            return 0
            
        if self.fecha_inicio.year < 2000:
            # Evitar años erróneos como 0026
            return 0
            
        from activos.models import Ubicacion, Activo
        
        # Determinar fecha límite
        limite_natural = self.fecha_fin or (self.fecha_inicio + timedelta(days=365))
        if fecha_corte:
            # Asegurar que sea date
            if isinstance(fecha_corte, datetime):
                fecha_corte = fecha_corte.date()
            if isinstance(limite_natural, datetime):
                limite_natural = limite_natural.date()
                
            limite = min(limite_natural, fecha_corte)
        else:
            limite = limite_natural
            
        restricciones = set(RestriccionCalendario.objects.values_list('fecha', flat=True))
        
        # 1. Expandir áreas a sus descendientes
        areas_iniciales = self.areas.all()
        # Permitimos sin áreas si hay activos específicos o si hay categoría en la rutina (para el Wizard)
        if not self.horario:
            return 0
        
        has_criteria = areas_iniciales.exists() or self.activos.exists() or (self.rutina.categoria)
        if not has_criteria:
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
        
        # 2. Recopilar todos los activos a programar en el ciclo
        # Store as (activo, area_sugerida)
        items_a_procesar_config = [] 
        if self.activos.exists():
            for a in self.activos.all():
                items_a_procesar_config.append((a, a.ubicacion))
        else:
            from activos.models import Categoria as CategoriaActivo
            cat_mantenimiento = self.rutina.categoria
            asset_cats = CategoriaActivo.objects.none()
            if cat_mantenimiento:
                m_cats = cat_mantenimiento.get_descendants(include_self=True)
                asset_cats_ids = [c.categoria_activo_id for c in m_cats if c.categoria_activo_id]
                asset_cats = CategoriaActivo.objects.filter(id__in=asset_cats_ids)
            
            if areas_a_programar:
                for area in areas_a_programar:
                    if asset_cats.exists():
                        activos_en_area = list(Activo.objects.filter(ubicacion=area, modelo__categoria__in=asset_cats))
                        if activos_en_area:
                            for act in activos_en_area:
                                items_a_procesar_config.append((act, area))
                        else:
                            # Fallback: una orden para el área si es criterio de rutina
                            items_a_procesar_config.append((None, area))
                    else:
                        # Sin filtros de categoría, una orden por área
                        items_a_procesar_config.append((None, area))
            elif asset_cats.exists():
                # Caso solicitado: sin áreas pero con categoría de rutina
                for act in Activo.objects.filter(modelo__categoria__in=asset_cats):
                    items_a_procesar_config.append((act, act.ubicacion))
            
            # Si al final no hay nada, pero hay criterio, aseguramos al menos un item
            if not items_a_procesar_config:
                items_a_procesar_config = [(None, self.areas.first())]

        # 3. Preparación de asignación de técnicos (Round Robin + Capacidad Global)
        tecnicos_disponibles = []
        puesto = self.rutina.puesto_trabajo
        if puesto:
            tecnicos_disponibles = list(TecnicoPuesto.objects.filter(puesto=puesto, disponible=True).select_related('user'))
        
        # Track de carga por técnico y semana: {(perfil_id, anio_semana): horas_decimal}
        carga_trabajo = {}
        
        # Pre-cargar carga desde la DB si hay técnicos
        if tecnicos_disponibles:
            user_ids = [t.user_id for t in tecnicos_disponibles]
            
            # Convertir fechas a datetimes conscientes para la consulta exacta
            q_start = timezone.make_aware(datetime.combine(self.fecha_inicio, datetime.min.time()))
            q_end = timezone.make_aware(datetime.combine(limite, datetime.max.time()))

            # Solo buscamos OTs en el rango de fechas programado
            historico_ots = OrdenTrabajo.objects.filter(
                tecnico_id__in=user_ids,
                inicio_programado__gte=q_start,
                inicio_programado__lte=q_end
            ).values('tecnico_id', 'inicio_programado', 'fin_programado')
            
            # Mapear perfil a user para consistencia de llaves
            user_to_perfil = {t.user_id: t.id for t in tecnicos_disponibles}
            
            for ot in historico_ots:
                anio, semana, _ = ot['inicio_programado'].isocalendar()
                semana_key = f"{anio}-{semana}"
                duracion = (ot['fin_programado'] - ot['inicio_programado']).total_seconds() / 3600
                
                if ot['tecnico_id'] in user_to_perfil:
                    perfil_id = user_to_perfil[ot['tecnico_id']]
                    key = (perfil_id, semana_key)
                    carga_trabajo[key] = carga_trabajo.get(key, 0.0) + float(duracion)
            

        horas_rutina = self.rutina.tiempo_estimado.total_seconds() / 3600 if self.rutina.tiempo_estimado else 1.0

        tecnico_idx = 0
        ordenes_creadas = 0
        fecha_ciclo = self.fecha_inicio
        
        while fecha_ciclo <= limite:
            # Para cada ciclo, rastreamos las OTs creadas en este ciclo para agrupar por día+area+tecnico
            # Llave: (fecha_date, area_id, tecnico_id) -> OrdenTrabajo
            ots_en_ciclo = {} 

            # Para cada ciclo (ej: cada mes), reiniciamos el cursor temporal al inicio del día del ciclo
            fecha_actual_cursor = fecha_ciclo
            current_dt_cursor = None # Rastrea el final de la última OT programada en este ciclo
            
            for activo, area_sugerida in items_a_procesar_config:
                segundos_pendientes = tiempo_rutina.total_seconds()
                
                # Buscamos el slot para ESTE activo en particular
                ot_start_dt = None
                ot_end_dt = None
                
                while segundos_pendientes > 0:
                    if fecha_actual_cursor > limite: break # Seguridad
                    
                    # Chequear si es día laborable y no restringido
                    if fecha_actual_cursor in restricciones:
                        fecha_actual_cursor += timedelta(days=1)
                        current_dt_cursor = None
                        continue
                        
                    horario_dia = self.horario.dias.filter(dia=fecha_actual_cursor.weekday()).first()
                    if not horario_dia:
                        fecha_actual_cursor += timedelta(days=1)
                        current_dt_cursor = None
                        continue
                    
                    # Ventana laboral
                    try:
                        inicio_laboral = timezone.make_aware(datetime.combine(fecha_actual_cursor, horario_dia.hora_inicio))
                        fin_laboral = timezone.make_aware(datetime.combine(fecha_actual_cursor, horario_dia.hora_fin))
                        if fin_laboral < inicio_laboral:
                            fin_laboral += timedelta(days=1)
                    except (ValueError, TypeError):
                        inicio_laboral = datetime.combine(fecha_actual_cursor, horario_dia.hora_inicio)
                        fin_laboral = datetime.combine(fecha_actual_cursor, horario_dia.hora_fin)
                        if fin_laboral < inicio_laboral:
                            fin_laboral += timedelta(days=1)
                    
                    # Punto de entrada para este activo
                    entry_dt = max(current_dt_cursor, inicio_laboral) if current_dt_cursor else inicio_laboral
                    
                    if entry_dt >= fin_laboral:
                        # Si el cursor ya pasó el fin laboral de hoy, saltar a mañana
                        fecha_actual_cursor += timedelta(days=1)
                        current_dt_cursor = None
                        continue
                    
                    if not ot_start_dt: ot_start_dt = entry_dt
                    
                    segundos_disponibles = (fin_laboral - entry_dt).total_seconds()
                    
                    if segundos_pendientes <= segundos_disponibles:
                        ot_end_dt = entry_dt + timedelta(seconds=segundos_pendientes)
                        current_dt_cursor = ot_end_dt # El siguiente activo empieza donde termina este
                        segundos_pendientes = 0
                    else:
                        segundos_pendientes -= segundos_disponibles
                        fecha_actual_cursor += timedelta(days=1)
                        current_dt_cursor = None
                
                # Crear o Agrupar la orden para ESTE activo
                if ot_start_dt and ot_end_dt:
                    # Asignar técnico automáticamente respetando capacidad
                    tecnico_asignado = None
                    if tecnicos_disponibles:
                        anio, semana, _ = ot_start_dt.isocalendar()
                        semana_key = f"{anio}-{semana}"
                        for _ in range(len(tecnicos_disponibles)):
                            perfil = tecnicos_disponibles[tecnico_idx % len(tecnicos_disponibles)]
                            tecnico_idx += 1
                            key = (perfil.id, semana_key)
                            usado = carga_trabajo.get(key, 0.0)
                            if (usado + (segundos_pendientes/3600)) <= float(perfil.horas_semanales_max):
                                tecnico_asignado = perfil.user
                                carga_trabajo[key] = usado + horas_rutina
                                break
                    
                    main_ubi = area_sugerida or self.areas.first()
                    ot_key = (ot_start_dt.date(), main_ubi.id if main_ubi else None, tecnico_asignado.id if tecnico_asignado else None)
                    
                    if ot_key in ots_en_ciclo:
                        # AGRUPAR: Añadir a la orden existente en este día/área/técnico
                        existing_ot = ots_en_ciclo[ot_key]
                        if activo:
                            existing_ot.activos.add(activo)
                        # Actualizar fin si este activo termina más tarde (siempre será así por el cursor)
                        existing_ot.fin_programado = ot_end_dt
                        existing_ot.save()
                    else:
                        # NUEVA: Crear nueva orden
                        ot = OrdenTrabajo.objects.create(
                            programacion=self,
                            ubicacion=main_ubi,
                            inicio_programado=ot_start_dt,
                            fin_programado=ot_end_dt,
                            rutina=self.rutina,
                            tipo='PREVENTIVA',
                            prioridad='MEDIA',
                            estado='ESPERA',
                            tecnico=tecnico_asignado
                        )
                        if activo:
                            ot.activos.add(activo)
                        ots_en_ciclo[ot_key] = ot
                        ordenes_creadas += 1

            fecha_ciclo += timedelta(days=frecuencia_dias)
            
            
            
        self.procesada = True
        self.save()
        return ordenes_creadas

class Falla(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True, null=True)
    padre = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='hijos')
    puesto_trabajo = models.ForeignKey(PuestoTrabajo, on_delete=models.SET_NULL, null=True, blank=True, related_name='catalogo_fallas', help_text="Vincular a un puesto si es el nodo raíz")

    def get_ruta_completa(self, separador=' → '):
        path = [self.nombre]
        curr = self.padre
        while curr:
            path.append(curr.nombre)
            curr = curr.padre
        return separador.join(reversed(path))

    def __str__(self):
        return self.get_ruta_completa()

    class Meta:
        verbose_name = "Falla"
        verbose_name_plural = "Catálogo de Fallas"
        unique_together = ('nombre', 'padre')

class Aviso(models.Model):
    PRIORIDAD_CHOICES = [
        ('BAJA', 'Baja'),
        ('MEDIA', 'Media'),
        ('ALTA', 'Alta'),
        ('CRITICA', 'Crítica'),
    ]

    TIPO_CHOICES = [
        ('AVERIA', 'Avería / Falla (M2)'),
        ('SOLICITUD', 'Solicitud de Servicio (M1)'),
        ('MEJORA', 'Mejora / Modificación'),
        ('LEGAL', 'Requerimiento Legal / Seguridad'),
    ]
    
    ESTADO_CHOICES = [
        ('ABIERTO', 'Abierto'),
        ('PROCESO', 'En Proceso'),
        ('CERRADO', 'Cerrado'),
        ('CANCELADO', 'Cancelado'),
    ]

    activo = models.ForeignKey('activos.Activo', on_delete=models.SET_NULL, null=True, blank=True, related_name='avisos')
    ubicacion = models.ForeignKey('activos.Ubicacion', on_delete=models.CASCADE, related_name='avisos')
    falla = models.ForeignKey(Falla, on_delete=models.SET_NULL, null=True, blank=True, related_name='avisos')
    descripcion = models.TextField(help_text="Descripción detallada de la falla o solicitud")
    prioridad = models.CharField(max_length=10, choices=PRIORIDAD_CHOICES, default='MEDIA', db_index=True)
    tipo = models.CharField(max_length=15, choices=TIPO_CHOICES, default='SOLICITUD', db_index=True)
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

class FotoAviso(models.Model):
    aviso = models.ForeignKey(Aviso, on_delete=models.CASCADE, related_name='fotos')
    foto = models.ImageField(upload_to='avisos/fotos/')
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Foto de Aviso"
        verbose_name_plural = "Fotos de Aviso"

class NotificacionMantenimiento(models.Model):
    TIPO_CHOICES = [
        ('SUCCESS', 'Éxito'),
        ('ERROR', 'Error'),
        ('INFO', 'Información'),
        ('WARNING', 'Advertencia'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notificaciones_mantenimiento')
    mensaje = models.TextField()
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, default='INFO')
    leida = models.BooleanField(default=False, db_index=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Notificación de Mantenimiento"
        verbose_name_plural = "Notificaciones de Mantenimiento"
        ordering = ['-creado_en']

    def __str__(self):
        return f"{self.user.username} - {self.tipo}: {self.mensaje[:30]}..."

class OrdenTrabajo(models.Model):
    ESTADO_CHOICES = [
        ('ESPERA', 'En Espera de Programación'),
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
    
    codigo_de_orden = models.CharField(max_length=20, unique=True, blank=True, null=True, verbose_name="Código de Orden", db_index=True)
    
    tipo = models.CharField(max_length=15, choices=TIPO_CHOICES, default='PREVENTIVA', db_index=True)
    prioridad = models.CharField(max_length=10, choices=PRIORIDAD_CHOICES, default='MEDIA', db_index=True)
    rutina = models.ForeignKey(Rutina, on_delete=models.CASCADE, related_name='ordenes', null=True, blank=True)
    aviso = models.ForeignKey(Aviso, on_delete=models.SET_NULL, null=True, blank=True, related_name='ordenes')
    tecnico = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='ordenes_asignadas', help_text="Técnico específico asignado")
    equipo = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True, blank=True, related_name='ordenes_equipo', help_text="Equipo o Grupo de trabajo asignado")
    
    ubicacion = models.ForeignKey('activos.Ubicacion', on_delete=models.CASCADE, related_name='ordenes_trabajo', null=True, blank=True)
    activos = models.ManyToManyField('activos.Activo', related_name='ordenes_trabajo', blank=True)
    programacion = models.ForeignKey(Programacion, on_delete=models.CASCADE, null=True, blank=True, related_name='ordenes')
    falla = models.ForeignKey(Falla, on_delete=models.SET_NULL, null=True, blank=True, related_name='ordenes_trabajo')
    planificacion = models.ForeignKey(PlanificacionMensual, on_delete=models.SET_NULL, null=True, blank=True, related_name='ordenes', verbose_name="Plan Mensual")
    
    inicio_programado = models.DateTimeField(help_text="Fecha y hora de inicio prevista", db_index=True)
    fin_programado = models.DateTimeField(help_text="Fecha y hora de fin prevista")
    
    fecha_ejecucion = models.DateTimeField(null=True, blank=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='ESPERA', db_index=True)
    
    notas = models.TextField(blank=True, null=True)
    
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        """
        Garantiza que la orden tenga un código único.
        Si no viene en el import, usa OT-000000ID.
        """
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        if not self.codigo_de_orden:
            self.codigo_de_orden = f"OT-{str(self.id).zfill(9)}"
            # Update single field to avoid recursion and update only what's necessary
            OrdenTrabajo.objects.filter(pk=self.pk).update(codigo_de_orden=self.codigo_de_orden)

    class Meta:
        verbose_name = "Orden de Trabajo"
        verbose_name_plural = "Órdenes de Trabajo"
        ordering = ['inicio_programado', 'ubicacion']

    def __str__(self):
        nombre = self.rutina.nombre if self.rutina else (self.aviso.descripcion[:30] if self.aviso else "OT Correctiva")
        lugar = self.ubicacion.nombre if self.ubicacion else "S/U"
        return f"{self.tipo[:3]} {self.codigo_de_orden or 'OT-TEMP'}: {nombre} - {lugar} ({self.inicio_programado.date()})"

class CierreOrdenTrabajo(models.Model):
    orden_trabajo = models.OneToOneField(OrdenTrabajo, on_delete=models.CASCADE, related_name='cierre', verbose_name="Orden de Trabajo")
    tecnico = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='cierres_ot', verbose_name="Técnico Responsable")
    
    fecha_inicio_real = models.DateTimeField(verbose_name="Inicio Real")
    fecha_fin_real = models.DateTimeField(verbose_name="Fin Real")
    horas_hombre = models.FloatField(default=0, help_text="Total de Horas-Hombre (HH) consumidas", verbose_name="HH Totales")
    
    comentarios = models.TextField(blank=True, null=True, verbose_name="Comentarios Técnicos / Hallazgos")
    
    materiales_utilizados = models.TextField(blank=True, null=True, help_text="Listado de materiales o repuestos utilizados")
    
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cierre de Orden de Trabajo"
        verbose_name_plural = "Cierres de Órdenes de Trabajo"

    def __str__(self):
        return f"Cierre {self.orden_trabajo.codigo_de_orden or self.orden_trabajo.id}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Al guardar el cierre, la orden debe pasar a REALIZADA
        if self.orden_trabajo.estado != 'REALIZADA':
            self.orden_trabajo.estado = 'REALIZADA'
            self.orden_trabajo.fecha_ejecucion = self.fecha_fin_real
            self.orden_trabajo.save(update_fields=['estado', 'fecha_ejecucion'])
class ValorPasoOrden(models.Model):
    """
    Almacena el resultado/valor capturado para un paso específico de una OT.
    """
    orden_trabajo = models.ForeignKey(OrdenTrabajo, on_delete=models.CASCADE, related_name='resultados_checklist')
    paso = models.ForeignKey(PasoProcedimiento, on_delete=models.CASCADE)
    
    valor_texto = models.TextField(blank=True, null=True)
    valor_numerico = models.FloatField(blank=True, null=True)
    valor_bool = models.BooleanField(null=True, blank=True, help_text="Para tipos CHECK")
    no_aplica = models.BooleanField(default=False)
    
    comentarios = models.TextField(blank=True, null=True, help_text="Comentarios adicionales del técnico para este paso")
    capturado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Valor de Checklist"
        verbose_name_plural = "Valores de Checklist"
        unique_together = ('orden_trabajo', 'paso')

    def __str__(self):
        return f"OT-{self.orden_trabajo_id} - {self.paso}"
