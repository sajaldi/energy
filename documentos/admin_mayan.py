from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline
from django.utils.html import format_html
from .models import MayanDocumentLink

class MayanDocumentInline(GenericTabularInline):
    """Inline para mostrar documentos de Mayan vinculados"""
    model = MayanDocumentLink
    extra = 0
    fields = ('document_label', 'document_type', 'get_view_link', 'uploaded_by', 'uploaded_at')
    readonly_fields = ('get_view_link', 'uploaded_by', 'uploaded_at')
    can_delete = True
    
    def get_view_link(self, obj):
        if not obj.id:
            return "-"
        
        return format_html(
            '<div style="display: flex; gap: 8px;">'
            '<a href="{}" target="_blank" class="button" style="background: #2563eb; color: white; padding: 4px 12px; border-radius: 4px; text-decoration: none;">'
            '📄 Ver en Mayan'
            '</a> '
            '<a href="{}" target="_blank" class="button" style="background: #10b981; color: white; padding: 4px 12px; border-radius: 4px; text-decoration: none;">'
            '⬇️ Descargar'
            '</a>'
            '</div>',
            obj.mayan_url,
            obj.download_url
        )
    get_view_link.short_description = "Acciones"

@admin.register(MayanDocumentLink)
class MayanDocumentLinkAdmin(admin.ModelAdmin):
    list_display = ('document_label', 'document_type', 'content_type', 'content_object', 'uploaded_by', 'uploaded_at')
    list_filter = ('document_type', 'content_type', 'uploaded_at')
    search_fields = ('document_label', 'description')
    readonly_fields = ('uploaded_by', 'uploaded_at')
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)
