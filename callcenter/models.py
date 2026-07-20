from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from pgvector.django import VectorField, CosineDistance
import logging
from webpush import send_user_notification

logger = logging.getLogger(__name__)

class SolicitudTicket(models.Model):
    # Identificadores
    id_solicitud = models.BigIntegerField(unique=True, verbose_name="ID Solicitud Servicio")
    folio = models.CharField(max_length=100, blank=True, null=True, verbose_name="Folio", db_index=True)
    es_interno = models.BooleanField(default=False, verbose_name="Es Ticket Interno", db_index=True)
    solicitud_adicional = models.BooleanField(default=False, verbose_name="Solicitud Adicional", db_index=True)
    
    # Personas
    solicitante = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    enlace_solicitante = models.ForeignKey(
        'Enlace',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tickets',
        verbose_name="Enlace Solicitante"
    )
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
    
    comentarios_internos = models.TextField(blank=True, null=True, verbose_name="Comentarios Internos")
    
    # Clasificación de Falla Final
    clasificacion_falla_final = models.CharField(max_length=255, blank=True, null=True, verbose_name="Clasificación Falla Final")
    categoria_falla = models.CharField(max_length=255, blank=True, null=True, verbose_name="Categoría Falla")
    
    # Búsqueda Vectorial Semántica
    embedding = VectorField(dimensions=1024, null=True, blank=True)

    # Catálogo de Falla (NUEVO)
    falla_reportada = models.ForeignKey(
        'FallaTicket', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='tickets',
        verbose_name="Falla del Catálogo"
    )

    # Catálogo de Diagnóstico (NUEVO)
    diagnostico_reportado = models.ForeignKey(
        'DiagnosticoTicket', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='tickets',
        verbose_name="Diagnóstico del Catálogo"
    )

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

    # Estado y Logs de Automatización (Robot Playwright)
    robot_estatus = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        verbose_name="Estatus de Automatización",
        help_text="Indica si el ticket fue documentado completa o parcialmente."
    )
    robot_log = models.TextField(
        blank=True, 
        null=True, 
        verbose_name="Log de Automatización",
        help_text="Historial detallado del proceso de guardado y carga de evidencias en SIG GIA."
    )

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

    @property
    def id_unlocalized(self):
        """Retorna el ID como string sin separadores de miles."""
        return str(self.id)

    @property
    def ubicacion_jerarquica(self):
        """
        Retorna la ruta completa de la ubicación.
        Si está vinculado a Ubicacion (activos), usa su ruta.
        Si no, concatena Area > Nivel > Grupo > Unidad.
        """
        if self.ubicacion:
            return self.ubicacion.ruta_completa
            
        parts = []
        if self.area: parts.append(self.area)
        if self.nivel: parts.append(self.nivel)
        if self.grupo: parts.append(self.grupo)
        if self.unidad: parts.append(self.unidad)
        
        return " > ".join(parts) if parts else "-"

    @property
    def tiempo_resolucion_horas(self):
        """
        Calcula el tiempo de resolución en horas si el ticket está cerrado.
        """
        if self.fecha_cierre and self.fecha_solicitud:
            diff = (self.fecha_cierre - self.fecha_solicitud).total_seconds() / 3600.0
            return round(diff, 2) if diff >= 0 else None
        return None

    @classmethod
    def buscar_vectorial(cls, query_embedding, limit=10, filters=None):
        """
        Búsqueda semántica de tickets usando distancia coseno.
        Permite aplicar filtros adicionales (ej: por ubicación).
        """
        qs = cls.objects.exclude(embedding__isnull=True)
        
        if filters:
            qs = qs.filter(**filters)
            
        return qs.annotate(
            distancia=CosineDistance('embedding', query_embedding)
        ).order_by('distancia')[:limit]

    def _resolve_enlace(self):
        """
        Auto-resuelve enlace_solicitante comparando el texto de solicitante
        con los nombres de Enlace existentes.
        """
        if not self.solicitante or self.enlace_solicitante:
            return

        from .models import Enlace
        from django.db.models import Q

        name = self.solicitante.strip().lower()
        # Quitar prefijos comunes (Ing., Lic., Dr., etc.)
        for prefix in ['ing. ', 'lic. ', 'dr. ', 'dra. ', 'arq. ', 'mba. ', 'mc. ']:
            if name.startswith(prefix):
                name = name[len(prefix):]
                break

        parts = name.split()
        if not parts:
            return

        # 1. Buscar coincidencia exacta con nombre + apellidos
        enlace = Enlace.objects.filter(
            Q(nombre__iexact=parts[0]) &
            Q(primer_apellido__iexact=parts[1]) if len(parts) > 1 else Q()
        ).first()

        if not enlace and len(parts) >= 2:
            # 2. Buscar solo nombre + primer apellido (ignorar segundo)
            enlace = Enlace.objects.filter(
                nombre__iexact=parts[0],
                primer_apellido__iexact=parts[1]
            ).first()

        if not enlace and len(parts) >= 1:
            # 3. Buscar solo por nombre
            enlace = Enlace.objects.filter(nombre__iexact=parts[0]).first()

        if enlace:
            self.enlace_solicitante = enlace
            return

        # 4. No se encontró ningún Enlace → crearlo automáticamente
        parts_list = self.solicitante.strip().split(maxsplit=2)
        nom = parts_list[0] if parts_list else self.solicitante.strip()
        ap1 = parts_list[1] if len(parts_list) > 1 else ''
        ap2 = parts_list[2] if len(parts_list) > 2 else ''

        from .models import Institucion
        inst = Institucion.objects.first()
        if not inst:
            inst = Institucion.objects.create(nombre='Sin Institución')

        enlace = Enlace.objects.create(
            nombre=nom,
            primer_apellido=ap1,
            segundo_apellido=ap2,
            institucion=inst,
        )
        self.enlace_solicitante = enlace

    def save(self, *args, **kwargs):
        self._resolve_enlace()
        super().save(*args, **kwargs)


class GrupoTicket(models.Model):
    """
    Agrupa múltiples tickets de Call Center bajo un mismo correlativo y descripción.
    Relación muchos a muchos.
    """
    correlativo = models.CharField(
        max_length=255, 
        unique=True, 
        verbose_name="Número de Grupo / Cluster"
    )
    fecha = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    departamento = models.ForeignKey(
        'core.Departamento', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="Departamento Responsable",
        related_name="clusters"
    )
    usuario_creador = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='clusters_creados',
        verbose_name="Creado por"
    )
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
    descripcion_ia = models.TextField(
        blank=True, 
        null=True, 
        verbose_name="Análisis de IA (Visual)"
    )
    analizada = models.BooleanField(
        default=False, 
        null=True,
        verbose_name="Analizada por IA"
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
    GENERO_CHOICES = [
        ('M', 'Masculino'),
        ('F', 'Femenino'),
        ('OTRO', 'Otro'),
    ]

    nombre = models.CharField(max_length=255, verbose_name="Nombres")
    primer_apellido = models.CharField(max_length=255, blank=True, null=True, verbose_name="1er Apellido")
    segundo_apellido = models.CharField(max_length=255, blank=True, null=True, verbose_name="2do Apellido")
    email = models.EmailField(blank=True, null=True, verbose_name="Correo Principal")
    correo_secundario = models.EmailField(blank=True, null=True, verbose_name="Correo Secundario")
    telefono = models.CharField(max_length=50, blank=True, null=True, verbose_name="Teléfono 1")
    telefono_2 = models.CharField(max_length=50, blank=True, null=True, verbose_name="Teléfono 2")
    extension_ccg = models.CharField(max_length=20, blank=True, null=True, verbose_name="Extensión CCG")
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
        verbose_name="Ubicación"
    )
    nivel_referencia = models.CharField(max_length=255, blank=True, null=True, verbose_name="Nivel de Referencia",
                                        help_text="Manual / Nivel jerárquico dentro de la institución")
    nombre_sig = models.CharField(max_length=100, blank=True, null=True, verbose_name="Nombre SIG")
    usuario_sig = models.CharField(max_length=100, blank=True, null=True, verbose_name="Usuario SIG")
    pin_sig = models.IntegerField(blank=True, null=True, verbose_name="PIN SIG")
    genero = models.CharField(max_length=10, choices=GENERO_CHOICES, blank=True, null=True, verbose_name="Género")
    contrasena_sig = models.CharField(max_length=255, blank=True, null=True, verbose_name="Contraseña SIG")
    oficio_alta = models.ForeignKey(
        'documentos.Documento',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='enlaces_oficio_alta',
        verbose_name="Oficio de Alta"
    )
    fecha_alta = models.DateField(blank=True, null=True, verbose_name="Fecha de Alta")
    oficio_baja = models.ForeignKey(
        'documentos.Documento',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='enlaces_oficio_baja',
        verbose_name="Oficio de Baja"
    )

    def __str__(self):
        parts = [self.nombre]
        if self.primer_apellido:
            parts.append(self.primer_apellido)
        if self.segundo_apellido:
            parts.append(self.segundo_apellido)
        nombre_completo = ' '.join(parts)
        return f"{nombre_completo} ({self.institucion.nombre})"

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
def notify_ticket_assignment(sender, instance, created, **kwargs):
    """
    Notifica al usuario responsable cuando se le asigna un ticket.
    """
    if instance.usuario_responsable:
        # Detectar si es nuevo o si el responsable cambió (opcionalmente)
        # Por ahora lo haremos simple: si hay responsable, notificamos
        
        payload = {
            "title": "🎫 Nuevo Ticket Asignado",
            "body": f"Folio {instance.folio or instance.id_solicitud}: {instance.falla_clasificacion or 'Sin clasificación'}",
            "icon": "/static/core/img/icon-512.png",
            "url": f"/callcenter/dashboard/ticket/{instance.id}/" # Ajustar a tu ruta de detalle
        }
        
        try:
            send_user_notification(user=instance.usuario_responsable, payload=payload, ttl=1000)
        except Exception as e:
            logger.warning(f"No se pudo enviar Web Push por ticket {instance.id}: {e}")

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


def add_historial(ticket, accion, usuario=None, descripcion=''):
    HistorialTicket.objects.create(
        ticket=ticket,
        accion=accion,
        usuario=usuario,
        descripcion=descripcion
    )


@receiver(post_save, sender=SolicitudTicket)
def track_ticket_changes(sender, instance, **kwargs):
    """
    Auto-detecta cambios en campos clave y registra en el historial.
    """
    if kwargs.get('created'):
        add_historial(instance, 'CREADO', descripcion="Ticket creado")
        return

    try:
        old = SolicitudTicket.objects.get(pk=instance.pk)
    except SolicitudTicket.DoesNotExist:
        return

    if instance.diagnostico and old.diagnostico != instance.diagnostico:
        add_historial(instance, 'DIAGNOSTICO', descripcion="Diagnóstico ingresado")
    if old.fecha_cierre != instance.fecha_cierre and instance.fecha_cierre:
        add_historial(instance, 'CIERRE_FECHA', descripcion=f"Fecha de cierre: {instance.fecha_cierre.strftime('%d/%m/%Y %H:%M')}")
    if not old.correo_cierre and instance.correo_cierre:
        add_historial(instance, 'CORREO_CIERRE', descripcion="Correo de cierre enviado")
    if old.robot_estatus != instance.robot_estatus and instance.robot_estatus:
        accion = 'SIG_SYNC' if 'COMPLETAMENTE' in str(instance.robot_estatus) else 'SIG_ERROR'
        add_historial(instance, accion, descripcion=f"SIG: {instance.robot_estatus}")
    if old.usuario_responsable != instance.usuario_responsable:
        name = instance.usuario_responsable.get_full_name() or str(instance.usuario_responsable) if instance.usuario_responsable else 'Sin asignar'
        add_historial(instance, 'REASIGNADO', descripcion=f"Asignado a: {name}")
    if old.deductiva != instance.deductiva and instance.deductiva:
        add_historial(instance, 'DEDUCTIVA', descripcion=f"Deductiva: ${instance.deductiva}")
    if not old.comentarios_internos and instance.comentarios_internos:
        add_historial(instance, 'COMENTARIO', descripcion="Comentario interno agregado")


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


class FallaTicket(models.Model):
    """
    Catálogo de fallas estandarizadas para el Call Center.
    """
    nombre = models.CharField(max_length=255, unique=True, verbose_name="Nombre de la Falla")
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subfallas',
        verbose_name="Falla Padre"
    )
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción Adicional")
    departamento_responsable = models.ForeignKey(
        'core.Departamento',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fallas_vinculadas',
        verbose_name="Departamento Responsable"
    )
    usuario_responsable = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fallas_asignadas_defecto',
        verbose_name="Responsable por Defecto"
    )

    def __str__(self):
        return self.nombre_completo

    @property
    def nombre_completo(self):
        if self.parent:
            return f"{self.parent.nombre} > {self.nombre}"
        return self.nombre

    def get_all_diagnosticos(self):
        """
        Retorna los diagnósticos de esta falla y de todas sus fallas padres (deduplicados).
        """
        diagnosticos = list(self.diagnosticos_asociados.all())
        if self.parent:
            parent_diags = self.parent.get_all_diagnosticos()
            seen = {d.id for d in diagnosticos}
            for d in parent_diags:
                if d.id not in seen:
                    diagnosticos.append(d)
                    seen.add(d.id)
        return diagnosticos

    class Meta:
        verbose_name = "Catálogo de Falla"
        verbose_name_plural = "Catálogo de Fallas"

class DiagnosticoTicket(models.Model):
    """
    Catálogo de diagnósticos estandarizados relacionados a una FallaTicket.
    Los hijos de la falla heredan implícitamente estos diagnósticos.
    """
    nombre = models.CharField(max_length=255, verbose_name="Nombre del Diagnóstico")
    falla = models.ForeignKey(
        FallaTicket,
        on_delete=models.CASCADE,
        related_name='diagnosticos_asociados',
        verbose_name="Falla Asociada"
    )
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción del Diagnóstico")
    actividad = models.CharField(max_length=255, blank=True, null=True, verbose_name="Actividad Realizada")

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Catálogo de Diagnóstico"
        verbose_name_plural = "Catálogos de Diagnósticos"
        ordering = ['falla__nombre', 'nombre']


class HistorialTicket(models.Model):
    ACCION_CHOICES = [
        ('CREADO', 'Ticket Creado'),
        ('ACTUALIZADO', 'Ticket Actualizado'),
        ('DIAGNOSTICO', 'Diagnóstico Ingresado'),
        ('CIERRE_FECHA', 'Fecha de Cierre Asignada'),
        ('CORREO_CIERRE', 'Correo de Cierre Enviado'),
        ('SIG_SYNC', 'Sincronización SIG'),
        ('SIG_ERROR', 'Error en Sincronización SIG'),
        ('DEDUCTIVA', 'Deductiva Actualizada'),
        ('REASIGNADO', 'Técnico Reasignado'),
        ('COMENTARIO', 'Comentario Interno'),
        ('CIERRE_VISUAL', 'Cierre Visual Realizado'),
    ]
    ticket = models.ForeignKey(
        SolicitudTicket,
        on_delete=models.CASCADE,
        related_name='historial',
        verbose_name="Ticket"
    )
    accion = models.CharField(
        max_length=20,
        choices=ACCION_CHOICES,
        verbose_name="Acción"
    )
    usuario = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name="Usuario"
    )
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    creado_en = models.DateTimeField(auto_now_add=True, verbose_name="Fecha")

    def __str__(self):
        return f"{self.get_accion_display()} - {self.ticket.folio or self.ticket.id_solicitud}"

    class Meta:
        verbose_name = "Historial de Ticket"
        verbose_name_plural = "Historial de Tickets"
        ordering = ['-creado_en']
