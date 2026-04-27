from django.contrib import admin
from .models import BACnetGateway, BACnetDevice, BACnetPoint, Telemetry

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
