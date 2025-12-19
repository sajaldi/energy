# Importación y Exportación de Ubicaciones

Este documento explica cómo utilizar la funcionalidad de importar/exportar ubicaciones jerárquicas en el sistema.

## 🔑 Características Principales

### Ruta Completa Jerárquica
Todas las ubicaciones ahora muestran su **ruta completa** en la jerarquía:
- ✅ **Formato de visualización**: `Campus Principal → Torre A → Nivel 1 → Aula 101`
- ✅ Permite identificar rápidamente la ubicación exacta en la estructura
- ✅ Se muestra automáticamente en el admin y en todas las exportaciones

### Clave Única Compuesta
El sistema usa una **clave única compuesta** que permite tener ubicaciones con el mismo nombre en diferentes padres:
- ✅ **Ejemplo**: Puedes tener `Nivel 1` en `Torre A`, `Torre B` y `Torre C`
- ✅ **Formato de clave**: `Campus Principal|Torre A|Nivel 1` (usa `|` como separador)
- ✅ Evita conflictos al importar/actualizar ubicaciones
- ✅ Se genera automáticamente al exportar

## 📊 Exportar Ubicaciones

1. En el panel de administración de Django, ve a **Activos > Ubicaciones**
2. Haz clic en el botón **"Export"** en la parte superior derecha
3. Selecciona el formato deseado (CSV, Excel, JSON, etc.)
4. Descarga el archivo

### Columnas en la exportación:

- **id**: ID de la ubicación en la base de datos
- **clave_unica**: Clave única compuesta (ej: `Campus Principal|Torre A|Nivel 1`)
- **ruta_completa**: Ruta completa legible (ej: `Campus Principal → Torre A → Nivel 1`)
- **nombre**: Nombre de la ubicación (ej: `Nivel 1`)
- **padre_nombre**: Nombre de la ubicación padre (ej: `Torre A`)
- **descripcion**: Descripción de la ubicación

## 📥 Importar Ubicaciones

### ✅ Formato del archivo CSV/Excel:

**Solo necesitas 3 columnas:**
```csv
nombre,padre_nombre,descripcion
Campus Principal,,Campus universitario principal
Torre A,Campus Principal,Primera torre del campus
Torre B,Campus Principal,Segunda torre del campus
Nivel 1,Torre A,Primer nivel de Torre A
Nivel 1,Torre B,Primer nivel de Torre B
Aula 101,Nivel 1,Aula 101 de Torre A - Nivel 1
```

### 🎯 Columnas Requeridas:

| Columna | ¿Requerida? | Descripción |
|---------|-------------|-------------|
| **nombre** | ✅ SÍ | Nombre de la ubicación (puede repetirse en diferentes padres) |
| **padre_nombre** | ⚪ Opcional | Nombre del padre. Dejar vacío para ubicaciones raíz |
| **descripcion** | ⚪ Opcional | Descripción de la ubicación |

### ❌ NO incluyas estos campos:

- ❌ **clave_unica** - Se calcula automáticamente
- ❌ **ruta_completa** - Se calcula automáticamente
- ❌ **id** - Se asigna automáticamente

**Estos campos aparecen solo en la EXPORTACIÓN**, no los incluyas al importar.

### 💡 Nota sobre ubicaciones duplicadas: 

El sistema permite tener múltiples ubicaciones con el mismo nombre si están bajo diferentes padres:
- ✅ "Nivel 1" en Torre A
- ✅ "Nivel 1" en Torre B  
- ✅ "Nivel 1" en Torre C

**Todas son diferentes** porque tienen diferente `padre_nombre`.

### Reglas importantes:

1. **nombre** (requerido)
   - Nombre simple de la ubicación
   - Ejemplo: `Nivel 1`, `Torre A`, `Aula 101`
   - Puede repetirse en diferentes padres sin problema

2. **padre_nombre** (opcional - vacío para raíz)
   - Nombre exacto de la ubicación padre
   - Debe existir antes en el archivo o en la base de datos
   - Vacío = ubicación raíz (sin padre)

3. **descripcion** (opcional)
   - Texto libre para describir la ubicación

### 📌 Importante sobre el orden:

⚠️ **Importa en orden jerárquico**: Padres primero, luego hijos

**✅ Correcto:**
```csv
nombre,padre_nombre,descripcion
Campus Principal,,Campus principal
Torre A,Campus Principal,Primera torre
Nivel 1,Torre A,Primer nivel
Aula 101,Nivel 1,Aula en nivel 1
```

**❌ Incorrecto:**
```csv
nombre,padre_nombre,descripcion
Aula 101,Nivel 1,Aula en nivel 1     ← Error: Nivel 1 no existe aún
Nivel 1,Torre A,Primer nivel         ← Error: Torre A no existe aún
Torre A,Campus Principal,Primera torre
Campus Principal,,Campus principal
```

**Ejemplo correcto - Múltiples torres con mismos niveles:**
```csv
nombre,padre_nombre,descripcion
Campus Principal,,Campus principal
Torre A,Campus Principal,Primera torre
Torre B,Campus Principal,Segunda torre
Nivel 1,Torre A,Nivel 1 de Torre A
Nivel 2,Torre A,Nivel 2 de Torre A
Nivel 1,Torre B,Nivel 1 de Torre B
Nivel 2,Torre B,Nivel 2 de Torre B
```

Esto creará:
- `Campus Principal` (raíz)
  - `Campus Principal → Torre A`
    - `Campus Principal → Torre A → Nivel 1`
    - `Campus Principal → Torre A → Nivel 2`
  - `Campus Principal → Torre B`
    - `Campus Principal → Torre B → Nivel 1` ✅ (diferente del Nivel 1 de Torre A)
    - `Campus Principal → Torre B → Nivel 2` ✅ (diferente del Nivel 2 de Torre A)

### Pasos para importar:

1. Ve a **Activos > Ubicaciones**
2. Haz clic en el botón **"Import"** en la parte superior derecha
3. Selecciona el formato del archivo (CSV, Excel, etc.)
4. Haz clic en "Choose file" y selecciona tu archivo
5. Haz clic en "Submit"
6. Revisa la vista previa de los cambios
7. Si todo está correcto, haz clic en "Confirm import"

### Actualización de ubicaciones existentes:

El sistema identifica ubicaciones por su **clave única compuesta** (ruta completa):
- `Campus Principal|Torre A|Nivel 1` se actualizará si ya existe
- `Campus Principal|Torre B|Nivel 1` es diferente y no se confundirá con la anterior
- Si cambias el **padre_nombre**, la ubicación se moverá en la jerarquía

### Ejemplo práctico completo:

**Ejemplo: Campus con 3 torres, cada una con sus propios niveles**

```csv
nombre,padre_nombre,descripcion
Campus Principal,,Campus universitario principal
Torre A,Campus Principal,Primera torre del campus
Torre B,Campus Principal,Segunda torre del campus
Torre C,Campus Principal,Tercera torre del campus
Nivel 1,Torre A,Primer nivel de Torre A
Nivel 2,Torre A,Segundo nivel de Torre A
Nivel 3,Torre A,Tercer nivel de Torre A
Nivel 1,Torre B,Primer nivel de Torre B
Nivel 2,Torre B,Segundo nivel de Torre B
Nivel 3,Torre B,Tercer nivel de Torre B
Nivel 1,Torre C,Primer nivel de Torre C
Nivel 2,Torre C,Segundo nivel de Torre C
Aula 101,Nivel 1,Aula de Torre A - Nivel 1
Aula 102,Nivel 1,Aula de Torre A - Nivel 1
Laboratorio 103,Nivel 1,Laboratorio de Torre A - Nivel 1
```

Este ejemplo muestra cómo puedes tener "Nivel 1", "Nivel 2" repetidos en diferentes torres sin conflictos. El sistema mostrará:
- `Campus Principal → Torre A → Nivel 1`
- `Campus Principal → Torre B → Nivel 1`
- `Campus Principal → Torre C → Nivel 1`

Cada una es una ubicación diferente y única.

## ⚠️ Notas adicionales:

- La funcionalidad de **drag-and-drop** sigue funcionando para reorganizar ubicaciones
- Puedes combinar ambas técnicas: importar en masa y luego reorganizar con drag-and-drop
- Los caracteres especiales y tildes son soportados (Ej: "Baño", "Área Técnica")
- Las ubicaciones importadas automáticamente actualizan la estructura jerárquica (MPTT)

## 🔄 Sincronización con el árbol MPTT:

El sistema automáticamente mantiene la estructura jerárquica (MPTT) al importar. No necesitas hacer nada especial, pero ten en cuenta:
- Las ubicaciones se reorganizan automáticamente en el árbol
- Los campos MPTT (lft, rght, tree_id, level) se calculan automáticamente
- No incluyas estos campos en tus archivos de importación
