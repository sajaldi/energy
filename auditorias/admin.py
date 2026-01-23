from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import Auditoria, ResultadoAuditoria

class ResultadoAuditoriaInline(admin.TabularInline):
    model = ResultadoAuditoria
    extra = 0
    fields = ('activo', 'estado', 'get_ubicacion_esperada', 'get_ubicacion_encontrada', 'fecha_escaneo')
    readonly_fields = ('get_ubicacion_esperada', 'get_ubicacion_encontrada', 'fecha_escaneo')
    autocomplete_fields = ['activo']

    def get_ubicacion_esperada(self, obj):
        return obj.ubicacion_esperada.ruta_completa if obj.ubicacion_esperada else "---"
    get_ubicacion_esperada.short_description = "Ubicación Esperada"

    def get_ubicacion_encontrada(self, obj):
        return obj.ubicacion_encontrada.ruta_completa if obj.ubicacion_encontrada else "---"
    get_ubicacion_encontrada.short_description = "Ubicación Encontrada"

@admin.register(Auditoria)
class AuditoriaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'estado', 'fecha_inicio', 'creado_por', 'ir_a_escanear')
    list_filter = ('estado', 'creado_por')
    search_fields = ('nombre',)
    autocomplete_fields = ['ubicaciones', 'categorias']
    inlines = [ResultadoAuditoriaInline]
    readonly_fields = ('control_panel',)

    def control_panel(self, obj):
        if not obj.id: return "Guarde la auditoría para habilitar controles."
        
        init_url = reverse('auditorias:api_inicializar', args=[obj.id])
        exec_url = reverse('auditorias:ejecutar', args=[obj.id])
        
        html = f"""
            <div style="background: #f8fafc; padding: 20px; border-radius: 12px; border: 1px solid #e2e8f0; display: flex; align-items: center; gap: 15px;">
                <div style="flex: 1;">
                    <h4 style="margin: 0 0 5px 0;">Panel de Control</h4>
                    <p style="margin: 0; font-size: 0.85rem; color: #64748b;">Inicialice el listado de activos esperados antes de empezar o vaya directo al escáner.</p>
                </div>
                <button type="button" onclick="confirmInit('{init_url}')" class="button" 
                    style="background: #059669; color: white; border: none; padding: 10px 20px; font-weight: bold; border-radius: 8px; cursor: pointer; height: auto;">
                    1. Inicializar Listado
                </button>
                <a href="{exec_url}" class="button" target="_blank"
                    style="background: #2563eb; color: white; border: none; padding: 10px 20px; font-weight: bold; border-radius: 8px; text-decoration: none; display: inline-block;">
                    2. Abrir Escáner de Auditoría
                </a>
                <button type="button" onclick="confirmFinalize('{reverse('auditorias:api_finalizar', args=[obj.id])}')" class="button"
                    style="background: #ef4444; color: white; border: none; padding: 10px 20px; font-weight: bold; border-radius: 8px; cursor: pointer; height: auto;">
                    3. Finalizar Auditoría
                </button>
            </div>
            <script>
                function confirmInit(url) {{
                    if (confirm('¿Estás seguro de inicializar la auditoría? Esto generará los registros pendientes para todos los activos en el alcance seleccionado.')) {{
                        fetch(url, {{
                            method: 'POST',
                            headers: {{ 'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value }}
                        }})
                        .then(r => r.json())
                        .then(data => {{
                            if (data.status === 'success') {{
                                alert(data.message);
                                window.location.reload();
                            }} else {{
                                alert('Error: ' + data.error);
                            }}
                        }});
                    }}
                }}
                function confirmFinalize(url) {{
                    if (confirm('¿Estás seguro de FINALIZAR la auditoría? Los equipos no encontrados se marcarán como EXTRAVIADOS y no se podrán realizar más escaneos.')) {{
                        fetch(url, {{
                            method: 'POST',
                            headers: {{ 'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value }}
                        }})
                        .then(r => r.json())
                        .then(data => {{
                            if (data.status === 'success') {{
                                alert(data.message);
                                window.location.reload();
                            }} else {{
                                alert('Error: ' + data.error);
                            }}
                        }});
                    }}
                }}
            </script>
        """
        return format_html(html)
    
    control_panel.short_description = "Acciones Rápidas"

    def ir_a_escanear(self, obj):
        if not obj.id: return "-"
        url = reverse('auditorias:ejecutar', args=[obj.id])
        return format_html(f'<a href="{url}" class="button" target="_blank" style="background: #2563eb; color: white; padding: 4px 10px; border-radius: 4px; text-decoration: none;">Abrir Escáner</a>')
    
    ir_a_escanear.short_description = "Escáner"

@admin.register(ResultadoAuditoria)
class ResultadoAuditoriaAdmin(admin.ModelAdmin):
    list_display = ('auditoria', 'activo', 'estado', 'get_ubicacion_esperada', 'get_ubicacion_encontrada', 'fecha_escaneo')
    list_filter = ('estado', 'auditoria')
    search_fields = ('activo__nombre', 'activo__codigo_interno')
    autocomplete_fields = ['auditoria', 'activo', 'ubicacion_esperada', 'ubicacion_encontrada']

    def get_ubicacion_esperada(self, obj):
        return obj.ubicacion_esperada.ruta_completa if obj.ubicacion_esperada else "---"
    get_ubicacion_esperada.short_description = "Ubicación Esperada"

    def get_ubicacion_encontrada(self, obj):
        return obj.ubicacion_encontrada.ruta_completa if obj.ubicacion_encontrada else "---"
    get_ubicacion_encontrada.short_description = "Ubicación Encontrada"
    actions = ['sincronizar_ubicacion']

    @admin.action(description="Sincronizar ubicación actual del activo con el hallazgo")
    def sincronizar_ubicacion(self, request, queryset):
        success_count = 0
        for res in queryset:
            if res.ubicacion_encontrada and res.activo:
                res.activo.ubicacion = res.ubicacion_encontrada
                res.activo.save()
                
                # Registrar trazabilidad
                from django.utils import timezone
                res.sincronizado = True
                res.sincronizado_por = request.user
                res.fecha_sincronizacion = timezone.now()
                res.save()
                
                success_count += 1
        
        self.message_user(request, f"Se han actualizado las ubicaciones de {success_count} activos conforme a los resultados de auditoría.")
