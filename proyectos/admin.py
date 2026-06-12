from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import Proyecto, Actividad, DocumentoProyecto
import json
from datetime import timedelta


class DocumentoProyectoInline(admin.TabularInline):
    """Inline para agregar documentos al proyecto como subgrid"""
    model = DocumentoProyecto
    extra = 1
    fields = ('documento', 'nota', 'ver_documento')
    readonly_fields = ('ver_documento',)
    autocomplete_fields = ('documento',)
    verbose_name = "Documento"
    verbose_name_plural = "Documentos del Proyecto"
    
    def ver_documento(self, obj):
        if obj.documento_id:
            return format_html(
                '<a href="/admin/documentos/documento/{}/change/" target="_blank" '
                'style="color: #2563eb;">📄 Ver</a>',
                obj.documento_id
            )
        return "-"
    ver_documento.short_description = "Acción"


class AvisoInline(admin.TabularInline):
    """Inline para ver avisos de mantenimiento vinculados al proyecto"""
    from mantenimiento.models import Aviso
    model = Aviso
    extra = 0
    fields = ('tipo', 'prioridad', 'estado', 'descripcion', 'solicitante', 'creado_en')
    readonly_fields = ('creado_en',)
    autocomplete_fields = ('solicitante',)
    show_change_link = True
    verbose_name = "Aviso de Mantenimiento"
    verbose_name_plural = "Avisos de Mantenimiento"


class ActividadInline(admin.TabularInline):
    model = Actividad
    extra = 1
    fields = ('nombre', 'estado', 'prioridad', 'asignado_a', 'fecha_inicio', 'fecha_fin', 'color', 'orden')
    autocomplete_fields = ('asignado_a',)
    ordering = ('orden', 'creado_en')


class AnalisisCostoInline(admin.TabularInline):
    from costos.models import AnalisisCostoUnitario
    model = AnalisisCostoUnitario
    extra = 0
    fields = ('codigo', 'nombre', 'unidad', 'estado', 'costo_total')
    readonly_fields = ('codigo', 'costo_total')
    show_change_link = True
    verbose_name = "ACU"
    verbose_name_plural = "Análisis de Costos Unitarios"

    def costo_total(self, obj):
        return obj.costo_total
    costo_total.short_description = "Costo Total"


class OrdenTrabajoInline(admin.TabularInline):
    from mantenimiento.models import OrdenTrabajo
    model = OrdenTrabajo
    extra = 1
    fields = ('codigo_de_orden', 'tipo', 'estado', 'prioridad', 'tecnico', 'inicio_programado', 'fin_programado', 'descripcion_corta')
    readonly_fields = ('codigo_de_orden',)
    autocomplete_fields = ('tecnico',)
    show_change_link = True
    verbose_name = "Orden de Trabajo"
    verbose_name_plural = "Órdenes de Trabajo"


@admin.register(Proyecto)
class ProyectoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'estado_badge', 'responsable', 'avance_bar', 'ver_cronograma', 'ver_repositorio_docs', 'total_docs', 'abrir_visores')
    list_filter = ('estado', 'responsable', 'ubicacion')
    search_fields = ('codigo', 'nombre', 'descripcion', 'visores__nombre')
    autocomplete_fields = ('responsable', 'ubicacion')
    readonly_fields = ('creado_en', 'actualizado_en', 'resumen_actividades', 'ver_cronograma_btn', 'ver_repositorio_docs_btn', 'visor_planos_dinamico', 'cronograma_interactivo')
    inlines = [ActividadInline, DocumentoProyectoInline, AvisoInline, AnalisisCostoInline, OrdenTrabajoInline]
    
    filter_horizontal = ('visores',)
    
    fieldsets = (
        ('Información General', {
            'fields': ('codigo', 'nombre', 'estado', 'responsable', 'ubicacion', 'descripcion', ('ver_cronograma_btn', 'ver_repositorio_docs_btn'))
        }),
        ('Planificación Interactiva (Gantt)', {
            'fields': ('cronograma_interactivo',),
            'description': 'Arrastre las barras para cambiar fechas o use el mouse para crear nuevas actividades.'
        }),
        ('Visualización en Planos (Dinámica)', {
            'fields': ('visor_planos_dinamico',),
            'description': 'Visualización interactiva de los planos asociados a este proyecto.'
        }),
        ('Configuración de Planos', {
            'fields': ('visores',),
            'classes': ('collapse',),
            'description': 'Gestione los visores que se mostrarán en la sección interactiva superior.'
        }),
        ('Notas y Sistema', {
            'fields': ('nota', 'creado_en', 'actualizado_en'),
            'classes': ('collapse',)
        }),
    )

    def cronograma_interactivo(self, obj):
        if not obj.pk:
            return "Guarde el proyecto para habilitar el cronograma."
        
        actividades = obj.actividades.all().order_by('orden')
        tasks = []
        predecesora_options_html = '<option value="">(Ninguna)</option>'
        
        for act in actividades:
            tasks.append({
                'id': str(act.id),
                'name': act.nombre,
                'start': act.fecha_inicio.isoformat() if act.fecha_inicio else (act.creado_en.date().isoformat()),
                'end': act.fecha_fin.isoformat() if act.fecha_fin else ((act.fecha_inicio or act.creado_en.date()) + timedelta(days=1)).isoformat(),
                'progress': 100 if act.estado == 'COMPLETADA' else 0,
                'dependencies': [str(act.predecesora.id)] if act.predecesora else [],
                'custom_class': f'gantt-item-{act.prioridad.lower()}'
            })
            predecesora_options_html += f'<option value="{act.id}">{act.nombre}</option>'
        
        tasks_json = json.dumps(tasks)
        create_url = reverse('proyectos:crear_actividad_api')
        update_url_pattern = reverse('proyectos:actualizar_actividad_api', args=[0]).replace('0/', '')
        standalone_url = reverse('proyectos:gantt_proyecto', args=[obj.id])

        # Generar lista de actividades para el sidebar
        sidebar_items_html = ""
        for act in actividades:
            sidebar_items_html += f"""
            <div class="sidebar-act-item" style="height: 30px; display: flex; align-items: center; padding: 0 10px; border-bottom: 1px solid #f1f5f9; font-size: 0.75rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; border-left: 3px solid {act.color}; box-sizing: border-box;">
                {act.nombre}
            </div>
            """

        html = f"""
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/frappe-gantt/0.6.1/frappe-gantt.css" />
        <script src="https://cdnjs.cloudflare.com/ajax/libs/frappe-gantt/0.6.1/frappe-gantt.min.js"></script>
        
        <div id="gantt-container" style="background: white; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden; margin-bottom: 20px; width: 100%;">
            <div id="gantt-header" style="padding: 15px; border-bottom: 1px solid #e2e8f0; display: flex; justify-content: space-between; align-items: center; background: #f8fafc;">
                <h3 style="margin: 0; font-size: 1rem;">Cronograma de Actividades</h3>
                <div style="display: flex; gap: 10px; align-items: center;">
                    <a href="{standalone_url}" target="_blank" class="view-btn" style="text-decoration: none; color: inherit; display: flex; align-items: center; gap: 5px;">
                        ↗️ Pantalla Completa
                    </a>
                    <button type="button" id="btn-link-mode" onclick="toggleLinkMode()" style="padding: 6px 14px; border-radius: 8px; border: 1px solid #cbd5e1; background: white; cursor: pointer; font-size: 0.85rem; font-weight: 600;">
                        🔗 Modo Vinculación: OFF
                    </button>
                    <button type="button" onclick="showCreateModal()" style="padding: 6px 14px; border-radius: 8px; border: none; background: #10b981; color: white; cursor: pointer; font-size: 0.85rem; font-weight: 600; transition: all 0.2s;">
                        + Nueva Actividad
                    </button>
                    <div class="view-buttons">
                        <button type="button" onclick="gantt.change_view_mode('Day')" class="view-btn">Día</button>
                        <button type="button" onclick="gantt.change_view_mode('Week')" class="view-btn active">Semana</button>
                        <button type="button" onclick="gantt.change_view_mode('Month')" class="view-btn">Mes</button>
                    </div>
                </div>
            </div>
            
            <div id="gantt-status" style="padding: 8px 15px; font-size: 0.8rem; background: #fffbeb; color: #92400e; border-bottom: 1px solid #fef3c7; display: none;">
                Seleccione la actividad predecesora...
            </div>
            
            <div id="gantt-main-split" style="display: flex; width: 100%; position: relative;">
                <div id="gantt-sidebar" style="width: 250px; background: #fff; border-right: 1px solid #e2e8f0; display: flex; flex-direction: column; flex-shrink: 0; z-index: 10; box-shadow: 2px 0 5px rgba(0,0,0,0.05);">
                    <div id="sidebar-header" style="padding: 12px; background: #f8fafc; border-bottom: 1px solid #e2e8f0; font-weight: 700; font-size: 0.75rem; color: #64748b; text-transform: uppercase; box-sizing: border-box; display: flex; align-items: flex-end;">Actividades</div>
                    <div id="sidebar-list" style="overflow-y: hidden; flex: 1;">
                        {sidebar_items_html}
                    </div>
                </div>
                <div id="gantt-canvas-container" style="flex: 1; overflow: hidden; position: relative;">
                    <div id="gantt-canvas" style="width: 100%; height: 100%; overflow: auto;"></div>
                </div>
            </div>
        </div>

        <!-- Modal para Nueva Actividad -->
        <div id="gantt-modal" style="display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); align-items: center; justify-content: center;">
            <div style="background: white; padding: 24px; border-radius: 12px; width: 450px; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1);">
                <h4 style="margin-top: 0;">Nueva Actividad</h4>
                <div style="margin-bottom: 15px;">
                    <label style="display: block; font-size: 0.85rem; margin-bottom: 5px;">Nombre</label>
                    <input type="text" id="modal-name" style="width: 100%; padding: 8px; border: 1px solid #e2e8f0; border-radius: 6px;">
                </div>
                <div style="display: flex; gap: 10px; margin-bottom: 15px;">
                    <div style="flex: 1;">
                        <label style="display: block; font-size: 0.85rem; margin-bottom: 5px;">Inicio</label>
                        <input type="date" id="modal-start" style="width: 100%; padding: 8px; border: 1px solid #e2e8f0; border-radius: 6px;">
                    </div>
                    <div style="flex: 1;">
                        <label style="display: block; font-size: 0.85rem; margin-bottom: 5px;">Fin</label>
                        <input type="date" id="modal-end" style="width: 100%; padding: 8px; border: 1px solid #e2e8f0; border-radius: 6px;">
                    </div>
                </div>
                <div style="margin-bottom: 20px;">
                    <label style="display: block; font-size: 0.85rem; margin-bottom: 5px;">Predecesora (Dependencia)</label>
                    <select id="modal-predecesora" style="width: 100%; padding: 8px; border: 1px solid #e2e8f0; border-radius: 6px;">
                        {predecesora_options_html}
                    </select>
                </div>
                <div style="display: flex; justify-content: flex-end; gap: 10px;">
                    <button type="button" onclick="hideModal()" style="padding: 8px 16px; border: 1px solid #e2e8f0; background: white; border-radius: 6px; cursor: pointer;">Cancelar</button>
                    <button type="button" onclick="createActivity()" style="padding: 8px 16px; border: none; background: #2563eb; color: white; border-radius: 6px; cursor: pointer; font-weight: 600;">Crear</button>
                </div>
            </div>
        </div>

        <style>
            #gantt-container .view-btn {{ 
                padding: 4px 12px; border: 1px solid #cbd5e1; background: white; border-radius: 6px; 
                cursor: pointer; font-size: 0.8rem; margin-left: 5px; 
            }}
            #gantt-container .view-btn.active {{ background: #2563eb; color: white; border-color: #2563eb; }}
            .frappe-gantt .bar-progress {{ fill: #3b82f6; }}
            .frappe-gantt .bar {{ fill: #94a3b8; }}
            .frappe-gantt .bar-label {{ font-size: 11px; font-weight: 600; }}
            .frappe-gantt .grid-header {{ background: #f8fafc; }}
            .gantt-target {{ min-height: 300px; }}
        </style>

        <script>
            let tasks = {tasks_json};
            let gantt;
            let isLinkingMode = false;
            let linkingSourceTask = null;

            function getCookie(name) {{
                let cookieValue = null;
                if (document.cookie && document.cookie !== '') {{
                    const cookies = document.cookie.split(';');
                    for (let i = 0; i < cookies.length; i++) {{
                        const cookie = cookies[i].trim();
                        if (cookie.substring(0, name.length + 1) === (name + '=')) {{
                            cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                            break;
                        }}
                    }}
                }}
                return cookieValue;
            }}

            document.addEventListener('DOMContentLoaded', function() {{
                const today = new Date().toISOString().split('T')[0];
                const modalStart = document.getElementById('modal-start');
                const modalEnd = document.getElementById('modal-end');
                if (modalStart) modalStart.value = today;
                if (modalEnd) modalEnd.value = today;

                initGantt();
            }});

            function initGantt() {{
                if (!tasks.length) {{
                    const canvas = document.getElementById('gantt-canvas');
                    if (canvas) canvas.innerHTML = '<div style="padding: 40px; text-align: center; color: #64748b;">No hay actividades con fechas. Use el botón superior para crear la primera.</div>';
                    return;
                }}

                gantt = new Gantt("#gantt-canvas", tasks, {{
                    on_date_change: function(task, start, end) {{
                        updateActivity(task.id, {{
                            fecha_inicio: start.toISOString().split('T')[0],
                            fecha_fin: end.toISOString().split('T')[0]
                        }});
                    }},
                    on_click: function(task) {{
                        if (isLinkingMode) {{
                            if (!linkingSourceTask) {{
                                linkingSourceTask = task;
                                document.getElementById('gantt-status').innerText = `Predecesora seleccionada: "${{task.name}}". Ahora click en la actividad siguiente...`;
                            }} else {{
                                if (linkingSourceTask.id === task.id) {{
                                    alert("Una actividad no puede ser su propia predecesora.");
                                    return;
                                }}
                                if (confirm(`¿Vincular "${{linkingSourceTask.name}}" como predecesora de "${{task.name}}"?`)) {{
                                    updateActivity(task.id, {{ predecesora_id: linkingSourceTask.id }}, true);
                                }}
                                toggleLinkMode();
                            }}
                        }}
                    }},
                    view_mode: 'Week',
                    language: 'es',
                    bar_height: 20,
                    padding: 10
                }});

                // Sync Sidebar Header Height with Gantt Grid Header
                setTimeout(() => {{
                    const ganttHeader = document.querySelector('.grid-header');
                    const sidebarHeader = document.getElementById('sidebar-header');
                    if (ganttHeader && sidebarHeader) {{
                        sidebarHeader.style.height = ganttHeader.getBoundingClientRect().height + 'px';
                    }}
                }}, 100);

                // Sync vertical scrolling between canvas and sidebar
                const canvas = document.getElementById('gantt-canvas');
                const sidebarList = document.getElementById('sidebar-list');
                
                canvas.addEventListener('scroll', () => {{
                    sidebarList.scrollTop = canvas.scrollTop;
                }});

                // Implement Drag-to-Scroll
                let isDragging = false;
                let startX;
                let scrollLeft;

                canvas.style.cursor = 'grab';

                canvas.addEventListener('mousedown', (e) => {{
                    // Solo si no estamos sobre una barra de tarea (que Frappe Gantt maneja)
                    if (e.target.classList.contains('grid-row') || e.target.classList.contains('grid-header') || e.target.tagName === 'svg') {{
                        isDragging = true;
                        canvas.style.cursor = 'grabbing';
                        startX = e.pageX - canvas.offsetLeft;
                        scrollLeft = canvas.scrollLeft;
                    }}
                }});

                canvas.addEventListener('mouseleave', () => {{
                    isDragging = false;
                    canvas.style.cursor = 'grab';
                }});

                canvas.addEventListener('mouseup', () => {{
                    isDragging = false;
                    canvas.style.cursor = 'grab';
                }});

                canvas.addEventListener('mousemove', (e) => {{
                    if (!isDragging) return;
                    e.preventDefault();
                    const x = e.pageX - canvas.offsetLeft;
                    const walk = (x - startX) * 2; // scroll-fast
                    canvas.scrollLeft = scrollLeft - walk;
                }});
            }}

            function toggleLinkMode() {{
                isLinkingMode = !isLinkingMode;
                const btn = document.getElementById('btn-link-mode');
                const status = document.getElementById('gantt-status');
                
                if (isLinkingMode) {{
                    btn.innerText = '🔗 Modo Vinculación: ON';
                    btn.style.background = '#fef3c7';
                    btn.style.borderColor = '#f59e0b';
                    status.style.display = 'block';
                    status.innerText = 'Seleccione la actividad predecesora...';
                    linkingSourceTask = null;
                }} else {{
                    btn.innerText = '🔗 Modo Vinculación: OFF';
                    btn.style.background = 'white';
                    btn.style.borderColor = '#cbd5e1';
                    status.style.display = 'none';
                    linkingSourceTask = null;
                }}
            }}

            function createActivity() {{
                const name = document.getElementById('modal-name').value;
                const start = document.getElementById('modal-start').value;
                const end = document.getElementById('modal-end').value;
                const predecesora_id = document.getElementById('modal-predecesora').value;

                if (!name) return alert('Ingrese un nombre');

                fetch('{create_url}', {{
                    method: 'POST',
                    headers: {{ 
                        'Content-Type': 'application/json', 
                        'X-CSRFToken': getCookie('csrftoken') 
                    }},
                    body: JSON.stringify({{
                        proyecto_id: {obj.pk},
                        nombre: name,
                        fecha_inicio: start,
                        fecha_fin: end,
                        predecesora_id: predecesora_id || null
                    }})
                }})
                .then(res => res.json())
                .then(data => {{
                    if (data.status === 'success') {{
                        location.reload(); 
                    }} else {{
                        alert('Error: ' + data.message);
                    }}
                }});
            }}

            function updateActivity(id, data, reload = false) {{
                fetch(`{update_url_pattern}${{id}}/`, {{
                    method: 'POST',
                    headers: {{ 
                        'Content-Type': 'application/json', 
                        'X-CSRFToken': getCookie('csrftoken') 
                    }},
                    body: JSON.stringify(data)
                }})
                .then(res => res.json())
                .then(data => {{
                    if (data.status === 'success') {{
                        if (reload) location.reload();
                        console.log('Actualizado');
                    }} else {{
                        alert('Error al actualizar: ' + data.message);
                    }}
                }});
            }}
        </script>
        """
        return mark_safe(html)
    cronograma_interactivo.short_description = "Cronograma Interactivo"

    def visor_planos_dinamico(self, obj):
        if not obj.pk or not obj.visores.exists():
            return mark_safe('<div style="padding: 20px; background: #f8fafc; border: 2px dashed #e2e8f0; border-radius: 8px; text-align: center; color: #94a3b8;">'
                               '<span style="font-size: 2rem; display: block; margin-bottom: 10px;">🗺️</span>'
                               'Asocie visores de planos en la sección de configuración para previsualizarlos aquí.</div>')
        
        visores = obj.visores.all()
        buttons_html = ""
        for i, v in enumerate(visores):
            active_class = "active-plan" if i == 0 else ""
            url = reverse('activos:visor_plano', args=[v.id])
            buttons_html += f'<button type="button" class="plan-chip {active_class}" onclick="changePlan(this, \'{url}\')" style="padding: 6px 14px; border-radius: 20px; border: 1px solid #cbd5e1; background: white; cursor: pointer; font-family: inherit; font-size: 0.8rem; font-weight: 500; margin-right: 8px; margin-bottom: 8px; transition: all 0.2s;">🗺️ {v.nombre}</button>'
        
        first_url = reverse('activos:visor_plano', args=[visores[0].id])
        
        html = f"""
        <div class="dynamic-visor-wrapper" style="display: flex; flex-direction: column; gap: 12px; margin-top: 10px; width: 100%;">
            <div class="plan-selector" style="display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between;">
                <div style="display: flex; flex-wrap: wrap;">
                    {buttons_html}
                </div>
                <button type="button" onclick="openPlanInNewWindow()" class="btn-new-window" style="padding: 6px 14px; border-radius: 20px; border: 1px solid #2563eb; background: #eff6ff; color: #2563eb; cursor: pointer; font-family: inherit; font-size: 0.8rem; font-weight: 600; display: flex; align-items: center; gap: 6px; transition: all 0.2s;">
                    <span>↗️ Abrir en Nueva Ventana</span>
                </button>
            </div>
            <iframe id="project-plan-iframe" src="{first_url}" style="width: 100%; height: 85vh; border: 1px solid #e2e8f0; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); background: white;" frameborder="0"></iframe>
        </div>
        <style>
            /* Romper el padding del fieldset para ganar espacio */
            .field-visor_planos_dinamico {{
                padding: 10px 0 !important;
            }}
            .field-visor_planos_dinamico .readonly {{
                width: 100%;
            }}
            .plan-chip.active-plan {{
                background: #2563eb !important;
                color: white !important;
                border-color: #2563eb !important;
                box-shadow: 0 4px 6px -1px rgba(37, 99, 235, 0.2);
            }}
            .plan-chip:hover:not(.active-plan) {{
                background: #f1f5f9 !important;
                border-color: #94a3b8 !important;
            }}
            .btn-new-window:hover {{
                background: #dbeafe !important;
                transform: translateY(-1px);
            }}
        </style>
        <script>
            function changePlan(btn, url) {{
                document.querySelectorAll('.plan-chip').forEach(b => b.classList.remove('active-plan'));
                btn.classList.add('active-plan');
                document.getElementById('project-plan-iframe').src = url;
            }}
            function openPlanInNewWindow() {{
                const url = document.getElementById('project-plan-iframe').src;
                window.open(url, '_blank');
            }}
        </script>
        """
        return mark_safe(html)
    visor_planos_dinamico.short_description = "Vista Previa de Planos"

    def ver_cronograma(self, obj):
        url = reverse('proyectos:cronograma', args=[obj.id])
        return format_html(
            '<a href="{}" target="_blank" style="background: #2563eb; color: white; '
            'padding: 4px 10px; border-radius: 6px; text-decoration: none; font-weight: 600;">'
            '📅 Ver Cronograma</a>',
            url
        )
    ver_cronograma.short_description = 'Cronograma'
    
    def ver_repositorio_docs(self, obj):
        if not obj.pk: return "-"
        url = reverse('proyectos:repositorio_documentos', args=[obj.id])
        return format_html(
            '<a href="{}" target="_blank" style="background: #4f46e5; color: white; '
            'padding: 4px 10px; border-radius: 6px; text-decoration: none; font-weight: 600;">'
            '📁 Consultar Docs</a>',
            url
        )
    ver_repositorio_docs.short_description = 'Repositorio'

    def ver_repositorio_docs_btn(self, obj):
        if not obj.id: return "-"
        url = reverse('proyectos:repositorio_documentos', args=[obj.id])
        return format_html(
            '<a href="{}" target="_blank" class="button" style="background: #4f46e5; color: white;">'
            '📁 Abrir Repositorio de Documentos del Proyecto</a>',
            url
        )
    ver_repositorio_docs_btn.short_description = 'Repositorio Visual'

    def ver_cronograma_btn(self, obj):
        if not obj.id: return "-"
        url = reverse('proyectos:cronograma', args=[obj.id])
        return format_html(
            '<a href="{}" target="_blank" class="button" style="background: #2563eb; color: white;">'
            '📅 Abrir Cronograma Semanal (Visual)</a>',
            url
        )
    ver_cronograma_btn.short_description = 'Acción Visual'
    def abrir_visores(self, obj):
        links = []
        if obj.pk:
            for v in obj.visores.all():
                url = reverse('activos:visor_plano', args=[v.id])
                links.append(f'<a href="{url}" target="_blank" class="button" style="background: #10b981; color: white; padding: 2px 8px; border-radius: 4px; text-decoration: none; margin-right: 4px; font-size: 0.75rem;">{v.nombre}</a>')
        return format_html("".join(links)) if links else "-"
    
    abrir_visores.short_description = "Ver en Planos"
    
    def total_docs(self, obj):
        count = obj.documentos_proyecto.count()
        if count == 0:
            return format_html('<span style="color: #94a3b8;">0</span>')
        return format_html('<span style="color: #2563eb; font-weight: 600;">{}</span>', count)
    total_docs.short_description = 'Docs'
    
    def estado_badge(self, obj):
        colores = {
            'PLANIFICACION': '#3b82f6',
            'EJECUCION': '#10b981',
            'PAUSADO': '#f59e0b',
            'COMPLETADO': '#6366f1',
            'CANCELADO': '#ef4444',
        }
        color = colores.get(obj.estado, '#64748b')
        return format_html(
            '<span style="background: {}; color: white; padding: 4px 10px; border-radius: 12px; '
            'font-size: 0.75rem; font-weight: 600;">{}</span>',
            color, obj.get_estado_display()
        )
    estado_badge.short_description = 'Estado'
    
    def avance_bar(self, obj):
        pct = obj.porcentaje_avance
        color = '#10b981' if pct == 100 else '#3b82f6'
        return format_html(
            '<div style="width: 100px; background: #e2e8f0; border-radius: 8px; overflow: hidden;">'
            '<div style="width: {}%; height: 8px; background: {};"></div>'
            '</div>'
            '<span style="font-size: 0.7rem; color: #64748b; margin-left: 5px;">{}/{}</span>',
            pct, color, obj.actividades_completadas, obj.total_actividades
        )
    avance_bar.short_description = 'Avance'
    
    def resumen_actividades(self, obj):
        actividades = obj.actividades.all()[:10]
        if not actividades:
            return format_html('<span style="color: #94a3b8;">Sin actividades registradas</span>')
        
        html = '<div style="display: flex; flex-direction: column; gap: 8px;">'
        for act in actividades:
            estado_color = {
                'PENDIENTE': '#94a3b8',
                'EN_PROGRESO': '#3b82f6',
                'COMPLETADA': '#10b981',
                'BLOQUEADA': '#ef4444',
            }.get(act.estado, '#64748b')
            
            html += f'''
            <div style="display: flex; align-items: center; gap: 10px; padding: 8px; 
                        background: #f8fafc; border-radius: 6px; border-left: 3px solid {act.color};">
                <span style="width: 8px; height: 8px; border-radius: 50%; background: {estado_color};"></span>
                <span style="flex: 1; font-weight: 500;">{act.nombre}</span>
                <span style="font-size: 0.75rem; color: #64748b;">{act.get_estado_display()}</span>
            </div>
            '''
        html += '</div>'
        return format_html(html)
    resumen_actividades.short_description = 'Actividades Recientes'


@admin.register(Actividad)
class ActividadAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'proyecto_link', 'estado_badge', 'prioridad_badge', 'asignado_a', 'fecha_fin')
    list_filter = ('estado', 'prioridad', 'proyecto', 'asignado_a')
    search_fields = ('nombre', 'descripcion', 'proyecto__codigo', 'proyecto__nombre')
    autocomplete_fields = ('proyecto', 'asignado_a')
    list_select_related = ('proyecto', 'asignado_a')
    
    fieldsets = (
        ('Información', {
            'fields': ('proyecto', 'nombre', 'descripcion')
        }),
        ('Estado y Prioridad', {
            'fields': ('estado', 'prioridad', 'color')
        }),
        ('Planificación', {
            'fields': ('fecha_inicio', 'fecha_fin', 'asignado_a', 'orden')
        }),
    )
    
    def proyecto_link(self, obj):
        return format_html(
            '<a href="/admin/proyectos/proyecto/{}/change/" style="color: #2563eb;">{}</a>',
            obj.proyecto.id, obj.proyecto.codigo
        )
    proyecto_link.short_description = 'Proyecto'
    
    def estado_badge(self, obj):
        colores = {
            'PENDIENTE': '#94a3b8',
            'EN_PROGRESO': '#3b82f6',
            'COMPLETADA': '#10b981',
            'BLOQUEADA': '#ef4444',
        }
        color = colores.get(obj.estado, '#64748b')
        return format_html(
            '<span style="background: {}20; color: {}; padding: 3px 8px; border-radius: 12px; '
            'font-size: 0.75rem; font-weight: 600;">{}</span>',
            color, color, obj.get_estado_display()
        )
    estado_badge.short_description = 'Estado'
    
    def prioridad_badge(self, obj):
        colores = {
            'BAJA': '#10b981',
            'MEDIA': '#3b82f6',
            'ALTA': '#f59e0b',
            'CRITICA': '#ef4444',
        }
        color = colores.get(obj.prioridad, '#64748b')
        return format_html(
            '<span style="color: {}; font-weight: 600;">{}</span>',
            color, obj.get_prioridad_display()
        )
    prioridad_badge.short_description = 'Prioridad'
