from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from pgvector.django import VectorField, CosineDistance
import logging

logger = logging.getLogger(__name__)

class SolicitudTicket(models.Model):
    # Identificadores
    id_solicitud = models.BigIntegerField(unique=True, verbose_name="ID Solicitud Servicio")
    folio = models.CharField(max_length=100, blank=True, null=True, verbose_name="Folio", db_index=True)
    
    # Personas
    solicitante = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    responsable = models.CharField(max_length=255, blank=True, null=True, verbose_name="Responsable de Atención")
    
    # Descripciones
    solicitud_descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción Solicitud")
    falla_descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción Falla")
    falla_clasificacion = models.CharField(max_length=255, blank=True, null=True, verbose_name="Clasificación Falla")
    
    # Clasificación Jerárquica
    servicio = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    subservicio = models.CharField(max_length=255, blank=True, null=True)
    unidad = models.CharField(max_length=255, blank=True, null=True)
    area = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    grupo = models.CharField(max_length=255, blank=True, null=True)
    nivel = models.CharField(max_length=255, blank=True, null=True)
    
    # Fechas
    fecha_solicitud = models.DateTimeField(blank=True, null=True, verbose_name="Fecha Solicitud", db_index=True)
    tipo_recepcion = models.CharField(max_length=100, blank=True, null=True, verbose_name="Tipo Recepción")
    fecha_tipo_recepcion = models.DateTimeField(blank=True, null=True, verbose_name="Fecha Tipo Recepción")
    fecha_suspension = models.DateTimeField(blank=True, null=True, verbose_name="Fecha Suspensión")
    fecha_cierre = models.DateTimeField(blank=True, null=True, verbose_name="Fecha Cierre")
    
    # Atributos de Servicio
    tipo_solicitud = models.CharField(max_length=100, blank=True, null=True, verbose_name="Tipo Solicitud")
    tiempo_tipo = models.CharField(max_length=100, blank=True, null=True, verbose_name="Tiempo Tipo")
    
    # Seguimiento Técnico
    fecha_diagnostico = models.DateTimeField(blank=True, null=True, verbose_name="Fecha/Hora Diagnóstico")
    diagnostico = models.TextField(blank=True, null=True, verbose_name="Diagnóstico")
    
    fecha_actividades = models.DateTimeField(blank=True, null=True, verbose_name="Fecha/Hora Actividades")
    actividades = models.TextField(blank=True, null=True, verbose_name="Actividades")
    
    fecha_observaciones = models.DateTimeField(blank=True, null=True, verbose_name="Fecha/Hora Observaciones")
    observaciones = models.TextField(blank=True, null=True, verbose_name="Observaciones")
    
    fecha_observaciones_usuario = models.DateTimeField(blank=True, null=True, verbose_name="Fecha/Hora Obs. Usuario")
    observaciones_usuario = models.TextField(blank=True, null=True, verbose_name="Observaciones Usuario")
    
    # Clasificación de Falla Final
    clasificacion_falla_final = models.CharField(max_length=255, blank=True, null=True, verbose_name="Clasificación Falla Final")
    categoria_falla = models.CharField(max_length=255, blank=True, null=True, verbose_name="Categoría Falla")
    
    # Búsqueda Vectorial Semántica
    embedding = VectorField(dimensions=1024, null=True, blank=True)

    # Estado de Notificación
    cierre_enviado = models.BooleanField(default=False, verbose_name="Cierre Notificado", db_index=True, null=True, blank=True)
    correo_cierre = models.BooleanField(
        default=False, 
        verbose_name="Correo de Cierre Enviado", 
        db_index=True,
        null=True, 
        blank=True,
        help_text="Se marca automáticamente cuando Power Automate confirma el envío del correo de cierre"
    )

    # Vinculación con Activos (Energía)
    activo = models.ForeignKey('activos.Activo', on_delete=models.SET_NULL, null=True, blank=True, related_name='tickets', verbose_name="Activo Relacionado")
    ubicacion = models.ForeignKey('activos.Ubicacion', on_delete=models.SET_NULL, null=True, blank=True, related_name='tickets', verbose_name="Ubicación Física")

    # Usuario asignado para resolver
    usuario_responsable = models.ForeignKey(
        'auth.User', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='tickets_responsable',
        verbose_name="Usuario Responsable"
    )

    # Auditoría Interna
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    # Información Financiera / Deductivas
    deductiva = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0.00, 
        verbose_name="Deductiva (USD)", 
        blank=True, 
        null=True,
        help_text="Monto de la deductiva en USD"
    )
    proveedor_deductiva = models.ForeignKey(
        'mantenimiento.Empresa', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='deductivas_callcenter', 
        verbose_name="Proveedor de Deductiva"
    )

    def __str__(self):
        return f"{self.folio or self.id_solicitud} - {self.solicitante}"

    class Meta:
        verbose_name = "Solicitud de Ticket"
        verbose_name_plural = "Solicitudes de Tickets"
        ordering = ['-fecha_solicitud']

    @classmethod
    def buscar_vectorial(cls, query_embedding, limit=10):
        """
        Búsqueda semántica de tickets usando distancia coseno.
        Recibe un vector de embedding (list[float]) y retorna los tickets más similares.
        """
        return cls.objects.exclude(
            embedding__isnull=True
        ).annotate(
            distancia=CosineDistance('embedding', query_embedding)
        ).order_by('distancia')[:limit]


class GrupoTicket(models.Model):
    """
    Agrupa múltiples tickets de Call Center bajo un mismo correlativo y descripción.
    Relación muchos a muchos.
    """
    correlativo = models.CharField(
        max_length=20, 
        unique=True, 
        editable=False, 
        verbose_name="Correlativo"
    )
    fecha = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    descripcion = models.TextField(verbose_name="Descripción del Grupo")
    
    tickets = models.ManyToManyField(
        SolicitudTicket, 
        related_name="grupos", 
        verbose_name="Tickets"
    )

    def save(self, *args, **kwargs):
        if not self.correlativo:
            # Obtener el último número y sumar 1
            last_group = GrupoTicket.objects.all().order_by('id').last()
            if not last_group:
                new_id = 1
            else:
                new_id = last_group.id + 1
            self.correlativo = f"GT-{new_id:04d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.correlativo} - {self.descripcion[:30]}..."

    class Meta:
        verbose_name = "Grupo de Ticket"
        verbose_name_plural = "Grupos de Tickets"
        ordering = ['-fecha']


class EvidenciaTicket(models.Model):
    """
    Repositorio de imágenes, fotos o documentos adjuntos para un ticket específico.
    """
    ticket = models.ForeignKey(
        SolicitudTicket, 
        on_delete=models.CASCADE, 
        related_name='evidencias',
        verbose_name="Ticket"
    )
    archivo = models.FileField(
        upload_to='callcenter/evidencias/%Y/%m/%d/', 
        verbose_name="Archivo/Foto"
    )
    descripcion = models.CharField(
        max_length=255, 
        blank=True, 
        null=True, 
        verbose_name="Descripción Corta"
    )
    fecha_carga = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Evidencia de {self.ticket.folio or self.ticket.id_solicitud}"

    class Meta:
        verbose_name = "Evidencia de Ticket"
        verbose_name_plural = "Evidencias de tickets"


class Institucion(models.Model):
    """
    Representa una institución externa (ej. SAR, BANX, etc.)
    que solicita extensiones de tiempo o soluciones provisionales.
    """
    nombre = models.CharField(max_length=255, verbose_name="Nombre de la Institución")
    acronimo = models.CharField(max_length=20, verbose_name="Acrónimo", blank=True, null=True, help_text="Ej: SAR, BANX, etc.")
    ubicaciones = models.ManyToManyField(
        'activos.Ubicacion', 
        related_name='instituciones', 
        verbose_name="Ubicaciones de la Institución",
        blank=True,
        help_text="Una institución puede tener una o más ubicaciones físicas."
    )

    def __str__(self):
        if self.acronimo:
            return f"{self.nombre} ({self.acronimo})"
        return self.nombre

    class Meta:
        verbose_name = "Institución"
        verbose_name_plural = "Instituciones"
        ordering = ['nombre']


class Enlace(models.Model):
    """
    Persona de contacto en una institución para el seguimiento de tickets.
    """
    nombre = models.CharField(max_length=255, verbose_name="Nombre Completo")
    email = models.EmailField(blank=True, null=True, verbose_name="Correo Electrónico")
    telefono = models.CharField(max_length=50, blank=True, null=True, verbose_name="Teléfono / WhatsApp")
    institucion = models.ForeignKey(
        Institucion, 
        on_delete=models.CASCADE, 
        related_name='enlaces', 
        verbose_name="Institución"
    )
    ubicacion = models.ForeignKey(
        'activos.Ubicacion', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='enlaces', 
        verbose_name="Ubicación por Defecto"
    )

    def __str__(self):
        return f"{self.nombre} ({self.institucion.nombre})"

    class Meta:
        verbose_name = "Enlace / Contacto"
        verbose_name_plural = "Enlaces de Instituciones"
        ordering = ['nombre']


class TiempoAcordado(models.Model):
    """
    Acuerdo de extensión de tiempo superando la holgura permitida.
    Incluye cronograma de tareas para vista Gantt/Timeline.
    """
    ESTATUS_CHOICES = [
        ('BORRADOR', 'Borrador'),
        ('PENDIENTE', 'Pendiente de Aprobación'),
        ('APROBADO', 'Aprobado / En Proceso'),
        ('VENCIDO', 'Vencido'),
        ('FINALIZADO', 'Finalizado'),
    ]

    ticket = models.ForeignKey(
        SolicitudTicket, 
        on_delete=models.CASCADE, 
        related_name='tiempos_acordados', 
        verbose_name="Ticket Relacionado"
    )
    enlace = models.ForeignKey(
        Enlace, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='tiempos_acordados', 
        verbose_name="Enlace Solicitante"
    )
    
    # Campos por defecto desde el enlace (pueden ser modificados)
    ubicacion = models.ForeignKey(
        'activos.Ubicacion', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name="Ubicación del Reporte"
    )
    institucion = models.ForeignKey(
        Institucion, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="Institución"
    )

    motivo_extension = models.TextField(verbose_name="Motivo del Tiempo Acordado")
    solucion_provisional = models.TextField(verbose_name="Solución Provisional Acordada")
    observaciones = models.TextField(blank=True, null=True, verbose_name="Observaciones Adicionales")
    
    fecha_solucion_final = models.DateTimeField(verbose_name="Fecha Solución Final Comprometida")
    
    estatus = models.CharField(
        max_length=20, 
        choices=ESTATUS_CHOICES, 
        default='BORRADOR',
        verbose_name="Estado del Acuerdo"
    )

    enviado = models.BooleanField(
        default=False, 
        verbose_name="¿Enviado por Correo?",
        help_text="Indica si el reporte PDF ya fue enviado a través del flujo de Power Automate."
    )

    # Firma Digital (Almacenada en Base64)
    firma_enlace = models.TextField(blank=True, null=True, verbose_name="Firma del Enlace")
    firma_responsable = models.TextField(blank=True, null=True, verbose_name="Firma del Responsable")

    # Auditoría y Filtrado
    usuario_creador = models.ForeignKey(
        'auth.User', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='acuerdos_creados'
    )
    departamento = models.ForeignKey(
        'core.Departamento', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='acuerdos_departamento'
    )

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Lógica de defaults si no se especifican
        if self.enlace:
            if not self.institucion:
                self.institucion = self.enlace.institucion
            if not self.ubicacion:
                self.ubicacion = self.enlace.ubicacion
        
        # Asignar departamento del creador si no está
        if self.usuario_creador and not self.departamento:
            try:
                self.departamento = self.usuario_creador.perfil.departamento
            except:
                pass
                
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Acuerdo: {self.ticket.folio or self.ticket.id_solicitud} - {self.estatus}"

    class Meta:
        verbose_name = "Tiempo Acordado"
        verbose_name_plural = "Tiempos Acordados"
        ordering = ['-fecha_solucion_final']


class TiempoAcordadoTarea(models.Model):
    """
    Tareas específicas dentro de un tiempo acordado para generar el cronograma.
    """
    tiempo_acordado = models.ForeignKey(
        TiempoAcordado, 
        on_delete=models.CASCADE, 
        related_name='tareas', 
        verbose_name="Acuerdo"
    )
    descripcion = models.CharField(max_length=255, verbose_name="Actividad / Tarea")
    fecha_inicio = models.DateTimeField(verbose_name="Fecha de Inicio")
    fecha_fin = models.DateTimeField(verbose_name="Fecha Final")
    
    completada = models.BooleanField(default=False, verbose_name="¿Completada?")

    def __str__(self):
        return f"{self.descripcion} ({self.tiempo_acordado.id})"

    class Meta:
        verbose_name = "Tarea de Cronograma"
        verbose_name_plural = "Tareas de Cronogramas"
        ordering = ['fecha_inicio']


class RestriccionAcceso(models.Model):
    ticket = models.OneToOneField(
        SolicitudTicket, 
        on_delete=models.CASCADE, 
        related_name='restriccion_acceso',
        verbose_name="Ticket Relacionado"
    )
    folio_ra = models.CharField(
        max_length=50, 
        unique=True, 
        verbose_name="Folio RA"
    )
    fecha_restriccion = models.DateTimeField(verbose_name="Fecha y Hora de Restricción")
    fecha_reprogramacion = models.DateTimeField(verbose_name="Fecha y Hora de Reprogramación")
    horas_restriccion = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        verbose_name="Horas de Restricción"
    )
    firma_usuario = models.TextField(blank=True, null=True, verbose_name="Firma del Usuario")
    firma_tecnico = models.TextField(blank=True, null=True, verbose_name="Firma del Técnico")
    
    usuario_creador = models.ForeignKey(
        'auth.User', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='restricciones_creadas'
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.folio_ra} - Ticket: {self.ticket.folio or self.ticket.id_solicitud}"

    class Meta:
        verbose_name = "Restricción de Acceso"
        verbose_name_plural = "Restricciones de Acceso"


# --- Señales ---
@receiver(post_save, sender=SolicitudTicket)
def trigger_vectorize_ticket(sender, instance, **kwargs):
    """
    Cuando se guarda un ticket sin embedding, envía a n8n para vectorización.
    """
    if instance.embedding is None:
        try:
            from .tasks import vectorize_ticket_n8n
            vectorize_ticket_n8n.delay(instance.id)
        except Exception as e:
            logger.warning(f"No se pudo encolar vectorización para ticket {instance.id}: {e}")


# --- MODELOS DE CRONOGRAMAS PREDEFINIDOS (PLANTILLAS) ---

class CronogramaPredefinido(models.Model):
    """
    Plantilla de cronograma para reutilizar en acuerdos de tiempo.
    """
    nombre = models.CharField(max_length=255, verbose_name="Nombre del Cronograma")
    departamento = models.ForeignKey(
        'core.Departamento', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='cronogramas_predefinidos',
        verbose_name="Departamento / Área"
    )

    def __str__(self):
        if self.departamento:
            return f"{self.nombre} [{self.departamento.nombre}]"
        return self.nombre

    class Meta:
        verbose_name = "Cronograma Predefinido"
        verbose_name_plural = "Cronogramas Predefinidos"
        ordering = ['nombre']


class CronogramaItemPredefinido(models.Model):
    """
    Actividad individual dentro de una plantilla de cronograma.
    """
    cronograma = models.ForeignKey(
        CronogramaPredefinido, 
        on_delete=models.CASCADE, 
        related_name='items', 
        verbose_name="Cronograma"
    )
    numero = models.PositiveIntegerField(verbose_name="N°")
    descripcion = models.CharField(max_length=255, verbose_name="Descripción de la Tarea")
    duracion_dias = models.PositiveIntegerField(verbose_name="Duración (Días)", default=1)
    
    predecesores = models.ManyToManyField(
        'self', 
        blank=True, 
        symmetrical=False, 
        related_name='sucesores',
        verbose_name="Predecesores"
    )

    def __str__(self):
        return f"{self.numero}. {self.descripcion}"

    class Meta:
        verbose_name = "Item de Cronograma"
        verbose_name_plural = "Items de Cronograma"
        ordering = ['numero']
