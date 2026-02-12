
# --- AVISO ADMIN WHATSAPP ---

@admin.register(Aviso)
class AvisoAdmin(admin.ModelAdmin):
    list_per_page = 50
    list_display = ('id', 'descripcion_corta', 'prioridad', 'estado', 'ubicacion', 'activo', 'solicitante', 'creado_en', 'enviar_whatsapp_button')
    list_filter = ('estado', 'prioridad', 'tipo')
    search_fields = ('descripcion', 'ubicacion__nombre', 'activo__nombre')
    autocomplete_fields = ('activo', 'ubicacion', 'falla', 'solicitante')
    
    def descripcion_corta(self, obj):
        return obj.descripcion[:50] + '...' if len(obj.descripcion) > 50 else obj.descripcion
    descripcion_corta.short_description = "Descripción"

    def enviar_whatsapp_button(self, obj):
        from django.urls import reverse
        from django.utils.safestring import mark_safe
        if not obj.id: return '-'
        # Usamos una URL personalizada dentro del admin
        url = reverse('admin:aviso_enviar_whatsapp', args=[obj.id])
        return mark_safe(f'<a class="button" href="{url}" style="background-color: #25D366; color: white; border-radius: 4px; padding: 5px 10px; font-weight: bold; text-decoration: none;">📱 Enviar WA</a>')
    enviar_whatsapp_button.short_description = 'WhatsApp'
    enviar_whatsapp_button.allow_tags = True
    
    def get_urls(self):
        urls = super().get_urls()
        from django.urls import path
        custom_urls = [
            path('enviar-whatsapp/<int:aviso_id>/', self.admin_site.admin_view(self.enviar_whatsapp_view), name='aviso_enviar_whatsapp'),
        ]
        return custom_urls + urls

    def enviar_whatsapp_view(self, request, aviso_id):
        import requests
        from django.contrib import messages
        from django.http import HttpResponseRedirect
        from django.shortcuts import get_object_or_404
        
        aviso = get_object_or_404(Aviso, id=aviso_id)
            
        texto = f"*🚨 AVISO #{aviso.id} - Energy ERP*\n"
        texto += f"🗓️ *Fecha:* {aviso.creado_en.strftime('%d/%m/%Y %H:%M')}\n"
        texto += f"📍 *Ubicación:* {str(aviso.ubicacion)}\n"
        if aviso.activo:
            texto += f"⚙️ *Activo:* {str(aviso.activo)}\n"
        if aviso.falla:
            texto += f"🔧 *Falla:* {str(aviso.falla)}\n"
        
        emoji_p = "🔴" if aviso.prioridad == 'CRITICA' else ("🟠" if aviso.prioridad == 'ALTA' else "🟡")
        texto += f"{emoji_p} *Prioridad:* {aviso.get_prioridad_display()}\n"
        texto += f"📝 *Descripción:* {aviso.descripcion}\n"
        solicita = aviso.solicitante.username if aviso.solicitante else 'N/A'
        texto += f"👤 *Solicitante:* {solicita}\n"
        texto += f"📊 *Estado:* {aviso.get_estado_display()}"
        
        try:
            # Enviamos al servicio local de Node
            resp = requests.post('http://localhost:3005/send-message', json={
                'number': '50488113195',
                'message': texto
            }, timeout=5)
            
            if resp.status_code == 200:
                self.message_user(request, f"✅ Mensaje enviado correctamente al +50488113195 para Aviso #{aviso.id}")
            else:
                self.message_user(request, f"❌ Error del servicio WA: {resp.text}", level=messages.ERROR)
        except Exception as e:
            self.message_user(request, f"❌ Error conectando con servicio WA (¿está corriendo node index.js?): {str(e)}", level=messages.ERROR)
            
        return HttpResponseRedirect(request.META.get('HTTP_REFERER', '../'))
