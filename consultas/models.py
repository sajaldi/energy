import re
from django.db import models
from django.contrib.auth.models import User
from pgvector.django import VectorField, CosineDistance


class Consulta(models.Model):
    """
    Representa un archivo TXT de chat (ej: WhatsApp) que se sube al sistema.
    Al procesarse, cada línea se parsea y almacena como MensajeConsulta.
    """
    nombre = models.CharField(
        max_length=255, 
        verbose_name="Nombre de la consulta",
        help_text="Nombre descriptivo para identificar este chat"
    )
    archivo = models.FileField(
        upload_to='consultas/%Y/%m/',
        verbose_name="Archivo TXT",
        help_text="Archivo de texto exportado del chat"
    )
    subido_por = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, blank=True,
        related_name='consultas_subidas'
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    procesado = models.BooleanField(default=False, verbose_name="¿Procesado?")
    total_mensajes = models.IntegerField(default=0, verbose_name="Total de mensajes")

    class Meta:
        verbose_name = "Consulta"
        verbose_name_plural = "Consultas"
        ordering = ['-creado_en']

    def __str__(self):
        return f"{self.nombre} ({self.total_mensajes} msgs)"

    def procesar_archivo(self):
        """
        Lee el archivo TXT, parsea cada mensaje de WhatsApp y lo almacena.
        
        El formato de WhatsApp puede tener mensajes multilínea. Un mensaje
        va desde una marca de tiempo hasta la siguiente marca de tiempo.
        Ejemplo:
            22/2/22 10:15 a. m. - Lesman OCC: Texto largo que puede
            continuar en la siguiente línea sin fecha.
            22/2/22 10:16 a. m. - Otro: Siguiente mensaje
        
        También maneja texto pegado sin salto de línea entre mensajes:
            ...final del msg anterior.22/2/22 10:16 a. m. - Otro: Siguiente
        """
        # Patrón para detectar el inicio de un mensaje de WhatsApp
        # Captura: fecha, hora, am/pm, remitente, texto inicial
        patron = re.compile(
            r'(\d{1,2}/\d{1,2}/\d{2,4})\s+'     # Fecha
            r'(\d{1,2}:\d{2})\s*'                 # Hora
            r'([ap]\.\s*m\.)\s*-\s*'              # AM/PM
            r'(.+?):\s*'                          # Nombre del remitente
            r'(.*)'                               # Texto del mensaje (puede estar vacío)
        )

        contenido = self.archivo.read().decode('utf-8', errors='replace')
        
        # Dividir el contenido usando el patrón de fecha como separador
        # Esto maneja correctamente mensajes multilínea y mensajes pegados
        partes = re.split(
            r'(?=\d{1,2}/\d{1,2}/\d{2,4}\s+\d{1,2}:\d{2}\s*[ap]\.\s*m\.\s*-\s*)',
            contenido
        )

        mensajes_creados = []
        for parte in partes:
            parte = parte.strip()
            if not parte:
                continue

            match = patron.match(parte)
            if match:
                fecha_str = match.group(1)
                hora_str = match.group(2)
                ampm = match.group(3)
                remitente = match.group(4).strip()
                texto = match.group(5).strip()

                # Si hay contenido después del match inicial (multilínea)
                resto = parte[match.end():]
                if resto:
                    texto += "\n" + resto.strip() if texto else resto.strip()

                mensajes_creados.append(MensajeConsulta(
                    consulta=self,
                    fecha_str=fecha_str,
                    hora_str=f"{hora_str} {ampm}",
                    remitente=remitente,
                    texto=texto,
                    linea_original=parte,
                ))

        # Insertar en bloque
        MensajeConsulta.objects.bulk_create(mensajes_creados)

        # Actualizar consulta
        self.procesado = True
        self.total_mensajes = len(mensajes_creados)
        self.save(update_fields=['procesado', 'total_mensajes'])

        return len(mensajes_creados)


class MensajeConsulta(models.Model):
    """
    Cada mensaje individual extraído del archivo de chat.
    Incluye embedding para búsqueda vectorial semántica.
    """
    consulta = models.ForeignKey(
        Consulta, 
        on_delete=models.CASCADE, 
        related_name='mensajes'
    )
    fecha_str = models.CharField(
        max_length=20, 
        verbose_name="Fecha",
        help_text="Fecha en formato original (ej: 22/2/22)"
    )
    hora_str = models.CharField(
        max_length=20, 
        verbose_name="Hora",
        help_text="Hora en formato original (ej: 10:15 a. m.)"
    )
    remitente = models.CharField(
        max_length=255, 
        verbose_name="Remitente",
        help_text="Nombre o número del remitente"
    )
    texto = models.TextField(
        verbose_name="Texto del mensaje"
    )
    linea_original = models.TextField(
        verbose_name="Línea original",
        help_text="Texto completo sin parsear para referencia"
    )

    # Búsqueda vectorial semántica
    embedding = VectorField(dimensions=768, null=True, blank=True)

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Mensaje de Consulta"
        verbose_name_plural = "Mensajes de Consulta"
        ordering = ['consulta', 'id']
        indexes = [
            models.Index(fields=['consulta', 'remitente']),
            models.Index(fields=['remitente']),
        ]

    def __str__(self):
        return f"[{self.fecha_str} {self.hora_str}] {self.remitente}: {self.texto[:50]}"

    @classmethod
    def buscar_vectorial(cls, query_embedding, consulta=None, remitente=None, limit=10):
        """
        Búsqueda semántica de mensajes usando distancia coseno.
        
        Args:
            query_embedding: Vector de embedding de la consulta del usuario
            consulta: (opcional) Filtrar por consulta específica
            remitente: (opcional) Filtrar por remitente
            limit: Número máximo de resultados
        
        Returns:
            QuerySet con mensajes ordenados por similitud
        """
        qs = cls.objects.exclude(embedding__isnull=True)

        if consulta:
            qs = qs.filter(consulta=consulta)
        if remitente:
            qs = qs.filter(remitente__icontains=remitente)

        return qs.annotate(
            distancia=CosineDistance('embedding', query_embedding)
        ).order_by('distancia')[:limit]


class ConversacionIA(models.Model):
    """
    Historial de preguntas y respuestas de la búsqueda IA.
    Cada interacción se vectoriza para enriquecer futuras búsquedas.
    """
    consulta = models.ForeignKey(
        Consulta,
        on_delete=models.CASCADE,
        related_name='conversaciones'
    )
    session_id = models.CharField(
        max_length=64,
        db_index=True,
        help_text="ID de sesión para agrupar una conversación"
    )
    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    pregunta = models.TextField(verbose_name="Pregunta del usuario")
    respuesta = models.TextField(verbose_name="Respuesta de la IA")

    # Embedding de la pregunta+respuesta para contexto futuro
    embedding = VectorField(dimensions=768, null=True, blank=True)

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Conversación IA"
        verbose_name_plural = "Conversaciones IA"
        ordering = ['session_id', 'creado_en']
        indexes = [
            models.Index(fields=['consulta', 'session_id']),
        ]

    def __str__(self):
        return f"[{self.creado_en:%d/%m/%y %H:%M}] {self.pregunta[:50]}"

    def texto_para_embedding(self):
        """Texto combinado para vectorizar."""
        return f"Pregunta: {self.pregunta}\nRespuesta: {self.respuesta[:500]}"

    @classmethod
    def buscar_contexto_previo(cls, query_embedding, consulta, session_id=None, limit=5):
        """
        Busca conversaciones previas relevantes como contexto adicional.
        """
        qs = cls.objects.filter(consulta=consulta).exclude(embedding__isnull=True)
        if session_id:
            # Priorizar la sesión actual pero no excluir otras
            pass
        return qs.annotate(
            distancia=CosineDistance('embedding', query_embedding)
        ).order_by('distancia')[:limit]


class NotaContexto(models.Model):
    """
    Notas de contexto proporcionadas por el usuario para enriquecer las respuestas de IA.
    Ej: "Lesman OCC es el operador del centro de control", "CBD es el Centro de Bodega"
    Se inyectan automáticamente como contexto en cada búsqueda/chat.
    Se vectorizan para ser encontradas cuando son relevantes.
    """
    consulta = models.ForeignKey(
        Consulta,
        on_delete=models.CASCADE,
        related_name='notas_contexto'
    )
    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    # El texto de la nota (ej: "Juan Inestroza es el técnico de plomería")
    contenido = models.TextField(verbose_name="Nota de contexto")
    
    # Categoría opcional para organizar
    CATEGORIA_CHOICES = [
        ('PERSONA', 'Persona / Rol'),
        ('LUGAR', 'Lugar / Ubicación'),
        ('TERMINO', 'Término / Acrónimo'),
        ('PROCESO', 'Proceso / Procedimiento'),
        ('OTRO', 'Otro'),
    ]
    categoria = models.CharField(max_length=20, choices=CATEGORIA_CHOICES, default='OTRO')

    # Embedding para búsqueda por relevancia
    embedding = VectorField(dimensions=768, null=True, blank=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Nota de Contexto"
        verbose_name_plural = "Notas de Contexto"
        ordering = ['-actualizado_en']

    def __str__(self):
        return f"[{self.get_categoria_display()}] {self.contenido[:80]}"

    @classmethod
    def obtener_contexto_relevante(cls, query_embedding, consulta, limit=10):
        """Busca notas de contexto relevantes para una query."""
        qs = cls.objects.filter(consulta=consulta).exclude(embedding__isnull=True)
        return qs.annotate(
            distancia=CosineDistance('embedding', query_embedding)
        ).order_by('distancia')[:limit]

    @classmethod
    def obtener_todas(cls, consulta):
        """Retorna todas las notas de contexto de una consulta (para inyectar siempre)."""
        return cls.objects.filter(consulta=consulta).values_list('contenido', flat=True)
