from django.contrib import admin
from django.utils.html import format_html, mark_safe
from django.urls import reverse
from .models import Documento, Carpeta, Revision, TipoDocumento, Disciplina, MetadatoConfig, MetadatoValor, ComentarioDocumento, N8nChatHistory, Biblioteca, ComentarioBiblioteca, GroqApiKey, DocumentoShare
import json

from django.forms import TextInput, Textarea
from django import forms
from django.db import models

from import_export.admin import ImportExportModelAdmin
from .resources import ComentarioDocumentoResource
from .views_import import import_comentarios_background, import_comentarios_process, import_comentarios_progress, download_template
from plantillas.admin import TemplateExportMixin

class ComentarioDocumentoInline(admin.TabularInline):
    model = ComentarioDocumento
    extra = 0
    fields = ('usuario', 'texto', 'pagina', 'resuelto')
    readonly_fields = ('usuario', 'texto', 'pagina')
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False # Se agregan desde el visor

class RevisionInline(admin.TabularInline):
    model = Revision
    extra = 1
    # Campos minimalistas para la lista: Versión, Archivo, Comentario (opcional), Fecha
    fields = ('revision', 'archivo', 'fecha_revision', 'comentarios')
    readonly_fields = ('fecha_revision',) 
    
    # Reducir tamaño del campo comentarios para que parezca una fila de tabla limpia
    formfield_overrides = {
        models.CharField: {'widget': TextInput(attrs={'size': '10'})},
        models.TextField: {'widget': Textarea(attrs={'rows': 1, 'cols': 40, 'style': 'resize:none;'})},
    }

    def has_add_permission(self, request, obj=None):
        return True

    def has_change_permission(self, request, obj=None):
        return True

class MetadatoValorForm(forms.ModelForm):
    class Meta:
        model = MetadatoValor
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Cambiar el widget dinámicamente según la configuración del metadato
        if hasattr(self, 'instance') and self.instance.pk and self.instance.config:
            config = self.instance.config
            tipo = config.tipo_campo
            
            # Configurar valor según tipo
            if tipo == 'FECHA':
                self.fields['valor'].widget = forms.DateInput(attrs={'type': 'date', 'class': 'vDateField'})
            elif tipo == 'HORA':
                self.fields['valor'].widget = forms.TimeInput(attrs={'type': 'time', 'class': 'vTimeField'})
            elif tipo == 'NUMERO':
                self.fields['valor'].widget = forms.NumberInput(attrs={'style': 'width: 120px;'})
            elif tipo == 'EMAIL':
                self.fields['valor'].widget = forms.EmailInput(attrs={'style': 'width: 300px;'})
            elif tipo == 'RELACION':
                # Si es una relación, ocultamos el campo 'valor' de texto
                self.fields['valor'].widget = forms.HiddenInput()
                self.fields['valor'].required = False
                
                # Configuramos el selector de objeto dinámico
                if config.modelo_relativo:
                    model_class = config.modelo_relativo.model_class()
                    if model_class:
                        # Cargar objetos del modelo vinculado
                        objetos = model_class.objects.all()[:1000]
                        
                        # Determinar qué campo mostrar
                        display_field = config.campo_visualizacion
                        choices = []
                        for obj in objetos:
                            try:
                                label = getattr(obj, display_field) if display_field else str(obj)
                            except AttributeError:
                                label = str(obj)
                            choices.append((obj.pk, label))

                        self.fields['object_id'] = forms.ChoiceField(
                            choices=[('', '---------')] + choices,
                            label="Seleccionar " + config.etiqueta,
                            required=config.requerido
                        )
                        # Forzamos el ContentType al del modelo configurado
                        self.fields['content_type'].initial = config.modelo_relativo
                        self.fields['content_type'].widget = forms.HiddenInput()
            else:
                self.fields['valor'].widget = forms.TextInput(attrs={'style': 'width: 90%; min-width: 400px;'})
        else:
            self.fields['valor'].widget = forms.TextInput(attrs={'style': 'width: 90%;'})

class MetadatoValorInline(admin.TabularInline):
    model = MetadatoValor
    form = MetadatoValorForm
    extra = 0
    fields = ('get_etiqueta', 'valor', 'object_id', 'content_type', 'objeto_vinculado')
    readonly_fields = ('get_etiqueta', 'objeto_vinculado')
    
    def get_etiqueta(self, obj):
        return obj.config.etiqueta if obj.config else "-"
    get_etiqueta.short_description = "Campo"

    def has_add_permission(self, request, obj=None):
        return False # Se crean dinámicamente

class DocumentoShareInlineForm(forms.ModelForm):
    class Meta:
        model = DocumentoShare
        fields = ('tipo', 'compartido_a_usuario', 'compartido_a_grupo', 'puede_ver', 'puede_editar', 'puede_eliminar', 'puede_compartir', 'expira_en', 'nota')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['compartido_a_usuario'].required = False
        self.fields['compartido_a_grupo'].required = False
        self.fields['expira_en'].widget = forms.DateTimeInput(attrs={'type': 'datetime-local'})

class DocumentoShareInline(admin.TabularInline):
    model = DocumentoShare
    form = DocumentoShareInlineForm
    extra = 0
    fields = ('tipo', 'compartido_a_usuario', 'compartido_a_grupo', 'puede_ver', 'puede_editar', 'puede_eliminar', 'puede_compartir', 'expira_en', 'nota', 'esta_vigente')
    readonly_fields = ('esta_vigente',)
    
    def esta_vigente(self, obj):
        if not obj.pk:
            return "-"
        vigente = obj.esta_vigente()
        if vigente:
            return format_html('<span style="color: #10b981; font-weight: bold;">✓ Vigente</span>')
        return format_html('<span style="color: #ef4444; font-weight: bold;">✗ Expirado</span>')
    esta_vigente.short_description = "Estado"
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.compartido_por = request.user
        super().save_model(request, obj, form, change)
    
    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for instance in instances:
            if not instance.pk:
                instance.compartido_por = request.user
            instance.save()
        formset.save_m2m()

@admin.register(Documento)
class DocumentoAdmin(TemplateExportMixin, admin.ModelAdmin):
    list_display = ('codigo', 'titulo', 'tipo_documento', 'estado_actual', 'get_vectorizado_status', 'ver_en_mapa_button', 'fecha_inicio', 'vista_rapida_button', 'trazabilidad_link')
    list_filter = ('tipo_documento', 'disciplina', 'estado_actual', 'fecha_inicio', 'departamentos')
    search_fields = ('codigo', 'titulo', 'revisiones__comentarios')
    filter_horizontal = ('activos', 'ubicaciones', 'departamentos')

    def get_respuesta_a_codigo(self, obj):
        return obj.respuesta_a.codigo if obj.respuesta_a else "-"
    get_respuesta_a_codigo.short_description = "Responde a"

    inlines = [MetadatoValorInline, ComentarioDocumentoInline, RevisionInline]
    autocomplete_fields = ('activos', 'ubicaciones')
    change_list_template = "admin/documentos/documento/change_list.html"
    
    def add_view(self, request, form_url='', extra_context=None):
        from django.shortcuts import redirect
        return redirect('documentos:documento_wizard')

    def get_queryset(self, request):
        """
        Filtrar documentos en el listado según seguridad a nivel de registro.
        
        - Superusuarios: ven todo.
        - Usuarios CON permiso Django (view_documento): ven documentos de su departamento,
          donde son responsable, o que tienen shares/departamentos que les apliquen.
        - Usuarios SIN permiso Django (acceden solo por shares): ven ÚNICAMENTE
          los documentos compartidos explícitamente con ellos.
        """
        qs = super().get_queryset(request)
        
        if request.user.is_superuser:
            return qs
        
        from django.db.models import Q, Exists, OuterRef
        from django.utils import timezone
        from core.models import PerfilUsuario
        
        now = timezone.now()
        user = request.user
        user_groups = user.groups.all()
        user_dept = getattr(user.perfil, 'departamento', None) if hasattr(user, 'perfil') else None
        
        # Shares vigentes base (no expirados)
        shares_vigentes = DocumentoShare.objects.filter(
            documento_id=OuterRef('pk'),
            puede_ver=True
        ).filter(
            Q(expira_en__isnull=True) | Q(expira_en__gt=now)
        )
        
        # Usuario SIN permiso Django al modelo: solo ve lo que le compartieron
        has_django_perm = user.has_perm('documentos.view_documento')
        
        if not has_django_perm:
            # Solo shares directos: público, usuario, o grupo
            tiene_share_publico = Exists(shares_vigentes.filter(tipo='publico'))
            tiene_share_usuario = Exists(shares_vigentes.filter(tipo='usuario', compartido_a_usuario=user))
            
            acceso_q = Q(responsable=user) | tiene_share_publico | tiene_share_usuario
            
            if user_groups.exists():
                tiene_share_grupo = Exists(
                    shares_vigentes.filter(tipo='grupo', compartido_a_grupo__in=user_groups)
                )
                acceso_q |= tiene_share_grupo
            
            return qs.filter(acceso_q).distinct()
        
        # Usuario CON permiso Django: lógica completa
        has_shares = Exists(
            DocumentoShare.objects.filter(documento_id=OuterRef('pk'))
        )
        has_departamentos = Exists(
            Documento.departamentos.through.objects.filter(documento_id=OuterRef('pk'))
        )
        
        # 1. Es responsable del documento
        es_responsable = Q(responsable=user)
        
        # 2. Sin restricciones (ni shares ni departamentos):
        #    Solo visible para usuarios del mismo departamento que el responsable
        if user_dept:
            mismos_dept_users = PerfilUsuario.objects.filter(
                departamento=user_dept
            ).values_list('usuario_id', flat=True)
            sin_restriccion_mismo_dept = (
                ~has_shares & ~has_departamentos & Q(responsable_id__in=mismos_dept_users)
            )
        else:
            sin_restriccion_mismo_dept = Q(pk__in=[])
        
        # 3. Shares vigentes
        tiene_share_publico = Exists(shares_vigentes.filter(tipo='publico'))
        tiene_share_usuario = Exists(shares_vigentes.filter(tipo='usuario', compartido_a_usuario=user))
        
        acceso_q = es_responsable | sin_restriccion_mismo_dept | tiene_share_publico | tiene_share_usuario
        
        # 4. Share por grupo
        if user_groups.exists():
            tiene_share_grupo = Exists(
                shares_vigentes.filter(tipo='grupo', compartido_a_grupo__in=user_groups)
            )
            acceso_q |= tiene_share_grupo
        
        # 5. Departamentos asignados explícitamente
        if user_dept:
            acceso_q |= Q(departamentos=user_dept)
        
        return qs.filter(acceso_q).distinct()

    def has_view_permission(self, request, obj=None):
        """
        Permite ver el módulo de documentos si el usuario tiene acceso
        a al menos un documento (via shares, departamento, o responsable).
        Django Admin requiere este permiso para mostrar el modelo en el sidebar.
        """
        # Si tiene el permiso estándar de Django, OK
        if super().has_view_permission(request, obj):
            return True
        # Si es un objeto específico, verificar acceso por share
        if obj is not None:
            return obj.user_has_access(request.user, permission='ver')
        # Para el listado: permitir si el usuario está autenticado (el queryset filtra)
        return request.user.is_authenticated

    def has_change_permission(self, request, obj=None):
        """
        Permite editar un documento si tiene share con puede_editar=True
        o el permiso estándar de Django.
        """
        if super().has_change_permission(request, obj):
            return True
        if obj is not None:
            return obj.user_has_access(request.user, permission='editar')
        # Para el listado general, permitir acceso (get_queryset filtra)
        return request.user.is_authenticated

    def has_module_permission(self, request):
        """
        Permite que el módulo 'Documentos' aparezca en el sidebar del admin
        para cualquier usuario autenticado. El filtrado real ocurre en get_queryset.
        """
        if super().has_module_permission(request):
            return True
        return request.user.is_authenticated

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'respuesta_a':
            # Obtener el ID del objeto actual desde la URL para excluirlo del dropdown
            object_id = request.resolver_match.kwargs.get('object_id')
            if object_id:
                kwargs['queryset'] = Documento.objects.exclude(pk=object_id)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    fieldsets = (
        ('Identificación', {
            'fields': (('codigo', 'titulo'), ('tipo_documento', 'disciplina'), ('respuesta_a', 'fecha_inicio'), 'trazabilidad_link')
        }),
        ('Estado y Herramientas', {
            'fields': (('estado_actual', 'ultima_revision'), ('vista_rapida_button', 'sync_metadatos_button', 'get_word_templates_buttons'))
        }),
        ('Inteligencia Artificial', {
            'fields': (('get_vectorizado_status', 'ver_en_mapa_button'), 'gestionar_bibliotecas_button'),
            'description': 'Vectorización, visualización 3D y gestión de bibliotecas del documento.'
        }),
        ('Seguridad y Acceso', {
            'fields': ('responsable', 'compartir_button', 'departamentos'),
            'description': 'El responsable siempre tiene acceso total. Si no hay comparticiones ni departamentos, solo el departamento del responsable puede ver el documento.'
        }),
        ('Relaciones', {
            'fields': ('activos', 'ubicaciones')
        }),
        ('Contenido para Búsqueda', {
            'fields': ('contenido_texto_display',),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('ultima_revision', 'gestionar_bibliotecas_button', 'vista_rapida_button', 'trazabilidad_link', 'ver_en_mapa_button', 'contenido_texto_display', 'get_word_templates_buttons', 'sync_metadatos_button', 'get_vectorizado_status', 'compartir_button') 

    def ver_en_mapa_button(self, obj):
        if not obj.pk:
            return "-"
        
        if obj.embedding is None:
            return mark_safe('<span style="color:#94a3b8; font-size:0.8rem;">(Sin vectorizar)</span>')
            
        url = reverse('documentos:documento_espacio_vectorial', args=[obj.id])
        return format_html(
            '<a class="button" href="{}" target="_blank" style="background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%); color: white; padding: 6px 12px; border-radius: 4px; text-decoration: none; font-weight: 700; font-size: 0.8rem; display: inline-block;">🧠 Ver en Espacio 3D</a>',
            url
        )
    ver_en_mapa_button.short_description = "Espacio Vectorial"

    def gestionar_bibliotecas_button(self, obj):
        if not obj.pk: return "-"
        
        return format_html(
            '''
            <button type="button" onclick="openBibliotecaModal({})" class="button" 
                    style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: white; padding: 6px 12px; border-radius: 4px; border: none; cursor: pointer; font-weight: 700; font-size: 0.8rem;">
                📚 Gestionar Bibliotecas
            </button>
            <div id="bib-modal-root"></div>
            
            <style>
                .bib-modal-overlay {{
                    position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                    background: rgba(0,0,0,0.5); backdrop-filter: blur(4px);
                    display: flex; align-items: center; justify-content: center;
                    z-index: 9999; opacity: 0; transition: opacity 0.3s ease;
                }}
                .bib-modal-content {{
                    background: #ffffff; width: 90%; max-width: 600px;
                    border-radius: 12px; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1);
                    overflow: hidden; transform: translateY(20px); transition: transform 0.3s ease;
                }}
                .bib-modal-header {{
                    padding: 20px; background: #f8fafc; border-bottom: 1px solid #e2e8f0;
                    display: flex; justify-content: space-between; align-items: center;
                }}
                .bib-modal-body {{
                    padding: 20px; max-height: 400px; overflow-y: auto;
                }}
                .bib-card {{
                    display: flex; align-items: center; justify-content: space-between;
                    padding: 12px; margin-bottom: 10px; border-radius: 8px;
                    border: 1px solid #e2e8f0; transition: all 0.2s;
                }}
                .bib-card:hover {{ border-color: #10b981; background: #f0fdf4; }}
                .bib-card.active {{ border-left: 4px solid #10b981; background: #f0fdf4; }}
                .bib-info b {{ display: block; color: #1e293b; }}
                .bib-info span {{ font-size: 0.75rem; color: #64748b; }}
                
                .bib-toggle {{
                    width: 44px; height: 24px; background: #cbd5e1; border-radius: 12px;
                    position: relative; cursor: pointer; transition: background 0.3s;
                }}
                .bib-toggle::after {{
                    content: ""; position: absolute; top: 2px; left: 2px;
                    width: 20px; height: 20px; background: white; border-radius: 50%;
                    transition: left 0.3s;
                }}
                .bib-toggle.active {{ background: #10b981; }}
                .bib-toggle.active::after {{ left: 22px; }}
            </style>
            
            <script>
                function openBibliotecaModal(docId) {{
                    const root = document.getElementById('bib-modal-root');
                    root.innerHTML = `
                        <div class="bib-modal-overlay" id="bib-overlay">
                            <div class="bib-modal-content">
                                <div class="bib-modal-header">
                                    <h3 style="margin:0; font-size:1.2rem;">📁 Bibliotecas Disponibles</h3>
                                    <button onclick="closeBibModal()" style="background:none; border:none; font-size:1.5rem; cursor:pointer;">&times;</button>
                                </div>
                                <div class="bib-modal-body" id="bib-list">
                                    <p style="text-align:center;">Cargando bibliotecas...</p>
                                </div>
                            </div>
                        </div>
                    `;
                    
                    setTimeout(() => {{
                        document.getElementById('bib-overlay').style.opacity = '1';
                        document.querySelector('.bib-modal-content').style.transform = 'translateY(0)';
                    }}, 10);
                    
                    fetchBibliotecas(docId);
                }}
                
                function closeBibModal() {{
                    const overlay = document.getElementById('bib-overlay');
                    overlay.style.opacity = '0';
                    document.querySelector('.bib-modal-content').style.transform = 'translateY(20px)';
                    setTimeout(() => overlay.remove(), 300);
                }}
                
                async function fetchBibliotecas(docId) {{
                    try {{
                        const res = await fetch(\`/documentos/api/bibliotecas/${{docId}}/\`);
                        const data = await res.json();
                        renderBibliotecas(docId, data.bibliotecas);
                    }} catch(e) {{
                        document.getElementById('bib-list').innerHTML = '<p style="color:red;">Error al cargar.</p>';
                    }}
                }}
                
                function renderBibliotecas(docId, bibliotecas) {{
                    const list = document.getElementById('bib-list');
                    if(bibliotecas.length === 0) {{
                        list.innerHTML = '<p style="text-align:center; color:#64748b;">No hay bibliotecas creadas.</p>';
                        return;
                    }}
                    
                    list.innerHTML = bibliotecas.map(b => `
                        <div class="bib-card ${{b.pertenece ? 'active' : ''}}">
                            <div class="bib-info">
                                <b>${{b.nombre}}</b>
                                <span>${{b.count}} documentos vinculados</span>
                            </div>
                            <div class="bib-toggle ${{b.pertenece ? 'active' : ''}}" 
                                 onclick="toggleBib(${{docId}}, ${{b.id}}, this)">
                            </div>
                        </div>
                    `).join('');
                }}
                
                async function toggleBib(docId, bibId, el) {{
                    el.style.opacity = '0.5';
                    el.style.pointerEvents = 'none';
                    try {{
                        const res = await fetch(\`/documentos/api/bibliotecas/toggle/${{docId}}/${{bibId}}/\`, {{
                            method: 'POST',
                            headers: {{ 'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value }}
                        }});
                        const data = await res.json();
                        el.classList.toggle('active', data.accion === 'agregado');
                        el.closest('.bib-card').classList.toggle('active', data.accion === 'agregado');
                        
                        // Actualizar contador
                        const span = el.closest('.bib-card').querySelector('span');
                        span.innerText = data.count + ' documentos vinculados';
                        
                    }} catch(e) {{
                        alert('Error al actualizar.');
                    }} finally {{
                        el.style.opacity = '1';
                        el.style.pointerEvents = 'auto';
                    }}
                }}
            </script>
            ''',
            obj.pk
        )
    gestionar_bibliotecas_button.short_description = "Bibliotecas"

    def compartir_button(self, obj):
        if not obj.pk:
            return "-"
        return format_html(
            '''
            <button type="button" onclick="openShareModal({})" class="button"
                    style="background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); color: white; padding: 8px 16px; border-radius: 6px; border: none; cursor: pointer; font-weight: 700; font-size: 0.9rem; box-shadow: 0 4px 6px -1px rgba(245, 158, 11, 0.3);">
                🔗 Compartir Documento
            </button>
            <div id="share-modal-root"></div>

            <style>
                #share-overlay {{
                    position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                    background: rgba(15, 23, 42, 0.65); backdrop-filter: blur(8px);
                    display: flex; align-items: center; justify-content: center;
                    z-index: 99999; opacity: 0; transition: opacity 0.3s ease;
                }}
                .share-modal {{
                    background: #fff; width: 95%; max-width: 700px; border-radius: 16px;
                    box-shadow: 0 25px 50px -12px rgba(0,0,0,0.25); overflow: hidden;
                    transform: translateY(30px) scale(0.98); transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
                    display: flex; flex-direction: column; max-height: 85vh;
                }}
                .share-header {{
                    padding: 20px 24px; background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%);
                    border-bottom: 1px solid #fde68a; display: flex; justify-content: space-between; align-items: center;
                }}
                .share-header h3 {{ margin: 0; font-size: 1.2rem; color: #92400e; }}
                .share-body {{ padding: 20px 24px; overflow-y: auto; flex-grow: 1; }}
                
                .share-form {{ background: #f8fafc; border-radius: 12px; padding: 16px; margin-bottom: 20px; border: 1px solid #e2e8f0; }}
                .share-form label {{ display: block; font-weight: 600; margin-bottom: 4px; font-size: 0.85rem; color: #475569; }}
                .share-form select, .share-form input {{
                    width: 100%; padding: 10px 12px; border: 2px solid #e2e8f0; border-radius: 8px;
                    font-size: 0.9rem; margin-bottom: 12px; outline: none; transition: border-color 0.2s;
                }}
                .share-form select:focus, .share-form input:focus {{ border-color: #f59e0b; }}
                .share-form .row {{ display: flex; gap: 12px; }}
                .share-form .row > div {{ flex: 1; }}
                
                .share-permisos {{ display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 12px; }}
                .share-permisos label {{
                    display: flex; align-items: center; gap: 6px; font-weight: 500;
                    cursor: pointer; font-size: 0.85rem; color: #334155;
                }}
                .share-permisos input[type="checkbox"] {{ width: auto; margin: 0; }}
                
                .share-btn-add {{
                    background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); color: white;
                    padding: 10px 20px; border: none; border-radius: 8px; cursor: pointer;
                    font-weight: 700; font-size: 0.9rem; transition: transform 0.2s;
                }}
                .share-btn-add:hover {{ transform: translateY(-1px); }}
                .share-btn-add:disabled {{ opacity: 0.5; cursor: not-allowed; transform: none; }}
                
                .share-list-title {{ font-weight: 700; color: #1e293b; margin-bottom: 12px; font-size: 1rem; }}
                
                .share-item {{
                    display: flex; align-items: center; justify-content: space-between;
                    padding: 12px 16px; margin-bottom: 8px; border-radius: 10px;
                    border: 1px solid #e2e8f0; background: #fff; transition: all 0.2s;
                }}
                .share-item:hover {{ border-color: #fbbf24; background: #fffbeb; }}
                .share-item-info {{ flex-grow: 1; }}
                .share-item-info b {{ display: block; color: #1e293b; font-size: 0.95rem; }}
                .share-item-info span {{ font-size: 0.75rem; color: #64748b; }}
                .share-item-perms {{ display: flex; gap: 6px; margin-right: 12px; }}
                .share-perm-badge {{
                    font-size: 0.7rem; padding: 2px 8px; border-radius: 99px; font-weight: 600;
                }}
                .share-perm-badge.active {{ background: #dcfce7; color: #166534; }}
                .share-perm-badge.inactive {{ background: #f1f5f9; color: #94a3b8; }}
                .share-btn-del {{
                    background: none; border: none; cursor: pointer; font-size: 1.2rem;
                    color: #94a3b8; transition: color 0.2s; padding: 4px 8px; border-radius: 6px;
                }}
                .share-btn-del:hover {{ color: #ef4444; background: #fef2f2; }}
                
                .share-empty {{ text-align: center; padding: 30px; color: #94a3b8; font-size: 0.9rem; }}
                .share-vigente {{ color: #10b981; font-weight: 700; }}
                .share-expirado {{ color: #ef4444; font-weight: 700; }}
            </style>

            <script>
            function openShareModal(docId) {{
                const root = document.getElementById('share-modal-root');
                root.innerHTML = `
                    <div id="share-overlay">
                        <div class="share-modal">
                            <div class="share-header">
                                <h3>🔗 Compartir Documento</h3>
                                <button type="button" onclick="closeShareModal()" style="background:none; border:none; font-size:1.5rem; cursor:pointer; color:#92400e;">&times;</button>
                            </div>
                            <div class="share-body">
                                <div class="share-form">
                                    <div class="row">
                                        <div>
                                            <label>Compartir con</label>
                                            <select id="share-tipo" onchange="shareTypeChanged()">
                                                <option value="usuario">Usuario Específico</option>
                                                <option value="grupo">Grupo</option>
                                                <option value="publico">Público (Todos)</option>
                                            </select>
                                        </div>
                                        <div id="share-target-container">
                                            <label id="share-target-label">Usuario</label>
                                            <select id="share-target"><option value="">Cargando...</option></select>
                                        </div>
                                    </div>
                                    <label>Permisos</label>
                                    <div class="share-permisos">
                                        <label><input type="checkbox" id="share-perm-ver" checked disabled> Ver</label>
                                        <label><input type="checkbox" id="share-perm-editar"> Editar</label>
                                        <label><input type="checkbox" id="share-perm-eliminar"> Eliminar</label>
                                        <label><input type="checkbox" id="share-perm-compartir"> Re-compartir</label>
                                    </div>
                                    <div class="row">
                                        <div>
                                            <label>Nota (opcional)</label>
                                            <input type="text" id="share-nota" placeholder="Motivo...">
                                        </div>
                                        <div>
                                            <label>Expira en (opcional)</label>
                                            <input type="datetime-local" id="share-expira">
                                        </div>
                                    </div>
                                    <button type="button" class="share-btn-add" id="share-btn-submit" onclick="submitShare(${{docId}})">
                                        + Compartir
                                    </button>
                                </div>
                                
                                <div class="share-list-title">Comparticiones Activas</div>
                                <div id="share-list">
                                    <div class="share-empty">Cargando...</div>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
                
                setTimeout(() => {{
                    document.getElementById('share-overlay').style.opacity = '1';
                    document.querySelector('.share-modal').style.transform = 'translateY(0) scale(1)';
                }}, 10);
                
                fetchShareData(docId);
            }}
            
            function closeShareModal() {{
                const overlay = document.getElementById('share-overlay');
                if (!overlay) return;
                overlay.style.opacity = '0';
                document.querySelector('.share-modal').style.transform = 'translateY(30px) scale(0.95)';
                setTimeout(() => overlay.remove(), 300);
            }}
            
            let _shareData = {{}};
            
            async function fetchShareData(docId) {{
                try {{
                    const res = await fetch('/documentos/api/shares/' + docId + '/');
                    _shareData = await res.json();
                    populateTargetSelect();
                    renderShareList(docId);
                }} catch(e) {{
                    document.getElementById('share-list').innerHTML = '<div class="share-empty" style="color:#ef4444;">Error al cargar datos.</div>';
                }}
            }}
            
            function shareTypeChanged() {{
                populateTargetSelect();
            }}
            
            function populateTargetSelect() {{
                const tipo = document.getElementById('share-tipo').value;
                const container = document.getElementById('share-target-container');
                const label = document.getElementById('share-target-label');
                const select = document.getElementById('share-target');
                
                if (tipo === 'publico') {{
                    container.style.display = 'none';
                    return;
                }}
                container.style.display = 'block';
                
                if (tipo === 'usuario') {{
                    label.textContent = 'Usuario';
                    select.innerHTML = '<option value="">-- Seleccionar --</option>' +
                        (_shareData.usuarios || []).map(u => `<option value="${{u.id}}">${{u.display}} (${{u.username}})</option>`).join('');
                }} else {{
                    label.textContent = 'Grupo';
                    select.innerHTML = '<option value="">-- Seleccionar --</option>' +
                        (_shareData.grupos || []).map(g => `<option value="${{g.id}}">${{g.name}}</option>`).join('');
                }}
            }}
            
            async function submitShare(docId) {{
                const btn = document.getElementById('share-btn-submit');
                btn.disabled = true;
                btn.textContent = 'Guardando...';
                
                const tipo = document.getElementById('share-tipo').value;
                const target = document.getElementById('share-target')?.value;
                
                const body = {{
                    tipo: tipo,
                    puede_ver: true,
                    puede_editar: document.getElementById('share-perm-editar').checked,
                    puede_eliminar: document.getElementById('share-perm-eliminar').checked,
                    puede_compartir: document.getElementById('share-perm-compartir').checked,
                    nota: document.getElementById('share-nota').value,
                    expira_en: document.getElementById('share-expira').value || null,
                }};
                
                if (tipo === 'usuario') body.usuario_id = target;
                if (tipo === 'grupo') body.grupo_id = target;
                
                try {{
                    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
                    const res = await fetch('/documentos/api/shares/create/' + docId + '/', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken }},
                        body: JSON.stringify(body)
                    }});
                    const data = await res.json();
                    
                    if (data.error) {{
                        alert(data.error);
                    }} else {{
                        // Recargar lista
                        await fetchShareData(docId);
                        // Limpiar form
                        document.getElementById('share-nota').value = '';
                        document.getElementById('share-expira').value = '';
                        document.getElementById('share-perm-editar').checked = false;
                        document.getElementById('share-perm-eliminar').checked = false;
                        document.getElementById('share-perm-compartir').checked = false;
                    }}
                }} catch(e) {{
                    alert('Error de red al compartir.');
                }} finally {{
                    btn.disabled = false;
                    btn.textContent = '+ Compartir';
                }}
            }}
            
            function renderShareList(docId) {{
                const list = document.getElementById('share-list');
                const shares = _shareData.shares || [];
                
                if (shares.length === 0) {{
                    list.innerHTML = '<div class="share-empty">🔒 Sin comparticiones. Solo el responsable y su departamento pueden ver este documento.</div>';
                    return;
                }}
                
                list.innerHTML = shares.map(s => `
                    <div class="share-item">
                        <div class="share-item-info">
                            <b>${{s.tipo === 'publico' ? '🌐' : s.tipo === 'grupo' ? '👥' : '👤'}} ${{s.destino}}</b>
                            <span>
                                Por ${{s.compartido_por}} · ${{s.creado_en}}
                                ${{s.nota ? ' · ' + s.nota : ''}}
                                ${{s.expira_en ? ' · <span class="' + (s.vigente ? 'share-vigente' : 'share-expirado') + '">' + (s.vigente ? '✓ Vigente' : '✗ Expirado') + '</span>' : ''}}
                            </span>
                        </div>
                        <div class="share-item-perms">
                            <span class="share-perm-badge ${{s.puede_ver ? 'active' : 'inactive'}}">Ver</span>
                            <span class="share-perm-badge ${{s.puede_editar ? 'active' : 'inactive'}}">Editar</span>
                            <span class="share-perm-badge ${{s.puede_compartir ? 'active' : 'inactive'}}">Compartir</span>
                        </div>
                        <button type="button" class="share-btn-del" onclick="deleteShare(${{s.id}}, ${{docId}})" title="Eliminar">🗑️</button>
                    </div>
                `).join('');
            }}
            
            async function deleteShare(shareId, docId) {{
                if (!confirm('¿Eliminar esta compartición?')) return;
                try {{
                    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
                    await fetch('/documentos/api/shares/delete/' + shareId + '/', {{
                        method: 'POST',
                        headers: {{ 'X-CSRFToken': csrfToken }}
                    }});
                    await fetchShareData(docId);
                }} catch(e) {{
                    alert('Error al eliminar.');
                }}
            }}
            </script>
            ''',
            obj.pk
        )
    compartir_button.short_description = "Compartir"

    def trazabilidad_link(self, obj):
        if not obj.pk: return "-"
        url = reverse('documentos:documento_trazabilidad', args=[obj.pk])
        return format_html(
            '<a class="button" href="{}" style="background: #0f172a; color: white; padding: 6px 12px; border-radius: 4px; text-decoration: none; font-weight: 700; font-size: 0.8rem;">🌳 Ver Trazabilidad</a>',
            url
        )
    trazabilidad_link.short_description = "Flujo / Trazabilidad"

    def vista_rapida_button(self, obj):
        if not obj.pk: return "-"
        url = reverse('documentos:visor_pines', args=[obj.pk])
        return format_html(
            '<a class="button" href="{}" target="_blank" style="background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); color: white; padding: 6px 12px; border-radius: 4px; text-decoration: none; font-weight: 700; font-size: 0.8rem; display: inline-block;">👁️ Vista Rápida</a>',
            url
        )
    vista_rapida_button.short_description = "Visor"

    def sync_metadatos_button(self, obj):
        if not obj.pk: return "-"
        url = reverse('documentos:documento_sync_metadatos', args=[obj.pk])
        return format_html(
            '<a class="button" href="{}" style="background: #0ea5e9; color: white; padding: 6px 12px; border-radius: 4px; text-decoration: none; font-weight: 700; font-size: 0.8rem;">⚙️ Sincronizar Campos</a>',
            url
        )
    sync_metadatos_button.short_description = "Metadatos"
    
    def contenido_texto_display(self, obj):
        if not obj.pk: return "-"
        
        texto = obj.contenido_texto or "Sin contenido extraído."
        
        return format_html(
            '''
            <div style="margin-bottom: 10px; display: flex; gap: 10px;">
                <button type="button" onclick="triggerExtraction({})" 
                        id="btn-extract-{}"
                        style="background: linear-gradient(135deg, #0ea5e9 0%, #0284c7 100%); color: white; padding: 8px 16px; border-radius: 6px; border: none; cursor: pointer; font-weight: 600; font-size: 0.9rem;">
                    ⚡ Extraer Texto con n8n
                </button>
                <button type="button" onclick="testN8nPing()" 
                        style="background: #64748b; color: white; padding: 8px 16px; border-radius: 6px; border: none; cursor: pointer; font-weight: 600; font-size: 0.9rem;">
                    📡 Test Ping
                </button>
            </div>
            <textarea readonly style="width: 100%; height: 150px; font-family: monospace; font-size: 0.85rem; padding: 10px; border: 1px solid #cbd5e1; border-radius: 4px; background: #f8fafc; color: #334155; resize: vertical;">{}</textarea>
            <script>
            function testN8nPing() {{
                if(!confirm('¿Enviar Ping de prueba a n8n?')) return;
                fetch('/documentos/api/test-n8n/', {{
                    method: 'POST',
                    headers: {{ 'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value }}
                }})
                .then(res => res.json())
                .then(data => alert('Respuesta n8n: ' + JSON.stringify(data)))
                .catch(err => alert('Error: ' + err));
            }}

            function triggerExtraction(docId) {{
                const btn = document.getElementById('btn-extract-' + docId);
                const originalText = btn.innerText;
                btn.innerText = "Enviando...";
                btn.disabled = true;
                
                fetch('/documentos/api/trigger-extraction/' + docId + '/', {{
                    method: 'POST',
                    headers: {{
                        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                    }}
                }})
                .then(res => res.json())
                .then(data => {{
                    if (data.error) {{
                        alert('Error: ' + data.error);
                        btn.innerText = originalText;
                        btn.disabled = false;
                    }} else {{
                        alert('Solicitud enviada a n8n. Recargue la página en unos segundos para ver el texto extraído.');
                        btn.innerText = "Enviado ✓";
                    }}
                }})
                .catch(err => {{
                    alert('Error de red: ' + err);
                    btn.innerText = originalText;
                    btn.disabled = false;
                }});
            }}
            </script>
            ''',
            obj.pk, obj.pk, texto
        )
    contenido_texto_display.short_description = "Contenido Texto"
    
    def save_formset(self, request, form, formset, change):
        # Asignar usuario automáticamente a las revisiones nuevas y shares
        instances = formset.save(commit=False)
        for instance in instances:
            if isinstance(instance, Revision) and not instance.pk:
                instance.creado_por = request.user
            elif isinstance(instance, DocumentoShare) and not instance.pk:
                instance.compartido_por = request.user
            instance.save()
        formset.save_m2m()

    def extraer_datos_button(self, obj):
        if not obj.pk: return "-"
        url = reverse('documentos:documento_reprocesar', args=[obj.pk])
        return format_html(
            '<a class="button" href="{}" style="background: #4f46e5; color: white; padding: 6px 12px; border-radius: 4px; text-decoration: none; font-weight: 700; font-size: 0.8rem;">🔍 Extraer Info</a>',
            url
        )
    extraer_datos_button.short_description = "Análisis"
    
    def get_ultima_revision_info(self, obj):
        if obj.ultima_revision:
            return format_html(
                '<b>Rev {}</b> <br> <small>{}</small>', 
                obj.ultima_revision.revision,
                obj.ultima_revision.fecha_revision
            )
        return "Sin Versión"
    get_ultima_revision_info.short_description = "Versión Actual"

    def get_extraccion_status(self, obj):
        if obj.ultima_revision:
            status = obj.ultima_revision.estado_extraccion
            color = {
                'PENDIENTE': '#64748b',
                'PROCESANDO': '#2563eb',
                'COMPLETADO': '#10b981',
                'ERROR': '#ef4444',
                'NO_APLICA': '#94a3b8'
            }.get(status, '#000')
            
            return format_html(
                '<span style="background: {}15; color: {}; padding: 2px 8px; border-radius: 12px; font-weight: 700; font-size: 0.75rem;">{}</span>',
                color, color, status
            )
        return "-"
    get_extraccion_status.short_description = "Extracción"
    
    def solicitar_firmas_link(self, obj):
        """Link para solicitar firmas para este documento"""
        from django.urls import reverse
        url = reverse('firmas:solicitar_firmas', args=[obj.pk])
        return format_html(
            '<a class="button" href="{}" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 8px 16px; border-radius: 6px; text-decoration: none; font-weight: 600;">🖊️ Solicitar Firmas</a>',
            url
        )
    solicitar_firmas_link.short_description = "Firmas"

    def get_vectorizado_status(self, obj):
        """Indica si el documento tiene embeddings generados o si está procesando"""
        from django.core.cache import cache
        status = cache.get(f"doc_ia_status_{obj.id}")
        
        if status == "PROCESANDO":
            return format_html(
                '<span id="ia-status-{0}" title="IA está trabajando..." style="font-size: 1.2rem; cursor: wait; animation: pulse 1s infinite;">🧠 ⏳</span>'
                '<style>@keyframes pulse {{ 0% {{ opacity: 1; }} 50% {{ opacity: 0.3; }} 100% {{ opacity: 1; }} }}</style>',
                obj.id
            )
            
        if obj.embedding is not None:
            return mark_safe('<span title="Vectorizado (IA Lista)" style="font-size: 1.2rem;">🧠 ✅</span>')
        
        # Botón para vectorizar si está pendiente
        return format_html(
            '<span id="ia-status-{0}" onclick="triggerAdminVectorize({0}, this)" title="Clic para vectorizar ahora" style="font-size: 1.2rem; cursor: pointer; transition: transform 0.2s; display: inline-block;" onmouseover="this.style.transform=\'scale(1.3)\'" onmouseout="this.style.transform=\'scale(1)\'">🧠 ⚪</span>'
            '<script>'
            'if(typeof triggerAdminVectorize === "undefined") {{'
            '  window.triggerAdminVectorize = function(id, el) {{'
            '    const originalHTML = el.innerHTML;'
            '    el.innerHTML = "🧠 ⏳";'
            '    el.style.animation = "pulse 1s infinite";'
            '    el.style.pointerEvents = "none";'
            '    fetch("/documentos/api/vectorize/" + id + "/", {{ method: "POST", headers: {{"X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]").value}} }})'
            '    .then(res => res.json())'
            '    .then(data => {{'
            '       if (data.status === "error") {{'
            '           if (data.message.includes("texto")) {{'
            '               el.innerHTML = "⚡ ⏳";'
            '               fetch("/documentos/api/trigger-extraction/" + id + "/", {{ method: "POST", headers: {{"X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]").value}} }})'
            '               .then(r => r.json()).then(d => {{'
            '                   alert("El documento no tenía texto. Se ha enviado a n8n para su extracción automática. Vuelve a intentar vectorizar en unos minutos.");'
            '                   el.innerHTML = "⚡ ⚪";'
            '                   el.style.animation = "none";'
            '                   el.style.pointerEvents = "auto";'
            '               }}).catch(e => {{'
            '                   alert("Error intentando extraer texto con n8n.");'
            '                   el.innerHTML = originalHTML;'
            '                   el.style.animation = "none";'
            '                   el.style.pointerEvents = "auto";'
            '               }});'
            '           }} else {{'
            '               alert("No se puede vectorizar: " + data.message);'
            '               el.innerHTML = originalHTML;'
            '               el.style.animation = "none";'
            '               el.style.pointerEvents = "auto";'
            '           }}'
            '       }} else {{'
            '           console.log("IA Task Started", data);'
            '           alert("Tarea iniciada: " + data.message);'
            '       }}'
            '    }}).catch(err => {{'
            '       alert("Error de red al intentar vectorizar.");'
            '       el.innerHTML = originalHTML;'
            '       el.style.animation = "none";'
            '       el.style.pointerEvents = "auto";'
            '    }});'
            '  }}'
            '}}'
            '</script>',
            obj.id
        )
    get_vectorizado_status.short_description = "IA"

class MetadatoConfigForm(forms.ModelForm):
    class Meta:
        model = MetadatoConfig
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Convertir campo_visualizacion en un Select con las opciones del modelo si existe
        if self.instance and self.instance.modelo_relativo:
            model_class = self.instance.modelo_relativo.model_class()
            if model_class:
                fields = []
                for f in model_class._meta.get_fields():
                    if not f.is_relation or f.many_to_one or f.one_to_one:
                        if hasattr(f, 'name') and not f.name.startswith('_'):
                            fields.append(f.name)
                
                sorted_fields = sorted(list(set(fields)))
                choices = [('', '---------')] + [(f, f) for f in sorted_fields]
                # Si el valor actual no está en la lista (ej: cambiado por error), lo agregamos
                current = self.initial.get('campo_visualizacion') or self.instance.campo_visualizacion
                if current and current not in sorted_fields:
                    choices.append((current, current))
                
                self.fields['campo_visualizacion'] = forms.ChoiceField(
                    choices=choices,
                    required=False,
                    label="Campo Visualización"
                )
        else:
            # Dropdown vacío por defecto si no hay modelo seleccionado
            self.fields['campo_visualizacion'] = forms.ChoiceField(
                choices=[('', '---------')],
                required=False,
                label="Campo Visualización"
            )

class MetadatoConfigInline(admin.TabularInline):
    model = MetadatoConfig
    form = MetadatoConfigForm
    extra = 1
    fields = ('nombre', 'etiqueta', 'tipo_campo', 'modelo_relativo', 'campo_visualizacion', 'descripcion', 'requerido', 'orden')
    
    class Media:
        js = ('admin/js/metadato_config_dynamic.js',)

@admin.register(TipoDocumento)
class TipoDocumentoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'codigo')
    inlines = [MetadatoConfigInline]

@admin.register(Disciplina)
class DisciplinaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'codigo')
    search_fields = ('nombre', 'codigo')

@admin.register(Revision)
class RevisionAdmin(admin.ModelAdmin):
    list_display = ('documento', 'revision', 'fecha_revision', 'creado_por', 'estado_extraccion', 'get_datos_preview')
    list_filter = ('fecha_revision', 'creado_por', 'estado_extraccion')
    search_fields = ('documento__codigo', 'datos_extraidos')
    date_hierarchy = 'fecha_revision'
    readonly_fields = ('datos_extraidos', 'estado_extraccion')
    change_list_template = "admin/documentos/revision/change_list.html"

    def get_datos_preview(self, obj):
        if obj.datos_extraidos:
            return format_html(
                '<pre style="max-width: 300px; max-height: 100px; overflow: auto; font-size: 0.7rem;">{}</pre>',
                json.dumps(obj.datos_extraidos, indent=2, ensure_ascii=False)
            )
        return "-"
    get_datos_preview.short_description = "Datos Extraídos"

@admin.register(ComentarioDocumento)
class ComentarioDocumentoAdmin(ImportExportModelAdmin):
    resource_class = ComentarioDocumentoResource
    change_list_template = "admin/documentos/comentariodocumento/change_list.html"
    
    list_display = ('documento', 'usuario', 'texto_resumen', 'pagina', 'creado_en', 'resuelto')
    list_filter = ('resuelto', 'creado_en', 'usuario')
    search_fields = ('documento__codigo', 'texto', 'usuario__username')
    readonly_fields = ('creado_en',)
    
    def texto_resumen(self, obj):
        return obj.texto[:50] + "..." if len(obj.texto) > 50 else obj.texto
    texto_resumen.short_description = "Comentario"

    def get_urls(self):
        urls = super().get_urls()
        from django.urls import path
        custom_urls = [
            path('import-background/', self.admin_site.admin_view(import_comentarios_background), name='documentos_comentariodocumento_import_background'),
            path('import-background/process/', self.admin_site.admin_view(import_comentarios_process), name='documentos_comentariodocumento_import_process'),
            path('import-background/progress/', self.admin_site.admin_view(import_comentarios_progress), name='documentos_comentariodocumento_import_progress'),
            path('import-background/template/', self.admin_site.admin_view(download_template), name='documentos_comentariodocumento_import_template'),
        ]
        return custom_urls + urls

@admin.register(N8nChatHistory)
class N8nChatHistoryAdmin(admin.ModelAdmin):
    list_display = ('session_id', 'usuario', 'mensaje_preview', 'respuesta_preview', 'timestamp', 'documento')
    list_filter = ('timestamp', 'usuario', 'modelo')
    search_fields = ('session_id', 'mensaje_usuario', 'respuesta_ia', 'usuario__username')
    readonly_fields = ('timestamp',)
    date_hierarchy = 'timestamp'
    
    def mensaje_preview(self, obj):
        return obj.mensaje_usuario[:50] + "..." if len(obj.mensaje_usuario) > 50 else obj.mensaje_usuario
    mensaje_preview.short_description = "Mensaje"
    
    def respuesta_preview(self, obj):
        return obj.respuesta_ia[:50] + "..." if len(obj.respuesta_ia) > 50 else obj.respuesta_ia
    respuesta_preview.short_description = "Respuesta"


class ComentarioBibliotecaInline(admin.TabularInline):
    model = ComentarioBiblioteca
    extra = 1
    fields = ('titulo', 'contenido', 'fecha')
    readonly_fields = ('fecha',)

@admin.register(Biblioteca)
class BibliotecaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'cantidad_documentos', 'get_progreso_ia', 'vectorize_button', 'gestionar_biblioteca_button', 'visualizar_biblioteca_link', 'creado_por', 'creado_en')
    list_filter = ('creado_en', 'actualizado_en')
    search_fields = ('nombre', 'descripcion', 'documentos__codigo', 'documentos__titulo')
    filter_horizontal = ('documentos',)
    readonly_fields = ('creado_en', 'actualizado_en', 'gestionar_biblioteca_button', 'get_progreso_ia')
    inlines = [ComentarioBibliotecaInline]

    def get_progreso_ia(self, obj):
        from django.core.cache import cache
        docs = obj.documentos.all()
        total = docs.count()
        if total == 0: return "-"
        
        vectorizados = docs.filter(embedding__isnull=False).count()
        porcentaje = int((vectorizados / total) * 100)
        
        # Verificar si alguno está procesando
        procesando = False
        for d in docs:
            if cache.get(f"doc_ia_status_{d.id}") == "PROCESANDO":
                procesando = True
                break
        
        color = "#10b981" if porcentaje == 100 else "#6366f1"
        if porcentaje == 0: color = "#94a3b8"
        if procesando: color = "#f59e0b" # Naranja para procesando
        
        label = f"{vectorizados} / {total} ({porcentaje}%)"
        if procesando: label += " - ⏳ Trabajando..."
        
        return format_html(
            '''
            <div style="width: 100px; background: #f1f5f9; border-radius: 10px; height: 8px; overflow: hidden; margin-top: 4px;">
                <div style="width: {}%; background: {}; height: 100%;"></div>
            </div>
            <small style="color: {}; font-weight: bold;">{}</small>
            ''',
            porcentaje, color, color if procesando else "#64748b", label
        )
    get_progreso_ia.short_description = "Progreso IA"

    fieldsets = (
        ('Información', {
            'fields': ('nombre', 'descripcion', 'gestionar_biblioteca_button')
        }),
        ('Documentos (Estándar)', {
            'fields': ('documentos',),
            'classes': ('collapse',),
            'description': 'Aquí puedes usar el selector estándar de Django.'
        }),
        ('Auditoría', {
            'fields': ('creado_por', 'creado_en', 'actualizado_en'),
            'classes': ('collapse',)
        }),
    )



    def visualizar_biblioteca_link(self, obj):
        if not obj.pk: return "-"
        url = f"/documentos/biblioteca/visualizar/{obj.pk}/"
        return mark_safe(
            f'<a href="{url}" class="button" style="background:#64748b; color:white; padding:6px 15px; border-radius:6px; font-weight:700; text-decoration:none;">👁️ Ver Galería</a>'
        )
    visualizar_biblioteca_link.short_description = "Vista Pública"

    def vectorize_button(self, obj):
        if not obj.pk: return "-"
        return format_html(
            '''
            <button type="button" onclick="vectorizarBiblioteca({0}, '{1}')" class="button" 
                    style="background: #10b981; color: white; padding: 6px 12px; border-radius: 4px; border: none; cursor: pointer; font-weight: 700; font-size: 0.8rem;">
                🧠 Vectorizar
            </button>
            <script>
                if (typeof window.vectorizarBiblioteca === 'undefined') {{
                    window.vectorizarBiblioteca = function(bibId, bibNombre) {{
                        if (!window.Swal) {{
                            const script = document.createElement('script');
                            script.src = 'https://cdn.jsdelivr.net/npm/sweetalert2@11';
                            document.head.appendChild(script);
                            script.onload = () => window.vectorizarBiblioteca(bibId, bibNombre);
                            return;
                        }}
                        
                        Swal.fire({{
                            title: '¿Vectorizar Biblioteca?',
                            text: `Se procesarán los documentos de "${{bibNombre}}". Esto habilitará la búsqueda inteligente para esta colección.`,
                            icon: 'question',
                            showCancelButton: true,
                            confirmButtonColor: '#10b981',
                            cancelButtonColor: '#6b7280',
                            confirmButtonText: 'Sí, iniciar',
                            cancelButtonText: 'Cancelar'
                        }}).then((result) => {{
                            if (result.isConfirmed) {{
                                Swal.fire({{
                                    title: 'Encolando...',
                                    didOpen: () => Swal.showLoading(),
                                    allowOutsideClick: false
                                }});
                                
                                fetch(`/documentos/api/biblioteca/vectorize/${{bibId}}/`)
                                    .then(res => res.json())
                                    .then(data => {{
                                        Swal.fire('¡Éxito!', data.message, 'success');
                                    }})
                                    .catch(err => Swal.fire('Error', 'No se pudo iniciar el proceso', 'error'));
                            }}
                        }});
                    }};
                }}
            </script>
            ''',
            obj.pk, obj.nombre
        )
    vectorize_button.short_description = "IA"

    def gestionar_biblioteca_button(self, obj):
        if not obj.pk: return "-"
        
        return format_html(
            '''
            <div style="display:flex; gap:10px; align-items:center;">
                <button type="button" data-bib-id="{0}" onclick="openDocBibliotecaModal(this)" class="button" 
                        style="background: linear-gradient(135deg, #4f46e5 0%, #3730a3 100%); color: white; padding: 6px 15px; border-radius: 6px; border: none; cursor: pointer; font-weight: 700; font-size: 0.85rem; box-shadow: 0 4px 6px -1px rgba(79, 70, 229, 0.2);">
                    📑 Gestionar Documentos
                </button>
                <a href="/documentos/biblioteca/visualizar/{0}/" class="button" style="background:#f1f5f9; color:#475569; padding:6px 15px; border-radius:6px; border:1px solid #e2e8f0; text-decoration:none; font-weight:700; font-size: 0.85rem;">
                    👁️ Ver Biblioteca Completa
                </a>
            </div>
            <div id="doc-bib-modal-root"></div>
            
            <style>
                #doc-bib-overlay {{
                    position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                    background: rgba(15, 23, 42, 0.65); backdrop-filter: blur(8px);
                    display: flex; align-items: center; justify-content: center;
                    z-index: 99999; opacity: 0; transition: opacity 0.3s ease;
                }}
                .doc-bib-modal-content {{
                    background: #ffffff; width: 95%; max-width: 850px;
                    border-radius: 16px; box-shadow: 0 25px 50px -12px rgba(0,0,0,0.25);
                    overflow: hidden; transform: translateY(30px) scale(0.98); transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
                    display: flex; flex-direction: column; max-height: 85vh;
                    border: 1px solid rgba(255,255,255,0.1);
                }}
                .doc-bib-header {{
                    padding: 24px; background: #f8fafc; border-bottom: 1px solid #e2e8f0;
                    display: flex; justify-content: space-between; align-items: center;
                }}
                .doc-bib-search {{
                    padding: 16px 24px; border-bottom: 1px solid #f1f5f9; background: #fff;
                    display: flex; align-items: center; gap: 15px;
                }}
                .doc-bib-search input {{
                    flex-grow: 1; padding: 12px 16px; border: 2px solid #e2e8f0; border-radius: 10px;
                    font-size: 0.95rem; outline: none; transition: border-color 0.2s;
                }}
                .doc-bib-search input:focus {{ border-color: #4f46e5; }}
                
                .doc-bib-body {{
                    padding: 12px 24px 24px; overflow-y: auto; flex-grow: 1; background: #fff;
                }}
                .doc-card {{
                    display: flex; align-items: center; gap: 18px;
                    padding: 14px 18px; margin-bottom: 10px; border-radius: 12px;
                    border: 1px solid #f1f5f9; transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
                    background: #f8fafc; cursor: pointer; user-select: none;
                    position: relative;
                }}
                .doc-card:hover {{ border-color: #c7d2fe; background: #f5f3ff; box-shadow: 0 4px 12px rgba(79, 70, 229, 0.08); }}
                .doc-card.active {{ background: #eff6ff; border-color: #bfdbfe; }}
                
                /* Estilo Checkbox */
                .doc-check-ui {{
                    width: 24px; height: 24px; border: 2px solid #cbd5e1; border-radius: 6px;
                    display: flex; align-items: center; justify-content: center;
                    background: #fff; transition: all 0.2s; flex-shrink: 0;
                }}
                .doc-card.active .doc-check-ui {{
                    background: #4f46e5; border-color: #4f46e5;
                }}
                .doc-check-ui::after {{
                    content: "✓"; color: #fff; font-weight: bold; font-size: 14px; display: none;
                }}
                .doc-card.active .doc-check-ui::after {{ display: block; }}

                .doc-info {{ flex-grow: 1; pointer-events: none; }}
                .doc-info b {{ display: block; color: #1e293b; font-size: 1rem; margin-bottom: 2px; }}
                .doc-info span {{ font-size: 0.8rem; color: #64748b; line-height: 1.4; }}
                
                .doc-actions {{
                    display: flex; align-items: center; gap: 8px;
                }}
                .btn-view-doc {{
                    width: 38px; height: 38px; border-radius: 8px; border: none;
                    background: #fff; color: #64748b; cursor: pointer;
                    display: flex; align-items: center; justify-content: center;
                    transition: all 0.2s; box-shadow: 0 2px 4px rgba(0,0,0,0.05);
                }}
                .btn-view-doc:hover {{ background: #4f46e5; color: #fff; transform: translateY(-2px); }}

                .save-badge {{
                    font-size: 0.7rem; background: #dcfce7; color: #166534;
                    padding: 2px 8px; border-radius: 99px; opacity: 0; transition: opacity 0.3s;
                }}
                .save-badge.show {{ opacity: 1; }}
            </style>
            
            <script>
                function openDocBibliotecaModal(btn) {{
                    const bibId = btn.getAttribute('data-bib-id');
                    const root = document.getElementById('doc-bib-modal-root');
                    if (!root) return;

                    root.innerHTML = `
                        <div id="doc-bib-overlay">
                            <div class="doc-bib-modal-content">
                                <div class="doc-bib-header">
                                    <div>
                                        <h3 style="margin:0; font-size:1.25rem; font-weight:800; color:#1e293b;">📑 Selección de Documentos</h3>
                                        <p style="margin:0; font-size:0.85rem; color:#64748b;">Marca para añadir/eliminar. Usa el ojo para visualizar individual.</p>
                                    </div>
                                    <div style="display:flex; gap:10px;">
                                        <a href="/documentos/biblioteca/visualizar/${{bibId}}/" class="button" style="background:var(--primary); color:white; padding:8px 15px; border-radius:8px; text-decoration:none; font-weight:700; font-size:0.85rem; display:flex; align-items:center; gap:5px;">👁️ Vista Galería</a>
                                        <button type="button" onclick="closeDocBibModal()" style="background:#f1f5f9; border:none; width:36px; height:36px; border-radius:10px; font-size:1.2rem; cursor:pointer; color:#64748b; display:flex; align-items:center; justify-content:center;">&times;</button>
                                    </div>
                                </div>
                                <div class="doc-bib-search">
                                    <input type="text" placeholder="Buscar por código o título..." id="doc-bib-search-input" autofocus>
                                    <div id="save-status-global" class="save-badge">Guardado automático activo</div>
                                </div>
                                <div class="doc-bib-body" id="doc-bib-list-container">
                                    <div style="text-align:center; padding: 40px; color:#64748b;">
                                        <p>Cargando documentos...</p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    `;
                    
                    const overlay = document.getElementById('doc-bib-overlay');
                    const content = overlay.querySelector('.doc-bib-modal-content');
                    
                    setTimeout(() => {{
                        overlay.style.opacity = '1';
                        content.style.transform = 'translateY(0) scale(1)';
                    }}, 10);
                    
                    const searchInput = document.getElementById('doc-bib-search-input');
                    let searchTimer;
                    searchInput.addEventListener('input', (e) => {{
                        clearTimeout(searchTimer);
                        searchTimer = setTimeout(() => fetchDocsInBib(bibId, e.target.value), 350);
                    }});
                    
                    fetchDocsInBib(bibId);
                }}
                
                function closeDocBibModal() {{
                    const overlay = document.getElementById('doc-bib-overlay');
                    if (!overlay) return;
                    const content = overlay.querySelector('.doc-bib-modal-content');
                    overlay.style.opacity = '0';
                    content.style.transform = 'translateY(30px) scale(0.95)';
                    setTimeout(() => overlay.remove(), 300);
                }}
                
                async function fetchDocsInBib(bibId, q = '') {{
                    const listContainer = document.getElementById('doc-bib-list-container');
                    try {{
                        const res = await fetch('/documentos/api/bibliotecas/documentos/' + bibId + '/?q=' + encodeURIComponent(q));
                        const data = await res.json();
                        
                        if(data.documentos.length === 0) {{
                            listContainer.innerHTML = '<div style="text-align:center; padding:40px; color:#94a3b8;"><p>No se encontraron resultados.</p></div>';
                            return;
                        }}
                        
                        listContainer.innerHTML = data.documentos.map(d => `
                            <div class="doc-card ${{d.pertenece ? 'active' : ''}}" 
                                 onclick="execToggleDoc(${{d.id}}, ${{bibId}}, this)">
                                <div class="doc-check-ui"></div>
                                <div class="doc-info">
                                    <b>${{d.codigo}}</b>
                                    <span>${{d.titulo}} <br> <small>${{d.tipo}}</small></span>
                                </div>
                                <div class="doc-actions">
                                    <div class="save-badge-item save-badge">✓ Guardado</div>
                                    <a href="/admin/documentos/documento/${{d.id}}/change/" target="_blank" class="btn-view-doc" onclick="event.stopPropagation()" title="Ver detalles">
                                        👁️
                                    </a>
                                </div>
                            </div>
                        `).join('');
                    }} catch(e) {{
                        listContainer.innerHTML = '<div style="text-align:center; padding:40px; color:#ef4444;"><p>Error al sincronizar con el servidor.</p></div>';
                    }}
                }}
                
                async function execToggleDoc(docId, bibId, cardEl) {{
                    const badge = cardEl.querySelector('.save-badge-item');
                    cardEl.style.opacity = '0.7';
                    cardEl.style.pointerEvents = 'none';
                    
                    try {{
                        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
                        const res = await fetch('/documentos/api/bibliotecas/toggle/' + docId + '/' + bibId + '/', {{
                            method: 'POST',
                            headers: {{ 'X-CSRFToken': csrfToken }}
                        }});
                        const data = await res.json();
                        
                        const isAdded = data.accion === 'agregado';
                        cardEl.classList.toggle('active', isAdded);
                        
                        // Mostrar confirmación de guardado
                        badge.classList.add('show');
                        setTimeout(() => badge.classList.remove('show'), 1200);
                        
                    }} catch(e) {{
                        alert('Error al guardar.');
                    }} finally {{
                        cardEl.style.opacity = '1';
                        cardEl.style.pointerEvents = 'auto';
                    }}
                }}
            </script>
            ''',
            obj.pk
        )
    gestionar_biblioteca_button.short_description = "Gestión Visual"

    def save_model(self, request, obj, form, change):
        if not change:
            obj.creado_por = request.user
        super().save_model(request, obj, form, change)
        
@admin.register(Carpeta)
class CarpetaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'padre', 'proyecto_id', 'creado_en')
    list_filter = ('creado_en', 'departamentos')
    search_fields = ('nombre',)
    filter_horizontal = ('departamentos',)


@admin.register(GroqApiKey)
class GroqApiKeyAdmin(admin.ModelAdmin):
    list_display = ('alias', 'proveedor', 'modelo', 'is_active', 'orden', 'api_key_masked', 'created_at')
    list_editable = ('is_active', 'orden')
    list_filter = ('is_active', 'proveedor', 'modelo')
    search_fields = ('alias',)

    def api_key_masked(self, obj):
        k = obj.api_key
        return f"{k[:8]}...{k[-4:]}" if len(k) > 12 else "***"
    api_key_masked.short_description = "API Key"


# Importar y registrar admins del sistema de firmas
from . import admin_firmas


@admin.register(DocumentoShare)
class DocumentoShareAdmin(admin.ModelAdmin):
    list_display = ('documento', 'tipo', 'get_destino', 'puede_ver', 'puede_editar', 'puede_compartir', 'esta_vigente', 'compartido_por', 'creado_en')
    list_filter = ('tipo', 'puede_ver', 'puede_editar', 'creado_en')
    search_fields = ('documento__codigo', 'documento__titulo', 'compartido_a_usuario__username', 'compartido_a_grupo__name', 'nota')
    autocomplete_fields = ('documento', 'compartido_a_usuario')
    readonly_fields = ('creado_en', 'compartido_por')
    
    fieldsets = (
        ('Documento', {
            'fields': ('documento',)
        }),
        ('Compartir con', {
            'fields': ('tipo', 'compartido_a_usuario', 'compartido_a_grupo')
        }),
        ('Permisos', {
            'fields': (('puede_ver', 'puede_editar', 'puede_eliminar', 'puede_compartir'),)
        }),
        ('Configuración', {
            'fields': ('expira_en', 'nota', 'compartido_por', 'creado_en')
        }),
    )
    
    def get_destino(self, obj):
        if obj.tipo == 'usuario' and obj.compartido_a_usuario:
            return obj.compartido_a_usuario.get_full_name() or obj.compartido_a_usuario.username
        elif obj.tipo == 'grupo' and obj.compartido_a_grupo:
            return obj.compartido_a_grupo.name
        return "Público (Todos)"
    get_destino.short_description = "Compartido con"
    
    def esta_vigente(self, obj):
        return obj.esta_vigente()
    esta_vigente.boolean = True
    esta_vigente.short_description = "Vigente"
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.compartido_por = request.user
        super().save_model(request, obj, form, change)

