# CMMS Energia - Mantenimiento y Solución de Errores

Este archivo contiene guías para la resolución de errores comunes y mantenimiento del sistema.

## 🛠 Solución de Errores Comunes

### 1. TemplateSyntaxError: `Could not parse the remainder: '==u.id'`

**Problema:**
Django arroja un error de sintaxis en el archivo `cronograma.html` (o `cronograma_fix.html`) indicando que no puede parsear el resto de la etiqueta: `'==u.id'`.

**Causa:**
Este error ocurre cuando un formateador de código automático (como el de VS Code o Prettier) elimina los espacios alrededor del operador `==` en las etiquetas de Django:
- ❌ **Incorrecto:** `{% if current_ubi==u.id %}`
- ✅ **Correcto:** `{% if current_ubi == u.id %}` (Django requiere espacios aquí).

**Solución Definitiva (Arquitectónica):**
La mejor forma de evitar esto permanentemente es mover la lógica de comparación a la **vista (view)** y pasar un booleano al template.

En `views.py`:
```python
    for u in ubicaciones_roots:
        u.is_selected = (u.id == current_ubi_id)
```

En el template:
```django
{% if u.is_selected %}selected{% endif %}
```
Al no haber operador `==`, el formateador no tiene nada que "limpiar" y el error desaparece para siempre.

### 2. Cambios en plantillas que no se reflejan

**Problema:**
Modificas un archivo `.html` pero el servidor sigue mostrando la versión anterior o el error anterior.

**Causa:**
1. **Shadowing**: Puede haber una carpeta de plantillas global (`/templates/`) que tenga un archivo con el mismo nombre y esté tomando prioridad sobre la de la app (`/mantenimiento/templates/`).
2. **Caché**: El servidor Django o el navegador pueden estar cacheando la plantilla.
3. **Editor Lock**: Si tienes el archivo abierto en un editor con "Auto Save", puede estar sobreescribiendo los cambios de las herramientas automáticas.

**Solución:**
1. Asegúrate de cerrar el archivo en tu editor antes de aplicar parches masivos.
2. Si el error persiste en un archivo específico (ej. `cronograma.html`), hemos creado una versión bypass llamada `cronograma_fix.html` y actualizado la vista en `views.py` para usarla. Esto rompe cualquier bucle de caché o shadowing persistente.

## 🚀 Despliegue y Base de Datos

Para más información sobre el despliegue en Coolify o importación de rutinas, consulta:
- `DEPLOY_COOLIFY.md`
- `RUTINAS_IMPORT_EXPORT.md`
- `UBICACIONES_IMPORT_EXPORT.md`
