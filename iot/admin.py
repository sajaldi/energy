from django.contrib import admin, messages
from .models import BACnetGateway, BACnetDevice, BACnetPoint, Telemetry
from .services.bacnet import bacnet_instance
from asgiref.sync import async_to_sync

@admin.register(BACnetGateway)
class BACnetGatewayAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'ip_address', 'port', 'device_id', 'is_active', 'last_sync')
    list_filter = ('is_active',)
    search_fields = ('nombre', 'ip_address')

@admin.register(BACnetDevice)
class BACnetDeviceAdmin(admin.ModelAdmin):
    list_display = ('name', 'device_id', 'address', 'vendor', 'model_name', 'is_online', 'last_seen')
    list_filter = ('is_online', 'vendor', 'gateway')
    search_fields = ('name', 'address', 'device_id')
    readonly_fields = ('last_seen',)
    actions = ['discover_points']

    @admin.action(description="Descubrir puntos automáticamente")
    def discover_points(self, request, queryset):
        success_count = 0
        error_count = 0
        
        for device in queryset:
            try:
                # Ejecutamos la tarea asíncrona de forma síncrona para el admin
                result = async_to_sync(bacnet_instance.discover_device_points)(device)
                if result:
                    success_count += 1
                else:
                    error_count += 1
            except Exception as e:
                self.message_user(request, f"Error en {device.name}: {str(e)}", messages.ERROR)
                error_count += 1
        
        if success_count > 0:
            self.message_user(request, f"Se completó el descubrimiento en {success_count} dispositivos.", messages.SUCCESS)
        if error_count > 0:
            self.message_user(request, f"Hubo errores en {error_count} dispositivos. Revise los logs.", messages.WARNING)

@admin.register(BACnetPoint)
class BACnetPointAdmin(admin.ModelAdmin):
    list_display = ('name', 'device', 'object_type', 'instance', 'unit', 'save_history')
    list_filter = ('object_type', 'device', 'save_history')
    search_fields = ('name', 'description')

@admin.register(Telemetry)
class TelemetryAdmin(admin.ModelAdmin):
    list_display = ('point', 'value', 'timestamp', 'status')
    list_filter = ('point__device', 'timestamp')
    search_fields = ('point__name',)
    readonly_fields = ('timestamp',)

    def has_add_permission(self, request):
        return False # Solo lectura desde el admin, se llena via tareas
