from django.contrib import admin

from .models import InvitationToken


@admin.register(InvitationToken)
class InvitationTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'status', 'created_at', 'expires_at')
    list_filter = ('status', 'expires_at')
    search_fields = ('user__username', 'user__email', 'token')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)
