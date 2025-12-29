"""
Administración de Django para el Sistema de Firmas Electrónicas
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models_firmas import (
    PerfilFirma, DocumentoFirmado, FirmaRequerida, 
    Firma, AuditoriaFirmas
)


@admin.register(PerfilFirma)
class PerfilFirmaAdmin(admin.ModelAdmin):
    list_display = ['usuario', 'cargo', 'departamento', 'activa', 'preview_firma', 'actualizada_en']
    list_filter = ['activa', 'creada_en']
    search_fields = ['usuario__username', 'usuario__first_name', 'usuario__last_name', 'cargo']
    readonly_fields = ['creada_en', 'actualizada_en', 'preview_firma_grande']
    
    fieldsets = (
        ('Usuario', {
            'fields': ('usuario', 'activa')
        }),
        ('Información', {
            'fields': ('cargo', 'departamento')
        }),
        ('Firma', {
            'fields': ('firma_imagen', 'preview_firma_grande')
        }),
        ('Metadatos', {
            'fields': ('creada_en', 'actualizada_en'),
            'classes': ('collapse',)
        }),
    )
    
    def preview_firma(self, obj):
        if obj.firma_imagen:
            return format_html(
                '<img src="{}" style="max-height: 40px; background: white; padding: 2px; border: 1px solid #ddd;"/>',
                obj.firma_imagen.url
            )
        return '-'
    preview_firma.short_description = 'Firma'
    
    def preview_firma_grande(self, obj):
        if obj.firma_imagen:
            return format_html(
                '<img src="{}" style="max-width: 400px; background: white; padding: 10px; border: 2px solid #ddd; border-radius: 8px;"/>',
                obj.firma_imagen.url
            )
        return '-'
    preview_firma_grande.short_description = 'Vista Previa'


class FirmaRequeridaInline(admin.TabularInline):
    model = FirmaRequerida
    extra = 1
    fields = ['firmante', 'rol', 'orden', 'obligatoria', 'posicion_x', 'posicion_y', 'pagina', 'estado_firma']
    readonly_fields = ['estado_firma']
    
    def estado_firma(self, obj):
        if hasattr(obj, 'firma_aplicada'):
            if obj.firma_aplicada.firmado:
                return format_html('<span style="color: green;">✅ Firmado</span>')
            elif obj.firma_aplicada.rechazado:
                return format_html('<span style="color: red;">❌ Rechazado</span>')
        return format_html('<span style="color: orange;">⏳ Pendiente</span>')
    estado_firma.short_description = 'Estado'


class FirmaInline(admin.TabularInline):
    model = Firma
    extra = 0
    can_delete = False
    fields = ['firmante', 'fecha_firma', 'firmado', 'rechazado', 'preview_firma', 'ver_firma']
    readonly_fields = ['firmante', 'fecha_firma', 'firmado', 'rechazado', 'preview_firma', 'ver_firma']
    
    def preview_firma(self, obj):
        if obj.imagen_firma:
            return format_html(
                '<img src="{}" style="max-height: 30px;"/>',
                obj.imagen_firma.url
            )
        return '-'
    preview_firma.short_description = 'Firma'
    
    def ver_firma(self, obj):
        url = reverse('admin:documentos_firma_change', args=[obj.pk])
        return format_html('<a href="{}">Ver detalle</a>', url)
    ver_firma.short_description = 'Acciones'


@admin.register(DocumentoFirmado)
class DocumentoFirmadoAdmin(admin.ModelAdmin):
    list_display = ['documento', 'revision', 'estado', 'progreso_firmas', 'creado_en', 'acciones']
    list_filter = ['estado', 'creado_en']
    search_fields = ['documento__codigo', 'documento__titulo']
    readonly_fields = [
        'hash_documento_original', 'creado_en', 'actualizado_en', 
        'progreso_firmas', 'verificar_integridad_display'
    ]
    inlines = [FirmaRequeridaInline, FirmaInline]
    
    fieldsets = (
        ('Documento', {
            'fields': ('documento', 'revision', 'estado')
        }),
        ('Seguridad', {
            'fields': ('hash_documento_original', 'verificar_integridad_display'),
            'classes': ('collapse',)
        }),
        ('Archivo Firmado', {
            'fields': ('pdf_firmado',)
        }),
        ('Metadatos', {
            'fields': ('creado_en', 'actualizado_en'),
            'classes': ('collapse',)
        }),
    )
    
    def progreso_firmas(self, obj):
        total = obj.firmas_requeridas.count()
        firmadas = obj.firmas.filter(firmado=True, rechazado=False).count()
        rechazadas = obj.firmas.filter(rechazado=True).count()
        
        if rechazadas > 0:
            color = 'red'
            texto = f'{rechazadas} rechazadas'
        elif firmadas == total and total > 0:
            color = 'green'
            texto = 'Completo'
        elif firmadas > 0:
            color = 'orange'
            texto = f'{firmadas}/{total}'
        else:
            color = 'gray'
            texto = f'0/{total}'
        
        return format_html(
            '<span style="background: {}; color: white; padding: 4px 12px; border-radius: 12px; font-weight: 600;">{}</span>',
            color, texto
        )
    progreso_firmas.short_description = 'Progreso'
    
    def verificar_integridad_display(self, obj):
        if obj.pk:
            es_valido = obj.verificar_integridad()
            if es_valido:
                return format_html(
                    '<span style="color: green; font-weight: 600;">✅ Documento íntegro (no modificado)</span>'
                )
            else:
                return format_html(
                    '<span style="color: red; font-weight: 600;">⚠️ ADVERTENCIA: Documento modificado</span>'
                )
        return '-'
    verificar_integridad_display.short_description = 'Verificación de Integridad'
    
    def acciones(self, obj):
        return format_html(
            '<a class="button" href="{}">Ver Firmas</a>',
            reverse('admin:documentos_documentofirmado_change', args=[obj.pk])
        )
    acciones.short_description = 'Acciones'


@admin.register(FirmaRequerida)
class FirmaRequeridaAdmin(admin.ModelAdmin):
    list_display = ['documento_firmado', 'firmante', 'rol', 'orden', 'obligatoria', 'estado_firma']
    list_filter = ['obligatoria', 'orden']
    search_fields = ['documento_firmado__documento__codigo', 'firmante__username', 'firmante__first_name']
    readonly_fields = ['estado_firma']
    
    fieldsets = (
        ('Documento', {
            'fields': ('documento_firmado',)
        }),
        ('Firmante', {
            'fields': ('firmante', 'rol', 'orden', 'obligatoria')
        }),
        ('Posicionamiento', {
            'fields': (
                ('posicion_x', 'posicion_y'),
                'pagina',
                ('ancho', 'alto')
            )
        }),
        ('Notificaciones', {
            'fields': ('notificado', 'fecha_notificacion'),
            'classes': ('collapse',)
        }),
        ('Estado', {
            'fields': ('estado_firma',)
        }),
    )
    
    def estado_firma(self, obj):
        if hasattr(obj, 'firma_aplicada'):
            firma = obj.firma_aplicada
            if firma.firmado:
                return format_html(
                    '<span style="color: green; font-weight: 600;">✅ Firmado el {}</span>',
                    firma.fecha_firma.strftime('%d/%m/%Y %H:%M')
                )
            elif firma.rechazado:
                return format_html(
                    '<span style="color: red; font-weight: 600;">❌ Rechazado: {}</span>',
                    firma.motivo_rechazo or 'Sin motivo'
                )
        return format_html('<span style="color: orange; font-weight: 600;">⏳ Pendiente</span>')
    estado_firma.short_description = 'Estado'


@admin.register(Firma)
class FirmaAdmin(admin.ModelAdmin):
    list_display = [
        'documento_firmado', 'firmante', 'fecha_firma', 
        'estado_visual', 'preview_firma', 'ver_token'
    ]
    list_filter = ['firmado', 'rechazado', 'fecha_firma']
    search_fields = [
        'documento_firmado__documento__codigo',
        'firmante__username',
        'firmante__first_name',
        'token_verificacion'
    ]
    readonly_fields = [
        'token_verificacion', 'hash_firma', 'fecha_firma',
        'preview_firma_grande', 'certificado_display', 'qr_verificacion'
    ]
    
    fieldsets = (
        ('Documento', {
            'fields': ('documento_firmado', 'firma_requerida')
        }),
        ('Firmante', {
            'fields': ('firmante', 'imagen_firma', 'preview_firma_grande')
        }),
        ('Posición', {
            'fields': (
                ('posicion_x', 'posicion_y'),
                'pagina',
                ('ancho', 'alto')
            )
        }),
        ('Estado', {
            'fields': ('firmado', 'rechazado', 'motivo_rechazo', 'comentarios')
        }),
        ('Trazabilidad', {
            'fields': (
                'fecha_firma',
                'ip_firmante',
                'user_agent',
            )
        }),
        ('Seguridad', {
            'fields': (
                'token_verificacion',
                'hash_firma',
                'certificado_display',
                'qr_verificacion'
            ),
            'classes': ('collapse',)
        }),
    )
    
    def estado_visual(self, obj):
        if obj.firmado:
            return format_html('<span style="color: green; font-weight: 600;">✅ Firmado</span>')
        elif obj.rechazado:
            return format_html('<span style="color: red; font-weight: 600;">❌ Rechazado</span>')
        return format_html('<span style="color: gray;">-</span>')
    estado_visual.short_description = 'Estado'
    
    def preview_firma(self, obj):
        if obj.imagen_firma:
            return format_html(
                '<img src="{}" style="max-height: 40px; background: white; padding: 2px; border: 1px solid #ddd;"/>',
                obj.imagen_firma.url
            )
        return '-'
    preview_firma.short_description = 'Firma'
    
    def preview_firma_grande(self, obj):
        if obj.imagen_firma:
            return format_html(
                '<img src="{}" style="max-width: 400px; background: white; padding: 10px; border: 2px solid #ddd; border-radius: 8px;"/>',
                obj.imagen_firma.url
            )
        return '-'
    preview_firma_grande.short_description = 'Vista Previa de Firma'
    
    def ver_token(self, obj):
        url = reverse('firmas:verificar_firma', args=[obj.token_verificacion])
        return format_html(
            '<a href="{}" target="_blank" class="button">🔍 Verificar</a>',
            url
        )
    ver_token.short_description = 'Verificación'
    
    def certificado_display(self, obj):
        if obj.pk:
            cert = obj.generar_certificado_autenticidad()
            import json
            cert_json = json.dumps(cert, indent=2, ensure_ascii=False)
            return format_html(
                '<pre style="background: #2c3e50; color: #2ecc71; padding: 15px; border-radius: 8px; overflow-x: auto;">{}</pre>',
                cert_json
            )
        return '-'
    certificado_display.short_description = 'Certificado de Autenticidad'
    
    def qr_verificacion(self, obj):
        if obj.pk:
            url = reverse('firmas:verificar_firma', args=[obj.token_verificacion])
            # Aquí podrías generar un código QR con una librería como qrcode
            # Por ahora solo mostramos el link
            return format_html(
                '<div style="background: white; padding: 15px; border: 2px solid #ddd; border-radius: 8px;">'
                '<p><strong>URL de Verificación:</strong></p>'
                '<input type="text" value="{}" readonly style="width: 100%; padding: 8px; font-family: monospace;" />'
                '</div>',
                self.request.build_absolute_uri(url) if hasattr(self, 'request') else url
            )
        return '-'
    qr_verificacion.short_description = 'QR de Verificación'
    
    def get_queryset(self, request):
        # Guardar request para usar en métodos readonly
        self.request = request
        return super().get_queryset(request)


@admin.register(AuditoriaFirmas)
class AuditoriaFirmasAdmin(admin.ModelAdmin):
    list_display = ['fecha', 'usuario', 'accion', 'documento_firmado', 'ip']
    list_filter = ['accion', 'fecha']
    search_fields = ['usuario__username', 'documento_firmado__documento__codigo', 'ip']
    readonly_fields = ['usuario', 'accion', 'documento_firmado', 'firma', 'fecha', 'ip', 'detalles_display']
    
    fieldsets = (
        ('Evento', {
            'fields': ('fecha', 'usuario', 'accion')
        }),
        ('Relacionado', {
            'fields': ('documento_firmado', 'firma')
        }),
        ('Trazabilidad', {
            'fields': ('ip', 'detalles_display')
        }),
    )
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def detalles_display(self, obj):
        if obj.detalles:
            import json
            detalles_json = json.dumps(obj.detalles, indent=2, ensure_ascii=False)
            return format_html(
                '<pre style="background: #f8f9fa; padding: 10px; border-radius: 4px; overflow-x: auto;">{}</pre>',
                detalles_json
            )
        return '-'
    detalles_display.short_description = 'Detalles'
