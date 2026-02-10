# Propuesta de Gestión de Lotes y Vencimientos

Esta propuesta detalla la arquitectura para implementar el control de trazabilidad por Lotes y Fechas de Vencimiento en el módulo de Inventarios.

## 1. Diagnóstico Actual

Actualmente, el sistema gestiona existencias usando el modelo `StockRecord`, que agrupa cantidades por:
`Material + Ubicación + Ubicación Específica`.

**Limitación:** Si tienes 100 unidades de "Paracetamol" en el "Estante A", el sistema no diferencia si 50 vencen mañana y 50 el próximo año.

## 2. Cambios en el Modelo de Datos

### A. Nuevo Modelo: `Lote`
Crearemos una entidad separada para gestionar los lotes, permitiendo trazabilidad y re-utilización del mismo identificador de lote en diferentes ubicaciones (si fuera necesario).

```python
class Lote(models.Model):
    material = models.ForeignKey(Material, related_name='lotes')
    codigo = models.CharField(max_length=50) # El identificador impreso en la caja
    fecha_fabricacion = models.DateField(null=True, blank=True)
    fecha_vencimiento = models.DateField(null=True, blank=True)
    
    # Metadatos para trazabilidad
    proveedor = models.ForeignKey(Proveedor, null=True, blank=True) 
    costo_unitario = models.DecimalField(...) # Para valoración de inventario real (FIFO/LIFO)

    class Meta:
        unique_together = ('material', 'codigo') # Un material no puede tener 2 lotes con el mismo código
```

### B. Actualización de `StockRecord`
La tabla de existencias debe desglosarse ahora por lote.

*   **Antes:** `Material + Ubicación -> 100 Unidades`
*   **Ahora:** 
    *   `Material + Ubicación + Lote A (Vence 2024) -> 50 Unidades`
    *   `Material + Ubicación + Lote B (Vence 2025) -> 50 Unidades`

Se agregará el campo `lote` (ForeignKey) a `StockRecord` y se actualizará el `unique_together`.

### C. Actualización de `MovimientoInventario`
Cada movimiento debe especificar a qué lote afecta.
*   **Entradas:** Obligan a crear o seleccionar un lote existente.
*   **Salidas:** Requieren descontar de un lote específico.

## 3. Estrategia de Flujo de Trabajo (FEFO)

Implementaremos la lógica **FEFO (First Expired, First Out)** - *Primero en expirar, primero en salir*.

### Flujo de Entrada (Compras/Recepciones)
Al recibir mercancía, el usuario **debe** capturar:
1.  Cantidad
2.  Ubicación
3.  **Código de Lote** (Nuevo campo)
4.  **Fecha de Vencimiento** (Nuevo campo, obligatorio para materiales perecederos)

### Flujo de Salida (Despachos/Consumo)
Al solicitar material (ej. para una Orden de Trabajo), el sistema operará en dos niveles:

1.  **Solicitud Genérica:** El usuario pide "10 cajas de Guantes". NO elige lote.
2.  **Sugerencia de Picking (Backend):** Cuando el Almacenista va a despachar (Liquidar), el sistema le sugiere/obliga a descontar del lote **próximo a vencer**.

**Algoritmo de Liquidación:**
```python
def liquidar_salida(cantidad_solicitada):
    lotes_disponibles = StockRecord.objects.filter(material=m).order_by('lote__fecha_vencimiento')
    
    for stock in lotes_disponibles:
        if cantidad_solicitada <= 0: break
        
        tomar = min(cantidad_solicitada, stock.cantidad)
        stock.cantidad -= tomar
        stock.save()
        cantidad_solicitada -= tomar
```

## 4. Impacto en Importación Masiva

El archivo de Excel para importación de inventario (`IMPORT_MATERIALES`) deberá incluir columnas nuevas:
*   `lote_codigo`
*   `lote_vencimiento`

Si se usan estas columnas durante la carga inicial, el sistema creará los objetos `Lote` automáticamente.

## 5. Estrategia de Migración (Importante)

Para los materiales ya existentes que tienen stock pero no lote:

1.  **Opción A (Lote Genérico):**
    Crear automáticamente un lote "S/L" (Sin Lote) o "INICIAL-2024" con fecha de vencimiento `null`. Todo el stock actual se moverá a este lote.

2.  **Opción B (Auditoría Obligatoria):**
    Resetear stock a 0 y obligar a hacer un "Conteo Físico" ingresando los lotes reales. (Recomendado para farmacia/químicos).

## 6. Plan de Implementación

1.  **Fase 1: Base de Datos**
    *   Crear modelo `Lote`.
    *   Migrar `StockRecord` y `MovimientoInventario` para soportar FK a `Lote`.
2.  **Fase 2: Lógica de Backend**
    *   Modificar `liquidar()` en `MovimientoInventario` para manejar descuente por lotes.
    *   Crear señales de alerta (Semáforo de vencimientos: Verde > 90 días, Amarillo < 60 días, Rojo < 30 días).
3.  **Fase 3: Interfaz de Usuario y Scanner**
    *   En las vistas de "Salida", mostrar desplegable de lotes disponibles ordenados por FEFO.
    *   En el Scanner, permitir escanear el código de lote.

---
**¿Procedemos con la implementación de la Fase 1?**
