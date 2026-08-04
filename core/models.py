from django.db import models
from django.core.cache import cache
from colorfield.fields import ColorField
from pgvector.django import VectorField
from .models_config import ConfiguracionUI

class TipoMedidor(models.Model):
    """Representa un tipo de medidor."""
    nombre = models.CharField(max_length=50, unique=True)
    descripcion = models.TextField(blank=True, null=True)
    #verbose
    verbose_name = 'Tipo de Medidor'
    verbose_name_plural = 'Tipos de Medidores'
    def __str__(self) -> str:
        return str(self.nombre)
    

class UnidadMedida(models.Model):
    """Representa una unidad de medida."""
    nombre = models.CharField(max_length=50, unique=True)
    simbolo = models.CharField(max_length=10, blank=True, null=True)
    descripcion = models.TextField(blank=True, null=True)

    def __str__(self) -> str:
        return str(self.nombre)
    
    class Meta:
        verbose_name = 'Unidad de Medida'
        verbose_name_plural = 'Unidades de Medida'
        
class Medidor(models.Model):
    
    nombre = models.CharField(max_length=50)
    tipo = models.CharField(max_length=50, blank=True, null=True)
    tipo_medidor = models.ForeignKey(TipoMedidor, on_delete=models.CASCADE, null=True, blank=True, related_name='medidores')
    medidor_padre = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='medidores_hijos')
    unidad = models.ForeignKey(UnidadMedida, on_delete=models.CASCADE, null=True, blank=True, related_name='medidores')
    def __str__(self):
        return self.nombre

class VistaConsumoDiferencia(models.Model):
    medidor_id = models.IntegerField(primary_key=True)  # Django necesita un primary_key
    fecha = models.DateTimeField()
    consumo = models.FloatField()
    consumo_anterior = models.FloatField()
    diferencia_consumo = models.FloatField()

    class Meta:
        managed = False  # Evita que Django intente crear esta tabla
        db_table = 'vista_consumo_diferencia'
        verbose_name = 'Vista Consumo Diferencia'
        verbose_name_plural = 'Vista Consumo Diferencia'
        ordering = ['-fecha']

class Consumo(models.Model):
    # El db_index en la fecha también ayuda a las consultas de rango
    fecha = models.DateTimeField(db_index=True) 
    consumo = models.FloatField(null=True, blank=True)
    medidor = models.ForeignKey(
        'Medidor',  # Usar el nombre como string es más seguro para evitar importaciones circulares
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name='consumos',
        # --- OPTIMIZACIÓN 1: AÑADIR ÍNDICE SIMPLE ---
        # Acelera drásticamente cualquier consulta que filtre por medidor (ej. WHERE medidor_id = X)
        db_index=True 
    )
    
    class Meta:
        unique_together = [['fecha', 'medidor']]
        verbose_name = 'Consumo'
        verbose_name_plural = 'Consumos'
        # --- OPTIMIZACIÓN 2: AÑADIR ÍNDICE COMPUESTO ---
        # Súper optimización para consultas que filtran por medidor Y ordenan/filtran por fecha.
        # Es exactamente lo que hacemos en los gráficos e inlines.
        indexes = [
            models.Index(fields=['medidor', 'fecha']),
        ]

    def __str__(self):
        # Pequeña mejora: quitamos 'kWh' para que no sea fijo, ya que ahora la unidad es dinámica.
        return f"{self.medidor.nombre if self.medidor else 'Sin medidor'} - {self.fecha} - {self.consumo}"
    
    

from django.db import models

class InterfaceConsumo(models.Model):
    fecha = models.DateTimeField(null=True, blank=True)
    consumo = models.FloatField(null=True, blank=True)
    medidor = models.CharField(max_length=50, null=True, blank=True)
    
    class Meta:
        db_table = 'interface_core_consumo'
        managed = True
        unique_together = ['fecha', 'medidor']

        # NO unique_together HERE

from django.db import models

class Equipo(models.Model):
    """Representa un equipo en el sistema."""
    numero_equipo = models.CharField(max_length=50, unique=True)
    descripcion = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self) -> str:
        return str(self.numero_equipo)

class UbicacionTecnica(models.Model):
    """Representa una ubicación técnica en el sistema."""
    codigo_ubicacion = models.CharField(max_length=50, unique=True)
    descripcion = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self) -> str:
        return str(self.codigo_ubicacion)

class CategoriaPuntoMedicion(models.Model):
    """Clasifica los puntos de medición por su tipo."""
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True)

    def __str__(self) -> str:
        return str(self.nombre)

class CaracteristicaMedicion(models.Model):
    """Define la característica que se mide (ej. Temperatura, Presión) y su unidad."""
    nombre = models.CharField(max_length=100, unique=True)
    unidad_medida = models.CharField(max_length=20)
    descripcion = models.TextField(blank=True, null=True)
    # Removed: ambito_medicion_inferior, ambito_medicion_superior, valor_objetivo

    def __str__(self) -> str:
        return f"{self.nombre} ({self.unidad_medida})"

class RangoMedicion(models.Model):
    """Define rangos personalizados para cada característica de medición."""
    caracteristica = models.ForeignKey(
        CaracteristicaMedicion,
        on_delete=models.CASCADE,
        related_name='rangos'
    )
    valor_min = models.FloatField(verbose_name="Valor mínimo")
    valor_max = models.FloatField(verbose_name="Valor máximo")
    descripcion = models.CharField(max_length=255, verbose_name="Descripción")
    color = ColorField(default='#FF0000', verbose_name="Color representativo")
    
    def __str__(self) -> str:
        return f"{self.descripcion} ({self.valor_min} - {self.valor_max})"
    
    class Meta:
        verbose_name = "Rango de Medición"
        verbose_name_plural = "Rangos de Medición"
        ordering = ['caracteristica', 'valor_min']

class PuntoMedicion(models.Model):
    """Representa un punto específico donde se realiza una medición."""
    numero_interno = models.AutoField(primary_key=True)
    descripcion = models.CharField(max_length=255)
    objeto_tecnico_equipo = models.ForeignKey(Equipo, on_delete=models.CASCADE, blank=True, null=True, verbose_name="Equipo Asociado")
    objeto_tecnico_ubicacion = models.ForeignKey(UbicacionTecnica, on_delete=models.CASCADE, blank=True, null=True, verbose_name="Ubicación Técnica Asociada")
    categoria = models.ForeignKey(CategoriaPuntoMedicion, on_delete=models.SET_NULL, blank=True, null=True)
    caracteristica = models.ForeignKey(CaracteristicaMedicion, on_delete=models.PROTECT)
    es_contador = models.BooleanField(default=False, verbose_name="Es Contador")
    # Removed fields: ambito_medicion_inferior, ambito_medicion_superior, valor_objetivo

    def __str__(self) -> str:  # Add explicit return type annotation
        return str(self.descripcion)  # Ensure string conversion

    class Meta:
        verbose_name = "Punto de Medición"
        verbose_name_plural = "Puntos de Medición"

class DocumentoMedicion(models.Model):
    """Registra las lecturas tomadas en los puntos de medición."""
    punto_medicion = models.ForeignKey(PuntoMedicion, on_delete=models.CASCADE)
    fecha_hora_lectura = models.DateTimeField(verbose_name="Fecha y hora de lectura")  # Removed auto_now_add
    valor_leido = models.FloatField()
    lectura_contador = models.FloatField(blank=True, null=True, verbose_name="Lectura de Contador (si aplica)")
    observaciones = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Lectura de {str(self.punto_medicion)} el {self.fecha_hora_lectura}"

    class Meta:
        verbose_name = "Documento de Medición"
        verbose_name_plural = "Documentos de Medición"
        ordering = ['-fecha_hora_lectura']

class Servicio(models.Model):
    """Representa un servicio para agrupar KPIs."""
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Servicio"
        verbose_name_plural = "Servicios"

class KPI(models.Model):
    """Representa un indicador clave de rendimiento (KPI)."""
    kpi = models.CharField(max_length=100, verbose_name="KPI")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")
    servicio = models.ForeignKey(Servicio, on_delete=models.CASCADE, related_name='kpis', verbose_name="Servicio")

    def __str__(self):
        return f"{self.kpi} ({self.servicio.nombre})"

    class Meta:
        verbose_name = "KPI"
        verbose_name_plural = "KPIs"
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class Departamento(models.Model):
    """Representa un departamento de la empresa."""
    nombre = models.CharField(max_length=100, unique=True, verbose_name="Nombre del Departamento")
    codigo = models.CharField(max_length=4, blank=True, null=True, verbose_name="Código")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")
    responsable = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='departamentos_a_cargo', verbose_name="Responsable / Jefe de departamento")
    aprobador = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='departamentos_a_aprobar', verbose_name="Aprobador de Requisiciones")
    correo = models.EmailField(max_length=255, blank=True, null=True, verbose_name="Correo del Departamento")

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Departamento"
        verbose_name_plural = "Departamentos"

class PerfilUsuario(models.Model):
    INVITATION_STATUS_CHOICES = [
        ('pending', 'Pending Invitation'),
        ('active',  'Active'),
    ]

    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    visto_tutorial = models.BooleanField(default=False, verbose_name="Visto tutorial")
    telefono = models.CharField(max_length=20, blank=True, null=True, verbose_name="Teléfono")
    puesto = models.ForeignKey('mantenimiento.PuestoTrabajo', on_delete=models.SET_NULL, null=True, blank=True, related_name='perfiles_usuario', verbose_name="Puesto de Trabajo")
    departamento = models.ForeignKey(Departamento, on_delete=models.SET_NULL, null=True, blank=True, related_name='usuarios', verbose_name="Departamento")
    ubicacion_defecto = models.ForeignKey('activos.Ubicacion', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Ubicación por Defecto")
    responsable = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='subordinados', verbose_name="Responsable / Jefe Directo")
    invitation_status = models.CharField(
        max_length=10,
        choices=INVITATION_STATUS_CHOICES,
        default='active',
        verbose_name="Estado de Invitación",
    )
    nav_config = models.JSONField(
        default=dict, blank=True, verbose_name="Configuración de navegación",
        help_text='{"hidden_menus": ["Mantenimiento"], "custom_menus": [{"name": "Mis Links", "icon": "fas fa-star", "color": "#f59e0b", "columns": [{"heading": "", "items": [{"name": "Link", "url": "/url/"}]}]}]}',
    )

    def __str__(self):
        return f"Perfil de {self.usuario.username}"

    class Meta:
        verbose_name = "Perfil de Usuario"
        verbose_name_plural = "Perfiles de Usuarios"

@receiver(post_save, sender=User)
def crear_perfil_usuario(sender, instance, created, **kwargs):
    if created:
        PerfilUsuario.objects.create(usuario=instance, invitation_status='active')

@receiver(post_save, sender=User)
def guardar_perfil_usuario(sender, instance, **kwargs):
    if hasattr(instance, 'perfil'):
        instance.perfil.save()
    else:
        PerfilUsuario.objects.get_or_create(usuario=instance, defaults={'invitation_status': 'active'})


class VistaPersonalizada(models.Model):
    """Permite guardar filtros del admin como vistas personalizadas."""
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='vistas_personalizadas')
    nombre = models.CharField(max_length=100)
    app_label = models.CharField(max_length=100)
    model_name = models.CharField(max_length=100)
    query_string = models.TextField(help_text="Query string del filtro (ej: ?empresa__id=1)")
    es_publica = models.BooleanField(default=False, verbose_name="¿Es pública?")
    color = ColorField(default='#4f46e5', verbose_name="Color de la etiqueta")
    icono = models.CharField(max_length=50, default='fas fa-filter', verbose_name="Icono FontAwesome")
    creado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nombre} ({self.model_name})"

    class Meta:
        verbose_name = "Vista Personalizada"
        verbose_name_plural = "Vistas Personalizadas"
        ordering = ['nombre']
        unique_together = ['usuario', 'nombre', 'app_label', 'model_name']


class KnowledgeChunk(models.Model):
    """
    Fragmento de conocimiento para búsqueda vectorial.
    """
    content = models.TextField()
    embedding = VectorField(dimensions=384, null=True, blank=True)
    source = models.CharField(max_length=255, blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Fragmento de Conocimiento"
        verbose_name_plural = "Fragmentos de Conocimiento"

    def __str__(self):
        return f"Chunk {self.id} from {self.source}"


class ElementoApp(models.Model):
    """
    Configura la visibilidad de cada sección/botón del dashboard móvil
    según los Grupos de Django. Si no tiene grupos asignados, es visible para todos.
    """
    clave = models.CharField(
        max_length=50, unique=True,
        help_text="Identificador interno (ej: auditoria, finanzas, logistica)"
    )
    nombre = models.CharField(
        max_length=100,
        help_text="Nombre visible en el admin (ej: Auditoría, Gestión Financiera)"
    )
    descripcion = models.CharField(max_length=255, blank=True, default='')
    grupos = models.ManyToManyField(
        'auth.Group', blank=True,
        help_text="Grupos que pueden ver este elemento. Si está vacío, es visible para TODOS."
    )
    activo = models.BooleanField(default=True, help_text="Desactivar para ocultar globalmente")
    orden = models.PositiveIntegerField(default=0, help_text="Orden de aparición")

    class Meta:
        verbose_name = "Elemento de App"
        verbose_name_plural = "Elementos de App"
        ordering = ['orden', 'nombre']

    def __str__(self):
        return f"{self.nombre} ({self.clave})"

    @staticmethod
    def get_secciones_usuario(user):
        """
        Retorna un set con las claves de los elementos activos
        visibles para el usuario, según sus grupos.
        Superusuarios ven todo.
        Elementos sin grupos asignados son visibles para todos.
        """
        from django.db.models import Count
        qs = ElementoApp.objects.filter(activo=True)
        if user.is_superuser:
            return set(qs.values_list('clave', flat=True))

        user_groups = user.groups.all()
        # Elementos con al menos un grupo del usuario
        con_grupo = set(
            qs.filter(grupos__in=user_groups)
            .values_list('clave', flat=True).distinct()
        )
        # Elementos sin ningún grupo (visibles para todos)
        sin_grupo = set(
            qs.annotate(num_g=Count('grupos'))
            .filter(num_g=0)
            .values_list('clave', flat=True)
        )
        return con_grupo | sin_grupo


class AdminNavMenu(models.Model):
    name = models.CharField(max_length=100, verbose_name="Nombre")
    icon = models.CharField(max_length=100, default="fas fa-circle", verbose_name="Icono (FontAwesome)")
    color = models.CharField(max_length=20, default="#0064d2", verbose_name="Color (hex)")
    superuser_only = models.BooleanField(default=False, verbose_name="Solo superusuarios")
    order = models.IntegerField(default=0, verbose_name="Orden")
    active = models.BooleanField(default=True, verbose_name="Activo")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order"]
        verbose_name = "Menú de navegación"
        verbose_name_plural = "Menús de navegación"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        cache.delete("admin_nav_groups")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        cache.delete("admin_nav_groups")
        super().delete(*args, **kwargs)


class AdminNavColumn(models.Model):
    menu = models.ForeignKey(AdminNavMenu, on_delete=models.CASCADE, related_name="columns", verbose_name="Menú")
    heading = models.CharField(max_length=100, verbose_name="Encabezado")
    order = models.IntegerField(default=0, verbose_name="Orden")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order"]
        verbose_name = "Columna de menú"
        verbose_name_plural = "Columnas de menú"

    def __str__(self):
        return f"{self.menu.name} → {self.heading}"

    def save(self, *args, **kwargs):
        cache.delete("admin_nav_groups")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        cache.delete("admin_nav_groups")
        super().delete(*args, **kwargs)


class AdminNavItem(models.Model):
    column = models.ForeignKey(AdminNavColumn, on_delete=models.CASCADE, related_name="items", verbose_name="Columna", blank=True, null=True)
    menu = models.ForeignKey(AdminNavMenu, on_delete=models.CASCADE, related_name="items", verbose_name="Menú", blank=True, null=True)
    name = models.CharField(max_length=200, verbose_name="Nombre")
    url = models.CharField(max_length=500, verbose_name="URL")
    permission = models.CharField(max_length=200, blank=True, null=True, verbose_name="Permiso requerido")
    group = models.CharField(max_length=100, blank=True, null=True, verbose_name="Encabezado de columna", help_text="Agrupa items bajo un mismo encabezado en el mega menú")
    order = models.IntegerField(default=0, verbose_name="Orden")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order"]
        verbose_name = "Elemento de menú"
        verbose_name_plural = "Elementos de menú"

    def __str__(self):
        return self.name

    def clean(self):
        from django.core.exceptions import ValidationError
        if not self.column_id and not self.menu_id:
            raise ValidationError("Debes asignar el elemento a un Menú o a una Columna.")

    def save(self, *args, **kwargs):
        if self.column_id and not self.menu_id:
            self.menu = self.column.menu
        cache.delete("admin_nav_groups")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        cache.delete("admin_nav_groups")
        super().delete(*args, **kwargs)


