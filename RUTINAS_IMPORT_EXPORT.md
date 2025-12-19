# Importación y Exportación de Rutinas

## 📊 Exportar Rutinas

1. Ve a **Mantenimiento > Rutinas**
2. Click en **"Export"** 
3. Selecciona formato (CSV, Excel, etc.)
4. Descarga el archivo

### Columnas en la exportación:

| Columna | Descripción |
|---------|-------------|
| **id** | ID de la rutina |
| **nombre** | Nombre de la rutina |
| **categoria_nombre** | Nombre de la categoría |
| **categoria_ruta** | Ruta completa de la categoría (ej: Eléctrica → Motores) |
| **frecuencia_nombre** | Nombre de la frecuencia |
| **tiempo_estimado** | Tiempo estimado en formato HH:MM:SS |
| **cantidad_tecnicos** | Cantidad de técnicos requeridos |
| **descripcion** | Descripción detallada |

---

## 📥 Importar Rutinas

### ✅ Formato del archivo CSV/Excel:

**Solo necesitas estas columnas:**
```csv
nombre,categoria_nombre,frecuencia_nombre,tiempo_estimado,cantidad_tecnicos,descripcion
Inspección de transformadores,Transformadores,Mensual,01:00:00,1,Inspección visual completa
Limpieza de aires,Climatización,Semanal,00:30:00,2,Limpieza de filtros
```

### 🎯 Columnas Requeridas:

| Columna | ¿Requerida? | Formato | Ejemplo |
|---------|-------------|---------|---------|
| **nombre** | ✅ SÍ | Texto | "Inspección de transformadores" |
| **categoria_nombre** | ⚪ Opcional | Nombre exacto | "Transformadores" |
| **frecuencia_nombre** | ⚪ Opcional | Nombre exacto | "Mensual" |
| **tiempo_estimado** | ⚪ Opcional | HH:MM:SS | "01:30:00" |
| **cantidad_tecnicos** | ⚪ Opcional | Número entero | 2 |
| **descripcion** | ⚪ Opcional | Texto | "Descripción detallada..." |

### ❌ NO incluyas estos campos:

- ❌ **id** - Se asigna automáticamente
- ❌ **categoria_ruta** - Se calcula automáticamente
- ❌ **creado_en** / **actualizado_en** - Se manejan automáticamente

---

## 📝 Notas Importantes:

### Categorías y Frecuencias:
- **Categorías**: Pueden ser de cualquier nivel (ej: Eléctrica, Transformadores, etc.)
- **Búsqueda inteligente**: El sistema busca la categoría por nombre + padre si es necesario
- Deben existir previamente o importarse primero en **Categorías**

### Formato de tiempo_estimado:
- **Formato**: `HH:MM:SS` (horas:minutos:segundos)
- **Ejemplos válidos**:
  - `01:00:00` = 1 hora
  - `00:30:00` = 30 minutos
  - `02:30:00` = 2 horas y 30 minutos
  - `00:15:00` = 15 minutos

### Cantidad de técnicos:
- Debe ser un número entero positivo
- Por defecto: 1

---

## 📚 Ejemplo Completo:

```csv
nombre,categoria_nombre,frecuencia_nombre,tiempo_estimado,cantidad_tecnicos,descripcion
Inspección visual de transformadores,Transformadores,Mensual,01:00:00,1,Inspección visual completa
Medición de temperatura en motores,Motores,Semanal,00:30:00,1,Medición con termómetro
Limpieza de aires acondicionados,Climatización,Mensual,02:00:00,2,Limpieza de filtros
Prueba de generadores,Generadores,Mensual,01:30:00,2,Prueba de arranque
Inspección contra incendio,Seguridad,Trimestral,02:00:00,2,Inspección de sistemas
```

---

## 🔄 Pasos para Importar:

1. Ve a **Mantenimiento > Rutinas**
2. Click en **"Import"**
3. Selecciona formato (CSV, Excel, etc.)
4. Sube tu archivo
5. Click en **"Submit"**
6. **Revisa la vista previa**
7. Click en **"Confirm import"**

---

## ⚠️ Troubleshooting:

### Error: "Categoria matching query does not exist"
- **Causa**: El nombre de categoría no existe o está mal escrito
- **Solución**: Verifica que exista en **Mantenimiento > Categorías**

### Error: "Frecuencia matching query does not exist"
- **Causa**: El nombre de frecuencia no existe o está mal escrito
- **Solución**: Verifica que exista en **Mantenimiento > Frecuencias**

### Error: "Invalid duration format"
- **Causa**: El formato de tiempo_estimado es incorrecto
- **Solución**: Usa formato `HH:MM:SS` (ej: `01:30:00`)

---

## 💡 Tips:

1. **Exporta primero** un par de rutinas existentes para ver el formato correcto
2. **Crea subdisciplinas y frecuencias** antes de importar rutinas nuevas
3. **Usa el archivo `rutinas_ejemplo.csv`** como plantilla
4. **Importa en lotes pequeños** para facilitar la detección de errores
5. El campo **disciplina_nombre** en exportación es solo informativo (se calcula automáticamente)
