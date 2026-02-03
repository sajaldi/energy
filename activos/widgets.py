from import_export.widgets import ForeignKeyWidget

class SmartModeloWidget(ForeignKeyWidget):
    """Widget que busca o CREA la Marca y el Modelo on-the-fly."""
    def clean(self, value, row=None, **kwargs):
        if not value:
            return None
        
        val_str = str(value).strip()
        if val_str.upper() in ('NONE', 'NULL', 'N/A', ''):
            return None
            
        # 1. Intentar buscar en caché (lectura rápida)
        val_upper = val_str.upper()
        marca_nombre = row.get('marca_nombre')
        marca_key = str(marca_nombre).strip().upper() if marca_nombre else "GENERICO"
        
        resource = getattr(self, 'resource', kwargs.get('resource'))
        if resource and hasattr(resource, 'modelo_cache'):
            cached = resource.modelo_cache.get((val_upper, marca_key))
            if cached:
                return cached

        # 2. Si no existe, intentar encontrarlo o crearlo en BD
        from .models import Marca, Modelo
        
        # Necesitamos la marca para poder crear/buscar el modelo con precisión
        if not marca_nombre:
            # Si no viene marca, buscamos el modelo "suelto" por nombre (arriesgado pero fallback)
            modelo = Modelo.objects.filter(nombre__iexact=val_str).first()
            if modelo:
                return modelo
            # Si no existe y no hay marca, no podemos crearlo
            return None
            
        marca_str = str(marca_nombre).strip()
        
        # Buscar o Crear Marca (Safer than get_or_create if duplicates exist)
        marca = Marca.objects.filter(nombre__iexact=marca_str).first()
        if not marca:
            marca = Marca.objects.create(nombre=marca_str)
        
        # Buscar o Crear Modelo (vinculado a esa marca)
        modelo = Modelo.objects.filter(nombre__iexact=val_str, marca=marca).first()
        if not modelo:
            modelo = Modelo.objects.create(nombre=val_str, marca=marca)
        
        # Actualizar caché si existe para futuras filas
        if resource and hasattr(resource, 'modelo_cache'):
             resource.modelo_cache[(val_upper, marca_key)] = modelo
             
        return modelo

class SmartUserWidget(ForeignKeyWidget):
    """Widget que busca el usuario por username y devuelve None si no existe instead of crashing."""
    def clean(self, value, row=None, **kwargs):
        if not value:
            return None
        val_str = str(value).strip()
        if val_str.upper() in ('NONE', 'NULL', 'N/A', ''):
            return None
        
        resource = getattr(self, 'resource', kwargs.get('resource'))
        if resource and hasattr(resource, 'user_cache'):
            return resource.user_cache.get(val_str)
            
        from django.contrib.auth.models import User
        return User.objects.filter(username=val_str).first()

class SmartActivoWidget(ForeignKeyWidget):
    """Widget que busca el activo por código interno y devuelve None si no existe."""
    def clean(self, value, row=None, **kwargs):
        if not value:
            return None
        val_str = str(value).strip()
        
        resource = getattr(self, 'resource', kwargs.get('resource'))
        if resource and hasattr(resource, 'activo_full_cache'):
            return resource.activo_full_cache.get(val_str)
            
        from .models import Activo
        return Activo.objects.filter(codigo_interno=val_str).first()

class SmartFamiliaWidget(ForeignKeyWidget):
    """Widget que busca la familia por nombre y devuelve None si no existe."""
    def clean(self, value, row=None, **kwargs):
        if not value:
            return None
        val_str = str(value).strip()
        val_upper = val_str.upper()
        
        resource = getattr(self, 'resource', kwargs.get('resource'))
        if resource and hasattr(resource, 'familia_cache'):
            return resource.familia_cache.get(val_upper)
            
        from .models import Familia
        return Familia.objects.filter(nombre__iexact=val_str).first()

class SmartParentWidget(ForeignKeyWidget):
    """
    Widget que busca el padre por nombre y devuelve el primero encontrado.
    Evita MultipleObjectsReturned en jerarquías con nombres repetidos en distintos niveles.
    """
    def clean(self, value, row=None, **kwargs):
        if not value:
            return None
            
        resource = getattr(self, 'resource', kwargs.get('resource'))
        if resource and hasattr(resource, 'ubicacion_nombre_cache'):
            return resource.ubicacion_nombre_cache.get(str(value).strip().upper())
            
        from .models import Ubicacion
        return Ubicacion.objects.filter(nombre=value).first()

class CachedDisciplinaWidget(ForeignKeyWidget):
    """
    Widget que utiliza un caché del Resource para evitar consultas redundantes a la DB.
    """
    def clean(self, value, row=None, **kwargs):
        if not value or str(value).strip().upper() in ('NONE', 'NULL', 'N/A', '', 'NAN'):
            return None
        val_orig = str(value).strip()
        val_clean = val_orig.upper()
        resource = getattr(self, 'resource', kwargs.get('resource'))
        
        if resource and hasattr(resource, 'disciplina_cache'):
            return resource.disciplina_cache.get(val_clean)
        
        from .models import Disciplina
        return Disciplina.objects.filter(nombre__iexact=val_orig).first()

class CachedUbicacionWidget(ForeignKeyWidget):
    """
    Widget que utiliza un caché del Resource para evitar consultas redundantes a la DB.
    """
    def clean(self, value, row=None, **kwargs):
        if not value or str(value).strip().upper() in ('NONE', 'NULL', 'N/A', '', 'NAN'):
            return None
        val_orig = str(value).strip()
        val_clean = val_orig.upper()
        resource = getattr(self, 'resource', kwargs.get('resource'))
        
        if resource and hasattr(resource, 'ubicacion_cache'):
            return resource.ubicacion_cache.get(val_clean)
        
        from .models import Ubicacion
        return Ubicacion.objects.filter(nombre__iexact=val_orig).first()

class SmartPlanoWidget(ForeignKeyWidget):
    """Widget que busca el plano por nombre. Si no existe lo crea."""
    def clean(self, value, row=None, **kwargs):
        if not value:
            return None
        val_str = str(value).strip()
        val_upper = val_str.upper()
        if val_upper in ('NONE', 'NULL', 'N/A', ''):
            return None
            
        resource = getattr(self, 'resource', kwargs.get('resource'))
        if resource and hasattr(resource, 'plano_cache'):
            plano = resource.plano_cache.get(val_upper)
            if plano:
                return plano
                
        from .models import Plano, Ubicacion
        plano = Plano.objects.filter(nombre__iexact=val_str).first()
        if not plano:
            # Si no existe, lo creamos. Intentamos obtener la ubicación del row.
            ubicacion_val = row.get('ubicacion_nombre')
            ubicacion = None
            if ubicacion_val:
                # Usar lógica de jerarquía optimizada si el resource tiene el caché
                u_val_clean = str(ubicacion_val).strip()
                import re
                u_norm = re.sub(r'\s*([→|>]|->)\s*', '|', u_val_clean).strip().upper()
                
                if resource and hasattr(resource, 'ubicacion_clave_cache'):
                    ubicacion = resource.ubicacion_clave_cache.get(u_norm)
                
                if not ubicacion:
                    # Fallback manual
                    for loc in Ubicacion.objects.filter(nombre__iexact=u_norm.split('|')[-1]):
                        if loc.get_clave_unica().upper() == u_norm:
                            ubicacion = loc
                            break
                
                if not ubicacion:
                    ubicacion = Ubicacion.objects.filter(nombre__iexact=u_val_clean).first()
            
            # Ahora permitimos crear planos sin ubicación
            plano = Plano.objects.create(nombre=val_str, ubicacion=ubicacion)
            
            # Actualizar el caché para que otras filas usen el mismo objeto recién creado
            if resource and hasattr(resource, 'plano_cache'):
                resource.plano_cache[val_upper] = plano
            
        return plano

class SmartUbicacionWidget(ForeignKeyWidget):
    """
    Widget optimizado que utiliza el caché del Resource para evitar consultas N+1.
    """
    def clean(self, value, row=None, **kwargs):
        if not value:
            return None
        
        value_str = str(value).strip()
        resource = getattr(self, 'resource', kwargs.get('resource'))
        
        # 1. Normalizar separadores y espacios (soporta: " → ", "->", " > ", "|")
        import re
        normalized_val = re.sub(r'\s*([→|>]|->)\s*', '|', value_str).strip()
        val_upper = normalized_val.upper()
        
        # 2. Intentar resolver por Clave Única (Ruta Completa) desde caché
        if resource and hasattr(resource, 'ubicacion_clave_cache'):
            if val_upper in resource.ubicacion_clave_cache:
                return resource.ubicacion_clave_cache[val_upper]
        
        # 3. Intentar resolver por Nombre Simple (solo si es único) desde caché
        if resource and hasattr(resource, 'ubicacion_nombre_cache'):
            if value_str.upper() in resource.ubicacion_nombre_cache:
                return resource.ubicacion_nombre_cache[value_str.upper()]

        # 4. Fallback: Resolución manual si el caché no lo tiene o el valor tiene jerarquía
        if '|' in normalized_val:
            parts = [p.strip() for p in normalized_val.split('|')]
            nombre_final = parts[-1]
            from .models import Ubicacion
            candidatos = Ubicacion.objects.filter(nombre__iexact=nombre_final)
            for cand in candidatos:
                if cand.get_clave_unica().upper() == val_upper:
                    return cand
        
        # Fallback final: buscar por nombre simple en la DB
        from .models import Ubicacion
        return Ubicacion.objects.filter(nombre__iexact=value_str).first()
