# Importación y Exportación de Materiales y Repuestos

## 📊 Exportar Materiales

1. Ve a **Inventarios > Materiales y Repuestos**
2. Click en **"Export"** 
3. Selecciona formato (CSV, Excel, etc.)
4. Descarga el archivo

### Columnas en la exportación:

| Columna | Descripción |
|---------|-------------|
| **sku** | Código único del material (SKU) |
| **nombre** | Nombre del material |
| **marca** | Marca del repuesto |
| **categoria** | Categoría del material |
| **unidad_medida** | Unidad de medida (UNIDAD, LITRO, METRO, etc.) |
| **tipo_material** | Tipo (INSUMO, REPUESTO, CONSUMIBLE, MEDICAMENTO, HERRAMIENTA, EPP, OTRO) |
| **precio_estimado** | Costo unitario estimado |
| **stock_minimo** | Nivel mínimo para alertas |
| **imagen** | Ruta relativa o URL de la imagen |
| **descripcion** | Descripción técnica detallada |

---

## 📥 Importar Materiales (Carga Masiva)

### ✅ Formato del archivo CSV/Excel:

**Ejemplo de columnas soportadas:**
```csv
sku,nombre,marca,categoria,unidad_medida,precio_estimado,stock_minimo,stock_inicial,ubicacion,modelos_compatibles
FIL-001,Filtro de Aceite,CAT,Filtros,UNIDAD,15.50,10,50,Almacén Central,Generador 500kVA; Motor Diesel
CBL-10mm,Cable 10mm,Generic,Eléctrico,METRO,2.10,100,200,Taller Eléctrico,
```

### 🎯 Columnas Principales:

| Columna | ¿Requerida? | Descripción | Ejemplo |
|---------|-------------|-------------|---------|
| **sku** | ✅ SÍ | Identificador único | "FIL-001" |
| **nombre** | ✅ SÍ | Nombre del repuesto | "Filtro de Aire" |
| **marca** | ⚪ Opcional | Se crea sí no existe | "Caterpillar" |
| **categoria** | ⚪ Opcional | Se crea si no existe | "Consumibles" |
| **tipo_material** | ⚪ Opcional | Default: INSUMO | "REPUESTO" |
| **unidad_medida** | ⚪ Opcional | Default: UNIDAD | "LITRO" |
| **precio_estimado** | ⚪ Opcional | Default: 0.00 | 15.50 |
| **stock_minimo** | ⚪ Opcional | Default: 0 | 10 |
| **imagen** | ⚪ Opcional | URL o Path | "materiales/filtro.jpg" |

### 📦 Columnas Especiales (Carga Inicial):

Estas columnas permiten cargar stock inicial y relaciones automáticamente durante la importación.

| Columna | Descripción |
|---------|-------------|
| **stock_inicial** | Cantidad inicial a cargar (Requiere 'ubicacion') |
| **ubicacion** | Nombre exacto de la bodega/ubicación donde se cargará el stock |
| **lote_codigo** | Identificador del lote (Opcional) |
| **lote_vencimiento** | Fecha de vencimiento YYYY-MM-DD (Opcional) |
| **modelos_compatibles** | Lista de equipos/modelos separados por `;` o `,` para crear compatibilidades |

### ❌ NO incluyas estos campos:

- ❌ **id** - Se asigna automáticamente
- ❌ **creado_en** / **actualizado_en** - Se manejan automáticamente
- ❌ **existencias** - Usa `stock_inicial` + `ubicacion` en su lugar

---

## 📝 Notas Importantes:

### Auto-creación de Datos:
- **Categorías**: Si la categoría especificada no existe, el sistema la creará automáticamente.
- **Marcas**: Si la marca no existe, se creará automáticamente.

### Stock Inicial:
- Para cargar stock, **DEBES** especificar tanto `stock_inicial` como `ubicacion`.
- Si la ubicación no existe, la carga de stock para esa fila se omitirá (pero el material se creará).
- El sistema registrará un "Movimiento de Entrada" aprobado automáticamente.

### Compatibilidad:
- Puedes asignar múltiples modelos a un repuesto usando `;` como separador.
- Ejemplo: `Generador A; Compresor B`
- El sistema buscará los modelos por Nombre o Código.

---

## 🔄 Pasos para Importar (Modo Background):

1. Ve a **Inventarios > Materiales y Repuestos**
2. Click en el botón **"Importar (Background)"** en la esquina superior derecha (o en el menú de acciones).
3. **Descarga el Formato**: Usa el botón verde para obtener una plantilla vacía.
4. **Modo Verificación**:
   - Sube tu archivo y marca "Solo verificar".
   - El sistema validará qué SKUs ya existen y cuáles son nuevos sin hacer cambios.
   - Si faltan SKUs, podrás descargar un reporte de faltantes.
5. **Importación Real**:
   - Sube tu archivo (sin marcar verificación).
   - Confirma la vista previa de cambios (Nuevos vs Actualizados).
   - Espera a que la barra de progreso llegue al 100%.

---

## ⚠️ Troubleshooting:

### Error: "Stock insuficiente"
- No aplica al importar, pero asegúrate de que `stock_inicial` sea positivo.

### Error: "Invalid decimal literal"
- Asegúrate de usar punto `.` para decimales (ej: `10.50`), no comas.

### Duplicados de SKU
- Si un SKU ya existe en el sistema, la importación **ACTUALIZARÁ** los datos de ese material con la información del archivo (Nombre, Marca, etc.).
