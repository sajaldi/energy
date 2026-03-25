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
    cierre_enviado = models.BooleanField(default=False, verbose_name="Cierre Notificado", db_index=True)

    # Vinculación con Activos (Energía)
    activo = models.ForeignKey('activos.Activo', on_delete=models.SET_NULL, null=True, blank=True, related_name='tickets', verbose_name="Activo Relacionado")
    ubicacion = models.ForeignKey('activos.Ubicacion', on_delete=models.SET_NULL, null=True, blank=True, related_name='tickets', verbose_name="Ubicación Física")

    # Auditoría Interna
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

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
