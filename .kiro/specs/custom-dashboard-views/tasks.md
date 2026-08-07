# Implementation Plan: Vistas Personalizadas del Dashboard

## Overview

Implementación de la funcionalidad de vistas personalizadas para el Dashboard de Requisiciones. Se construye en capas: primero el modelo y API backend, luego la lógica frontend (columnas, ordenamiento, vistas), y finalmente la integración completa con persistencia.

## Tasks

- [x] 1. Modelo Django y migración
  - [x] 1.1 Crear modelo `DashboardView` en `presupuestos/models.py`
    - Agregar el modelo con los campos: user (FK), name, columns (JSONField), sort_column, sort_direction, is_last_used, created_at, updated_at
    - Definir `unique_together = ['user', 'name']` y `ordering = ['name']`
    - Generar y aplicar la migración con `makemigrations` y `migrate`
    - _Requisitos: 3.3, 4.5_

- [x] 2. API REST de vistas personalizadas
  - [x] 2.1 Crear archivo `presupuestos/views_dashboard_api.py` con los endpoints
    - `POST /presupuestos/requisiciones/dashboard/api/views/` → crear vista (validar nombre no vacío, no duplicado, máximo 10)
    - `GET /presupuestos/requisiciones/dashboard/api/views/` → listar vistas del usuario autenticado
    - `DELETE /presupuestos/requisiciones/dashboard/api/views/<pk>/` → eliminar vista (verificar pertenencia)
    - `POST /presupuestos/requisiciones/dashboard/api/views/<pk>/apply/` → marcar como última usada (desmarcar las demás)
    - `POST /presupuestos/requisiciones/dashboard/api/views/reset/` → limpiar última usada del usuario
    - Todas las vistas con `@login_required` y respuestas `JsonResponse`
    - _Requisitos: 3.3, 3.6, 3.7, 3.8, 3.9, 3.10, 3.11, 4.1, 4.6_

  - [x] 2.2 Registrar URLs de la API en `presupuestos/urls.py`
    - Agregar las rutas bajo el path `requisiciones/dashboard/api/views/`
    - _Requisitos: 3.3_

  - [ ]* 2.3 Escribir tests unitarios para la API (Django TestCase)
    - Probar creación exitosa, validación de nombre vacío, nombre duplicado, límite de 10
    - Probar eliminación exitosa y verificación de pertenencia (no acceder a vistas ajenas)
    - Probar apply (marcar última usada) y reset (limpiar última usada)
    - Verificar status codes (200, 201, 400, 404) y estructura JSON
    - _Requisitos: 3.3, 3.6, 3.7, 3.8, 3.9, 3.10, 4.1, 4.6_

- [x] 3. Checkpoint - Verificar backend
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Frontend: Módulo ColumnSelector y TableManager
  - [x] 4.1 Crear el módulo JavaScript `DashboardCustomizer` con sub-módulos ColumnSelector y TableManager
    - Definir constantes `COLUMNS_ORDER`, `DEFAULT_COLUMNS`, `SORTABLE_COLUMNS`, `NON_REMOVABLE`, `COLUMN_DEFS`
    - Implementar `TableManager` para manipular las columnas del DOM en ambas tablas (Resumen General y Mis Requisiciones)
    - Implementar `ColumnSelector` con panel dropdown de 14 checkboxes, casilla "Acciones" deshabilitada
    - Al activar una columna, insertarla en la posición correcta según `COLUMNS_ORDER`
    - Al desactivar una columna, removerla preservando datos de filas existentes
    - Impedir desactivar la última columna de datos (mostrar mensaje con SweetAlert2)
    - Cerrar panel al hacer clic fuera o presionar Escape
    - Aplicar cambios de columnas a ambas tablas simultáneamente
    - _Requisitos: 1.1, 1.2, 1.3, 1.4, 1.5, 1.7, 1.8, 5.1, 5.4, 5.5_

  - [x] 4.2 Implementar sub-módulo `Persistence` para localStorage
    - Guardar/recuperar columnas visibles en `dashboard_columns`
    - Guardar/recuperar criterio de ordenamiento en `dashboard_sort_col` y `dashboard_sort_dir`
    - Manejar JSON inválido con reset a Columnas_Default
    - Manejar localStorage no disponible (degradación elegante)
    - _Requisitos: 1.9, 4.3_

  - [ ]* 4.3 Escribir property tests para ColumnSelector (fast-check + vitest)
    - **Property 1: Activación de columna inserta en posición correcta**
    - **Valida: Requisito 1.3**
    - **Property 2: Desactivación de columna preserva datos restantes**
    - **Valida: Requisito 1.4**
    - **Property 3: Invariante de columna Acciones**
    - **Valida: Requisito 1.5**
    - **Property 4: Invariante de mínimo una columna de datos**
    - **Valida: Requisito 1.7**
    - **Property 5: Persistencia round-trip en localStorage**
    - **Valida: Requisito 1.9**
    - **Property 15: Configuración de columnas se aplica a ambas pestañas**
    - **Valida: Requisitos 5.1, 5.5**

- [x] 5. Frontend: Módulo SortManager
  - [x] 5.1 Implementar sub-módulo `SortManager` con ordenamiento en cliente
    - Ciclo de 3 estados al hacer clic en encabezado: ascendente → descendente → sin orden (reset a Fecha desc)
    - Comparadores por tipo de dato: alfanumérico, cronológico, alfabético, severidad (Normal < Alta < Urgencia < Emergencia), numérico
    - Indicador visual de dirección en el encabezado de la columna activa
    - Excluir columnas O/C y Acciones del ordenamiento (sin cursor interactivo)
    - Sub-ordenamiento por Fecha descendente para valores duplicados (estabilidad)
    - Aplicar ordenamiento solo a la pestaña activa (aislamiento entre pestañas)
    - _Requisitos: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 5.2, 5.3_

  - [ ]* 5.2 Escribir property tests para SortManager (fast-check + vitest)
    - **Property 6: Ordenamiento produce orden correcto por tipo de dato**
    - **Valida: Requisitos 2.1, 2.2**
    - **Property 7: Estabilidad del sort — duplicados sub-ordenados por Fecha descendente**
    - **Valida: Requisito 2.8**
    - **Property 16: Ordenamiento manual aislado a la pestaña activa**
    - **Valida: Requisito 5.3**

- [x] 6. Checkpoint - Verificar lógica de columnas y ordenamiento
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Frontend: Módulo ViewManager y barra de vistas
  - [x] 7.1 Implementar sub-módulo `ViewManager` con CRUD de vistas vía API
    - Selector dropdown de vistas guardadas (ordenadas alfabéticamente)
    - Botón "Guardar Vista" habilitado solo cuando configuración difiere del default
    - Campo de texto para nombre (máx 100 caracteres), validar nombre no vacío/solo espacios
    - Llamar a API para crear, listar, eliminar vistas
    - Al seleccionar vista: aplicar columnas y ordenamiento, marcar como última usada vía API
    - Confirmar eliminación con SweetAlert2 antes de proceder
    - Mostrar mensaje si nombre duplicado o si se alcanzó el límite de 10 vistas
    - Manejar errores de API con toasts de SweetAlert2
    - _Requisitos: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10, 3.11_

  - [x] 7.2 Implementar botón "Restablecer Vista" y lógica de carga inicial
    - Botón "Restablecer Vista" que aplica Columnas_Default, orden Fecha desc, y llama API reset
    - Al cargar dashboard: consultar API para obtener última vista usada y aplicarla
    - Si no hay última vista o fue eliminada: cargar Columnas_Default
    - Sincronizar localStorage con la vista aplicada
    - _Requisitos: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

  - [ ]* 7.3 Escribir property tests para ViewManager (fast-check + vitest)
    - **Property 8: Botón Guardar habilitado si y solo si configuración difiere del default**
    - **Valida: Requisito 3.1**
    - **Property 9: Round-trip de guardar/cargar vista**
    - **Valida: Requisitos 3.3, 3.5**
    - **Property 10: Vistas listadas en orden alfabético**
    - **Valida: Requisito 3.4**
    - **Property 11: Nombres de vista de solo espacios rechazados**
    - **Valida: Requisito 3.8**
    - **Property 12: Nombres de vista duplicados rechazados**
    - **Valida: Requisito 3.10**
    - **Property 13: Round-trip de última vista utilizada**
    - **Valida: Requisitos 4.1, 4.2**
    - **Property 14: Cambios ad-hoc no actualizan última vista utilizada**
    - **Valida: Requisito 4.5**

- [x] 8. Integración en template del Dashboard
  - [x] 8.1 Modificar el template del dashboard para incluir la UI del personalizador
    - Agregar barra de vistas sobre las tabs (selector de vistas, botón Guardar, botón Restablecer)
    - Agregar botón "Columnas" en el `surface-header` de cada tabla
    - Incluir el JavaScript del módulo `DashboardCustomizer` (inline o como archivo estático)
    - Pasar datos de última vista usada desde el contexto Django al template (via JSON en script tag)
    - Agregar atributos `data-column-id` a los `<th>` y `<td>` de las tablas para manipulación DOM
    - _Requisitos: 1.1, 1.6, 3.4, 4.2_

  - [x] 8.2 Actualizar la vista Django del dashboard para inyectar contexto de última vista
    - En la vista que renderiza el dashboard, consultar `DashboardView` del usuario para obtener la última usada
    - Pasar al contexto del template: `last_view` (JSON con columnas y sort) o `null`
    - _Requisitos: 4.1, 4.2, 4.4_

  - [ ]* 8.3 Escribir tests de integración Django
    - Test de flujo completo: crear vista → aplicar → recargar → verificar contexto del template
    - Test de eliminación de vista activa como última usada → dashboard carga defaults
    - Test de aislamiento entre usuarios
    - _Requisitos: 3.3, 3.5, 4.1, 4.2, 4.4_

- [x] 9. Checkpoint final - Verificar integración completa
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Las tareas marcadas con `*` son opcionales y se pueden omitir para un MVP más rápido
- Cada tarea referencia requisitos específicos para trazabilidad
- Los checkpoints aseguran validación incremental
- Los property tests validan propiedades de correctitud universales del diseño
- Los tests unitarios validan ejemplos específicos y casos borde
- El frontend usa JavaScript vanilla (sin frameworks) inline en el template Django
- Se usa SweetAlert2 (ya disponible) para todas las notificaciones al usuario

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["2.1", "4.1"] },
    { "id": 2, "tasks": ["2.2", "4.2", "5.1"] },
    { "id": 3, "tasks": ["2.3", "4.3", "5.2"] },
    { "id": 4, "tasks": ["7.1", "7.2"] },
    { "id": 5, "tasks": ["7.3", "8.1", "8.2"] },
    { "id": 6, "tasks": ["8.3"] }
  ]
}
```
