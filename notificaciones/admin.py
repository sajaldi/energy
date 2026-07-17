from django.contrib import admin
from .models import Notificacion


@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'user', 'tipo', 'modulo', 'leida', 'creado_en']
    list_filter = ['tipo', 'modulo', 'leida', 'creado_en']
    search_fields = ['titulo', 'mensaje', 'user__username']
    ordering = ['-creado_en']
    date_hierarchy = 'creado_en'
    raw_id_fields = ['user', 'emisor']
    actions = ['marcar_como_leidas']

    @admin.action(description='Marcar como leídas')
    def marcar_como_leidas(self, request, queryset):
        updated = queryset.update(leida=True)
        self.message_user(request, f'{updated} notificaciones marcadas como leídas.')
