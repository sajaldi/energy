from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from django.contrib.auth.models import User
from .models import Activo, Categoria, Familia, Ubicacion, Marca, Modelo, Plano, Disciplina, BienAfecto, ControlSubmittal
from documentos.models import Documento
from .widgets import (
    SmartModeloWidget, SmartUserWidget, SmartActivoWidget, SmartFamiliaWidget, 
    SmartParentWidget, CachedDisciplinaWidget, CachedUbicacionWidget,
    SmartPlanoWidget, SmartUbicacionWidget
)
from django.core.cache import cache

class PlanoResource(resources.ModelResource):
    ubicacion_nombre = fields.Field(
        column_name='ubicacion_nombre',
        attribute='ubicacion',
        widget=CachedUbicacionWidget(Ubicacion, field='nombre')
    )
    disciplina_nombre = fields.Field(
        column_name='disciplina_nombre',
        attribute='disciplina',
        widget=CachedDisciplinaWidget(Disciplina, field='nombre')
    )

    def dehydrate_disciplina_nombre(self, plano):
        if plano.disciplina:
            return plano.disciplina.get_ruta_completa()
        return ''

    documento_codigo = fields.Field(
        column_name='documento_codigo',
        attribute='documento',
        widget=ForeignKeyWidget(Documento, field='codigo'), 
    )

    def before_import(self, dataset, **kwargs):
        """Caching agresivo en memoria: Cargamos todo el universo de datos una sola vez."""
        from .models import Ubicacion, Disciplina, Plano
        from documentos.models import Documento
        
        # Diccionarios de búsqueda rápida (O(1)) de OBJETOS completos
        self.ubicacion_cache = {str(u.nombre).strip().upper(): u for u in Ubicacion.objects.all()}
        self.disciplina_cache = {str(d.nombre).strip().upper(): d for d in Disciplina.objects.all()}
        self.documento_cache = {str(doc.codigo).strip().upper(): doc for doc in Documento.objects.all()}
        self.planos_existentes = {str(p.nombre).strip().upper() for p in Plano.objects.all()}

    class Meta:
        model = Plano
        import_id_fields = ('nombre',)
        fields = ('nombre', 'tipo_plano', 'numero_documento', 'titulo', 'ubicacion_nombre', 'disciplina_nombre', 'descripcion', 'documento_codigo')
        use_bulk = False
        batch_size = 1000
        skip_unchanged = True
    
    def before_import_row(self, row, **kwargs):
        # Mapeo flexible de nombres de columnas comunes
        if 'ubicacion' in row and 'ubicacion_nombre' not in row:
            row['ubicacion_nombre'] = row['ubicacion']
        if 'disciplina' in row and 'disciplina_nombre' not in row:
            row['disciplina_nombre'] = row['disciplina']
        if 'documento' in row and 'documento_codigo' not in row:
            row['documento_codigo'] = row['documento']

        # Limpieza básica y normalización
        for field in ['ubicacion_nombre', 'disciplina_nombre', 'documento_codigo']:
            if field in row and row[field]:
                # Quitar espacios y convertir a string limpio
                row[field] = str(row[field]).strip()
                if field == 'documento_codigo':
                    row[field] = row[field].upper()

class DisciplinaResource(resources.ModelResource):
    padre_nombre = fields.Field(
        column_name='padre_nombre',
        attribute='padre',
        widget=CachedDisciplinaWidget(Disciplina, field='nombre')
    )

    def before_import(self, dataset, **kwargs):
        """Cargar todas las disciplinas existentes en un caché para evitar N+1."""
        self.disciplina_cache = {d.nombre: d for d in Disciplina.objects.all()}

    def after_save_instance(self, instance, row=None, **kwargs):
        """Actualizar el caché con la nueva disciplina creada para que sus hijos la encuentren."""
        dry_run = kwargs.get('dry_run', False)
        if not dry_run and instance:
            self.disciplina_cache[instance.nombre] = instance

    def before_import_row(self, row, **kwargs):
        """Limpiar espacios en blanco en los nombres para evitar duplicados por error tipográfico."""
        if 'nombre' in row:
            row['nombre'] = str(row['nombre']).strip()
        if 'padre_nombre' in row and row['padre_nombre']:
            row['padre_nombre'] = str(row['padre_nombre']).strip()
        else:
            row['padre_nombre'] = None

    class Meta:
        model = Disciplina
        import_id_fields = ('nombre',)
        fields = ('nombre', 'padre_nombre', 'descripcion')
        export_order = fields
        skip_unchanged = True
        report_skipped = True
        use_bulk = False  # Desactivado para jerarquías (fila a fila para actualizar caché)

class FamiliaResource(resources.ModelResource):
    padre_nombre = fields.Field(
        column_name='padre_nombre',
        attribute='padre',
        widget=ForeignKeyWidget(Familia, field='nombre')
    )

    class Meta:
        model = Familia
        import_id_fields = ('nombre', 'padre_nombre')
        fields = ('id', 'nombre', 'padre_nombre', 'descripcion')
        export_order = ('id', 'nombre', 'padre_nombre', 'descripcion')

class UbicacionResource(resources.ModelResource):
    """
    Resource para Ubicaciones jerárquicas.
    Permite importar usando 'padre_nombre' en lugar de IDs.
    """
    padre_nombre = fields.Field(
        column_name='padre_nombre',
        attribute='padre',
        widget=SmartParentWidget(Ubicacion, field='nombre')
    )
    
    # Campos adicionales para exportación
    id = fields.Field(column_name='id', attribute='id', readonly=True)
    clave_unica = fields.Field(column_name='clave_unica', readonly=True)
    ruta_completa = fields.Field(column_name='ruta_completa', readonly=True)
    categoria_nombre = fields.Field(
        column_name='categoria_nombre',
        attribute='categoria',
        widget=ForeignKeyWidget(Categoria, field='nombre')
    )

    class Meta:
        model = Ubicacion
        # Usamos nombre y padre_nombre como identificadores para evitar duplicados en importación
        import_id_fields = ('nombre', 'padre_nombre')
        fields = ('id', 'clave_unica', 'ruta_completa', 'nombre', 'tipo', 'padre_nombre', 'categoria_nombre', 'orden', 'descripcion')
        export_order = ('id', 'clave_unica', 'ruta_completa', 'nombre', 'tipo', 'padre_nombre', 'categoria_nombre', 'orden', 'descripcion')
        skip_unchanged = True
        report_skipped = True
        
        # Desactivamos bulk para manejar la jerarquía fila a fila y evitar errores de bulk_update con PKs
        use_bulk = False

    def dehydrate_clave_unica(self, obj):
        return obj.get_clave_unica()

    def dehydrate_ruta_completa(self, obj):
        return obj.ruta_completa

class ModeloResource(resources.ModelResource):
    marca_nombre = fields.Field(
        column_name='marca_nombre',
        attribute='marca',
        widget=ForeignKeyWidget(Marca, field='nombre')
    )
    categoria_nombre = fields.Field(
        column_name='categoria_nombre',
        attribute='categoria',
        widget=ForeignKeyWidget(Categoria, field='nombre')
    )

    class Meta:
        model = Modelo
        # Identificamos por nombre y marca para que si el ID está vacío, 
        # actualice si ya existe esa combinación o cree uno nuevo si no.
        import_id_fields = ('nombre', 'marca_nombre')
        fields = ('id', 'nombre', 'marca_nombre', 'categoria_nombre', 'imagen_url')
        export_order = ('id', 'nombre', 'marca_nombre', 'categoria_nombre', 'imagen_url')

    def skip_row(self, instance, original, row, import_validation_errors=None, **kwargs):
        if not any(row.values()): return True
        return super().skip_row(instance, original, row, import_validation_errors, **kwargs)

    def before_import_row(self, row, **kwargs):
        """Asegurar que la marca existe antes de importar el modelo"""
        marca_name = str(row.get('marca_nombre') or '').strip()
        if marca_name:
            from .models import Marca
            Marca.objects.get_or_create(nombre=marca_name)

class ActivoResource(resources.ModelResource):
    marca_nombre = fields.Field(
        column_name='marca_nombre',
        attribute='modelo__marca__nombre',
        readonly=True
    )
    modelo_nombre = fields.Field(
        column_name='modelo_nombre',
        attribute='modelo',
        widget=SmartModeloWidget(Modelo, field='nombre')
    )
    categoria_nombre = fields.Field(
        column_name='categoria_nombre',
        attribute='modelo__categoria',
        widget=ForeignKeyWidget(Categoria, field='nombre'),
        readonly=True
    )
    ubicacion_nombre = fields.Field(
        column_name='ubicacion_nombre',
        attribute='ubicacion',
        widget=SmartUbicacionWidget(Ubicacion, field='nombre')
    )
    responsable_username = fields.Field(
        column_name='responsable_username',
        attribute='responsable',
        widget=SmartUserWidget(User, field='username')
    )
    padre_codigo = fields.Field(
        column_name='padre_codigo',
        attribute='padre',
        widget=SmartActivoWidget(Activo, field='codigo_interno')
    )
    familia_nombre = fields.Field(
        column_name='familia_nombre',
        attribute='familia',
        widget=SmartFamiliaWidget(Familia, field='nombre')
    )
    plano_nombre = fields.Field(
        column_name='plano_nombre',
        attribute='plano',
        widget=SmartPlanoWidget(Plano, field='nombre')
    )

    def __init__(self, **kwargs):
        super().__init__()
        # Vincular el resource a los widgets que lo soportan 
        # (algunos se vinculan dinámicamente en before_import si es necesario)
        widgets_to_bind = [
            'modelo_nombre', 'ubicacion_nombre', 'responsable_username', 
            'padre_codigo', 'familia_nombre', 'plano_nombre'
        ]
        for field_name in widgets_to_bind:
            if field_name in self.fields:
                self.fields[field_name].widget.resource = self

    def import_field(self, field, obj, row, is_m2m=False, **kwargs):
        """Simplificado para velocidad: Solo omite si es realmente vacío"""
        value = row.get(field.column_name)
        if value is None or str(value).strip() == '':
            return
        super().import_field(field, obj, row, is_m2m=is_m2m, **kwargs)

    def import_row(self, row, instance_loader, **kwargs):
        """Sobrescribe import_row para detectar qué campos cambiaron realmente"""
        from import_export import resources
        
        # Obtenemos la instancia y los valores originales para comparar después
        instance, is_new = self.get_or_init_instance(instance_loader, row)
        original_values = {}
        if not is_new and instance:
            for field in self.get_fields():
                original_values[field.column_name] = field.get_value(instance)

        # Procesar la fila normalmente
        row_result = super().import_row(row, instance_loader, **kwargs)

        # Si fue un update exitoso, comparamos valores (usando los originales que guardamos)
        if row_result.import_type == resources.RowResult.IMPORT_TYPE_UPDATE:
            changed_fields = []
            for field in self.get_fields():
                if field.column_name in row:
                    old_val = original_values.get(field.column_name)
                    new_val = field.get_value(row_result.instance)
                    if old_val != new_val:
                        changed_fields.append(field.column_name)
            
            # Guardamos los campos cambiados en el row_result para que la tarea los pueda leer
            row_result.changed_fields = changed_fields

        return row_result

    class Meta:
        model = Activo
        import_id_fields = ('codigo_interno',)
        fields = (
            'id', 'nombre', 'codigo_interno', 'epc', 'serie', 'referencia', 'marca_nombre', 'modelo_nombre', 
            'categoria_nombre', 'familia_nombre', 'plano_nombre', 'estado', 'ubicacion_nombre', 'responsable_username',
            'padre_codigo', 'descripcion', 'fecha_compra', 'costo', 'ubicacion_legacy', 'creado_en', 'actualizado_en'
        )
        export_order = fields
        skip_unchanged = True
        report_skipped = True  # Necesario para el reporte de verificación
        use_bulk = True
        batch_size = 1000  # Volvemos a un tamaño de lote más seguro y manejable
        use_transactions = True 

    def skip_row(self, instance, original, row, import_validation_errors=None, **kwargs):
        """Lógica rápida para omitir filas irrelevantes"""
        if not any(row.values()): return True
        
        # Si no hay nombre ni código, no podemos hacer nada
        nombre = str(row.get('nombre') or '').strip()
        codigo = str(row.get('codigo_interno') or '').strip()
        if not nombre and not codigo:
            return True

        # Si el objeto es nuevo (no hay original), no omitimos
        if not original:
            return False

        return super().skip_row(instance, original, row, import_validation_errors, **kwargs)

    def get_queryset(self, request):
        """Eager loading para que skip_row y exportación sean rápidos"""
        return super().get_queryset(request).select_related(
            'modelo__marca', 'modelo__categoria', 'ubicacion', 'responsable', 'familia', 'plano'
        )

    def get_bulk_update_fields(self):
        """Mapea nombres de campos del Resource a atributos reales del Modelo para Bulk Update"""
        actual_fields = {f.name for f in self._meta.model._meta.get_fields()}
        resource_fields = self.get_fields()
        
        update_fields = set()
        for f_name in super().get_bulk_update_fields():
            # Buscar el campo en el resource para ver qué atributo de modelo impacta
            res_field = next((rf for rf in resource_fields if rf.attribute and rf.column_name == f_name or rf.attribute == f_name), None)
            
            attr = res_field.attribute if res_field else f_name
            # Manejar atributos anidados (ej: modelo__nombre -> solo nos interesa 'modelo')
            base_attr = attr.split('__')[0] if attr else None
            
            if base_attr in actual_fields and base_attr != 'id':
                update_fields.add(base_attr)
                
        return list(update_fields)

    def before_import(self, dataset, *args, **kwargs):
        """Precarga cachés para velocidad y precisión en jerarquías"""
        from django.core.cache import cache
        from .models import Marca, Modelo, Categoria, Ubicacion
        from django.db.models import Count
        
        # 0. Normalizar cabeceras a minúsculas para asegurar coincidencia con Resource
        if dataset.headers:
            dataset.headers = [str(h).lower() for h in dataset.headers]

        # 0.1 Cachear dataset.dict (OPTIMIZACIÓN CRÍTICA para tablib)
        self.dataset_dict = dataset.dict

        # 0.1 Inicializar progreso detallado
        user = kwargs.get('user')
        self._import_user = user
        self._ids_creados = [] # Para rastrear y permitir reversión
        if user:
            cache.set(f"import_progress_{user.id}", 0, 600)
            cache.set(f"import_progress_{user.id}_count", 0, 600)
            cache.set(f"import_progress_{user.id}_current", 'Preparando datos...', 600)
            cache.set(f"import_progress_{user.id}_stats", {'new': 0, 'update': 0, 'skip': 0, 'error': 0}, 600)
            cache.set(f"import_progress_{user.id}_start", __import__('time').time(), 600)
            self.total_rows = len(dataset)

        # 1. Caché Ubicaciones (Iterativo para evitar RecursionError)
        self.ubicacion_clave_cache = {}
        self.ubicacion_nombre_cache = {}
        
        all_locs = {loc.id: loc for loc in Ubicacion.objects.all()}
        nombres_count = {}
        
        for loc_id, loc in all_locs.items():
            curr_path = []
            curr = loc
            visited = set()
            while curr:
                if curr.id in visited: break # Ciclo detectado
                visited.add(curr.id)
                curr_path.append(curr.nombre)
                curr = all_locs.get(curr.padre_id)
            
            path = "|".join(reversed(curr_path)).upper()
            self.ubicacion_clave_cache[path] = loc
            nombres_count[loc.nombre.upper()] = nombres_count.get(loc.nombre.upper(), 0) + 1
        
        for loc_id, loc in all_locs.items():
            if nombres_count.get(loc.nombre.upper()) == 1:
                self.ubicacion_nombre_cache[loc.nombre.upper()] = loc
        
        self.fields['ubicacion_nombre'].widget.resource = self
        self.fields['modelo_nombre'].widget.resource = self

        # 2. Caché Marcas/Modelos/Categorías
        self.marca_cache = {m.nombre.upper(): m for m in Marca.objects.all()}
        # Usar clave compuesta (Nombre, Marca) para evitar colisiones
        self.modelo_cache = {(m.nombre.upper(), m.marca.nombre.upper()): m for m in Modelo.objects.all().select_related('marca', 'categoria')}
        self.categoria_cache = {c.nombre.upper(): c for c in Categoria.objects.all()}
        
        # Caché de Planos (Indexado por nombre y por número de documento)
        self.plano_cache = {p.nombre.upper(): p for p in Plano.objects.all()}
        for p in list(self.plano_cache.values()):
            if p.numero_documento:
                self.plano_cache[p.numero_documento.upper()] = p

        # 3. Pre-procesar Dataset para creación masiva de Marcas/Modelos/Planos
        marcas_to_create = set()
        modelos_data = {} # {mod_name: (mar_name, cat_name)}
        categorias_to_create = set()
        planos_to_create = {} # {plano_name: (ubicacion_nombre)}
        
        def normalize_name(name):
            if not name: return ""
            s = str(name).strip()
            if s.upper() in ('NONE', 'NULL', 'N/A'): return ""
            return s

        import re
        for row in self.dataset_dict:
            mod_name = normalize_name(row.get('modelo_nombre'))
            mar_name = normalize_name(row.get('marca_nombre'))
            cat_name = normalize_name(row.get('categoria_nombre'))
            pl_name = normalize_name(row.get('plano_nombre'))
            
            if mod_name:
                mar_key_normalized = mar_name.upper() if mar_name else "GENERICO"
                mod_key = (mod_name.upper(), mar_key_normalized)
                if mod_key not in self.modelo_cache:
                    modelos_data[mod_key] = (mod_name, mar_name, cat_name)
                    if mar_name and mar_name.upper() not in self.marca_cache:
                        marcas_to_create.add(mar_name)
                    if cat_name and cat_name.upper() not in self.categoria_cache:
                        categorias_to_create.add(cat_name)
            
            if pl_name and pl_name.upper() not in self.plano_cache:
                planos_to_create[pl_name.upper()] = (pl_name, normalize_name(row.get('ubicacion_nombre')))

        # Crear Marcas faltantes
        if marcas_to_create:
            Marca.objects.bulk_create([Marca(nombre=m) for m in marcas_to_create], ignore_conflicts=True)
            self.marca_cache = {m.nombre.upper(): m for m in Marca.objects.all()}
            
        # Crear Categorías faltantes
        if categorias_to_create:
            Categoria.objects.bulk_create([Categoria(nombre=c) for c in categorias_to_create], ignore_conflicts=True)
            self.categoria_cache = {c.nombre.upper(): c for c in Categoria.objects.all()}

        # Crear Modelos faltantes
        if modelos_data:
            new_models = []
            if "GENERICO" not in self.marca_cache:
                gen, _ = Marca.objects.get_or_create(nombre="GENERICO")
                self.marca_cache["GENERICO"] = gen

            for mod_key, (m_name, mar_name, cat_name) in modelos_data.items():
                marca = self.marca_cache.get(mar_name.upper() if mar_name else "GENERICO")
                cat = self.categoria_cache.get(cat_name.upper()) if cat_name else None
                new_models.append(Modelo(nombre=m_name, marca=marca, categoria=cat))
            
            if new_models:
                Modelo.objects.bulk_create(new_models, ignore_conflicts=True)
                # Recargar caché de modelos con la nueva data
                self.modelo_cache = {(m.nombre.upper(), m.marca.nombre.upper()): m for m in Modelo.objects.all().select_related('marca', 'categoria')}

        # Crear Planos faltantes
        if planos_to_create:
            new_planos = []
            for pl_key, (pl_name, u_name) in planos_to_create.items():
                ubicacion = None
                if u_name:
                    u_norm = re.sub(r'\s*([→|>]|->)\s*', '|', u_name).strip().upper()
                    ubicacion = self.ubicacion_clave_cache.get(u_norm)
                    if not ubicacion:
                        ubicacion = self.ubicacion_nombre_cache.get(u_name.upper())
                new_planos.append(Plano(nombre=pl_name, ubicacion=ubicacion))
            
            if new_planos:
                Plano.objects.bulk_create(new_planos, ignore_conflicts=True)
                # Recargar caché de planos
                self.plano_cache = {p.nombre.upper(): p for p in Plano.objects.all()}
                for p in list(self.plano_cache.values()):
                    if p.numero_documento:
                        self.plano_cache[p.numero_documento.upper()] = p

        # 4. Caché de Objetos Activos (Solo los que vienen en el archivo para evitar saturar RAM)
        codigos = [str(row.get('codigo_interno')).strip() for row in self.dataset_dict if row.get('codigo_interno')]
        self.activo_instance_cache = {
            a.codigo_interno: a for a in Activo.objects.filter(codigo_interno__in=codigos).select_related(
                'modelo__marca', 'modelo__categoria', 'ubicacion', 'responsable', 'familia', 'plano'
            )
        }
        
        # 5. Caché de Otros (User, Familia)
        from django.contrib.auth.models import User
        from .models import Familia
        self.user_cache = {u.username: u for u in User.objects.all()}
        self.familia_cache = {f.nombre.upper(): f for f in Familia.objects.all()}

        # 6. Caché para SmartActivoWidget (padre_codigo)
        # Solo cargamos los activos que son referenciados como padres en este archivo
        padres_codigos = {str(row.get('padre_codigo')).strip() for row in self.dataset_dict if row.get('padre_codigo')}
        self.activo_full_cache = {a.codigo_interno: a for a in Activo.objects.filter(codigo_interno__in=padres_codigos) if a.codigo_interno}
        
        # Inicializar contadores
        self._row_counter = 0
        self._stats = {'new': 0, 'update': 0, 'skip': 0, 'error': 0}

    def after_import_row(self, row, row_result, **kwargs):
        """Reporte de progreso ultra-ligero (Cada 1000 filas)"""
        if not hasattr(self, '_row_counter'): self._row_counter = 0
        self._row_counter += 1
        
        if self._row_counter % 1000 == 0 or self._row_counter == self.total_rows:
            print(f"[CELERY] Progreso: {self._row_counter}/{self.total_rows} ({int((self._row_counter/self.total_rows)*100)}%)")
            user = self._import_user
            if user:
                from django.core.cache import cache
                percent = min(int((self._row_counter / self.total_rows) * 100), 100)
                cache.set(f"import_progress_{user.id}", percent, 300)
                cache.set(f"import_progress_{user.id}_count", self._row_counter, 300)

    def dehydrate_ubicacion_nombre(self, activo):
        """Exportar la ruta completa para evitar ambigüedad en futuras importaciones"""
        if activo.ubicacion:
            return activo.ubicacion.get_ruta_completa()
        return ""

    def dehydrate_plano_nombre(self, activo):
        if activo.plano:
            return activo.plano.numero_documento or activo.plano.nombre
        return ""

    def get_instance(self, instance_loader, row):
        codigo = row.get('codigo_interno')
        if codigo:
            # Usar caché de instancias pre-cargadas en before_import
            return self.activo_instance_cache.get(str(codigo))
        return None

class BienAfectoResource(resources.ModelResource):
    ubicacion_nombre = fields.Field(
        column_name='ubicacion_nombre',
        attribute='ubicacion',
        widget=SmartUbicacionWidget(Ubicacion, field='nombre')
    )
    plano_nombre = fields.Field(
        column_name='plano_nombre',
        attribute='plano',
        widget=SmartPlanoWidget(Plano, field='nombre')
    )
    familia_nombre = fields.Field(
        column_name='familia_nombre',
        attribute='familia',
        widget=SmartFamiliaWidget(Familia, field='nombre')
    )
    responsable_username = fields.Field(
        column_name='responsable_username',
        attribute='responsable',
        widget=SmartUserWidget(User, field='username')
    )
    
    class Meta:
        model = BienAfecto
        import_id_fields = ('codigo_interno',)
        fields = ('id', 'codigo_interno', 'nombre', 'ubicacion_nombre', 'plano_nombre', 'familia_nombre', 'responsable_username', 'creado_en', 'actualizado_en')
        export_order = fields
        skip_unchanged = True
        report_skipped = True
        use_bulk = True

    def __init__(self, **kwargs):
        super().__init__()
        # Vincular widgets
        widgets_to_bind = ['ubicacion_nombre', 'plano_nombre', 'familia_nombre', 'responsable_username']
        for field_name in widgets_to_bind:
            if field_name in self.fields:
                self.fields[field_name].widget.resource = self

    def before_import(self, dataset, *args, **kwargs):
        """Precarga cachés para velocidad y precisión en jerarquías"""
        from django.core.cache import cache
        from .models import Ubicacion, Familia, Plano
        from django.contrib.auth.models import User
        
        # 0. Normalizar cabeceras
        if dataset.headers:
            dataset.headers = [str(h).lower() for h in dataset.headers]

        self.dataset_dict = dataset.dict

        # 0.1 Inicializar progreso detallado
        user = kwargs.get('user')
        self._import_user = user
        if user:
            cache.set(f"import_bienes_progress_{user.id}", 0, 600)
            cache.set(f"import_bienes_progress_{user.id}_count", 0, 600)
            self.total_rows = len(dataset)

        # 1. Caché Ubicaciones
        self.ubicacion_clave_cache = {}
        self.ubicacion_nombre_cache = {}
        
        all_locs = {loc.id: loc for loc in Ubicacion.objects.all()}
        nombres_count = {}
        
        for loc_id, loc in all_locs.items():
            curr_path = []
            curr = loc
            visited = set()
            while curr:
                if curr.id in visited: break 
                visited.add(curr.id)
                curr_path.append(curr.nombre)
                curr = all_locs.get(curr.padre_id)
            
            path = "|".join(reversed(curr_path)).upper()
            self.ubicacion_clave_cache[path] = loc
            nombres_count[loc.nombre.upper()] = nombres_count.get(loc.nombre.upper(), 0) + 1
        
        for loc_id, loc in all_locs.items():
            if nombres_count.get(loc.nombre.upper()) == 1:
                self.ubicacion_nombre_cache[loc.nombre.upper()] = loc
        
        self.fields['ubicacion_nombre'].widget.resource = self

        # 2. Caché de Planos
        self.plano_cache = {p.nombre.upper(): p for p in Plano.objects.all()}
        for p in list(self.plano_cache.values()):
            if p.numero_documento:
                self.plano_cache[p.numero_documento.upper()] = p

        # 3. Caché de Otros (User, Familia)
        self.user_cache = {u.username: u for u in User.objects.all()}
        self.familia_cache = {f.nombre.upper(): f for f in Familia.objects.all()}
        
        # Inicializar contadores
        self._row_counter = 0

    def after_import_row(self, row, row_result, **kwargs):
        """Reporte de progreso ultra-ligero"""
        if not hasattr(self, '_row_counter'): self._row_counter = 0
        self._row_counter += 1
        
        if self._row_counter % 500 == 0 or self._row_counter == self.total_rows:
            user = self._import_user
            if user:
                from django.core.cache import cache
                percent = min(int((self._row_counter / self.total_rows) * 100), 100)
                cache.set(f"import_bienes_progress_{user.id}", percent, 300)
                cache.set(f"import_bienes_progress_{user.id}_count", self._row_counter, 300)

    def import_row(self, row, instance_loader, **kwargs):
        """Sobrescribe import_row para detectar qué campos cambiaron realmente"""
        from import_export import resources
        
        instance, is_new = self.get_or_init_instance(instance_loader, row)
        original_values = {}
        if not is_new and instance:
            for field in self.get_fields():
                original_values[field.column_name] = field.get_value(instance)

        row_result = super().import_row(row, instance_loader, **kwargs)

        if row_result.import_type == resources.RowResult.IMPORT_TYPE_UPDATE:
            changed_fields = []
            for field in self.get_fields():
                if field.column_name in row:
                    old_val = original_values.get(field.column_name)
                    new_val = field.get_value(row_result.instance)
                    if old_val != new_val:
                        changed_fields.append(field.column_name)
            
            row_result.changed_fields = changed_fields

        return row_result

    def dehydrate_ubicacion_nombre(self, obj):
        if obj.ubicacion:
            return obj.ubicacion.ruta_completa
        return ""

class ControlSubmittalResource(resources.ModelResource):
    class Meta:
        model = ControlSubmittal
        import_id_fields = ('codigo_ficha',)
        fields = (
            'descripcion', 'especialidad', 'trab_act_n',
            'fecha_recibido', 'codigo_ficha', 'codigo_submittal', 'num_submittal',
            'fecha_revisado_epc', 'comentario_epc', 'observacion_epc',
            'fecha_envio_sup', 'transmision_epc_sup', 'transmision_sup_epc',
            'fecha_recepcion_sup', 'dictamen_sup', 'observacion_sup',
            'enviado_constructora', 'fecha_envio_ccc', 'estatus_aconex',
            'estatus_ccg', 'carpeta', 'transmitido_a_ccc', 'fecha_envio_ccc_final'
        )
        skip_unchanged = True
        report_skipped = True
