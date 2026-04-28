from django.db import models

class BACnetGateway(models.Model):
    nombre = models.CharField(max_length=100)
    ip_address = models.GenericIPAddressField(help_text="IP local del servidor para el socket BACnet (o IP VPN)")
    port = models.IntegerField(default=47808)
    device_id = models.IntegerField(default=123, help_text="Device ID de este servidor en la red BACnet")
    is_active = models.BooleanField(default=True)
    last_sync = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Gateway BACnet"
        verbose_name_plural = "Gateways BACnet"

    def __str__(self):
        return f"{self.nombre} ({self.ip_address})"

class BACnetDevice(models.Model):
    gateway = models.ForeignKey(BACnetGateway, on_delete=models.CASCADE, related_name="devices")
    device_id = models.IntegerField(unique=True)
    name = models.CharField(max_length=200, blank=True, null=True)
    address = models.CharField(max_length=100, help_text="IP remota del controlador")
    vendor = models.CharField(max_length=100, blank=True, null=True)
    model_name = models.CharField(max_length=100, blank=True, null=True)
    is_online = models.BooleanField(default=True)
    last_seen = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Dispositivo BACnet"
        verbose_name_plural = "Dispositivos BACnet"

    def __str__(self):
        return f"{self.name or self.device_id} ({self.address})"

class BACnetPoint(models.Model):
    OBJECT_TYPES = [
        ('analogInput', 'Analog Input'),
        ('analogOutput', 'Analog Output'),
        ('analogValue', 'Analog Value'),
        ('binaryInput', 'Binary Input'),
        ('binaryOutput', 'Binary Output'),
        ('binaryValue', 'Binary Value'),
        ('multiStateInput', 'Multi-state Input'),
        ('multiStateOutput', 'Multi-state Output'),
        ('multiStateValue', 'Multi-state Value'),
    ]
    device = models.ForeignKey(BACnetDevice, on_delete=models.CASCADE, related_name="points")
    name = models.CharField(max_length=200)
    object_type = models.CharField(max_length=50, choices=OBJECT_TYPES)
    instance = models.IntegerField()
    description = models.TextField(blank=True, null=True)
    unit = models.CharField(max_length=50, blank=True, null=True)
    save_history = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Punto BACnet"
        verbose_name_plural = "Puntos BACnet"

    def __str__(self):
        return f"{self.name} ({self.object_type}:{self.instance})"

class Telemetry(models.Model):
    point = models.ForeignKey(BACnetPoint, on_delete=models.CASCADE, related_name="history")
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    value = models.FloatField()
    status = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Lectura de Telemetría"
        verbose_name_plural = "Lecturas de Telemetría"

    def __str__(self):
        return f"{self.point.name}: {self.value} @ {self.timestamp}"

class BACnetSchedule(models.Model):
    device = models.ForeignKey(BACnetDevice, on_delete=models.CASCADE, related_name="schedules")
    name = models.CharField(max_length=200)
    instance = models.IntegerField()
    weekly_schedule = models.JSONField(null=True, blank=True, help_text="JSON representation of weekly events")
    present_value = models.BooleanField(default=False)
    last_sync = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Horario BACnet"
        verbose_name_plural = "Horarios BACnet"
        unique_together = ('device', 'instance')

    def __str__(self):
        return f"{self.name} ({self.device.name})"
