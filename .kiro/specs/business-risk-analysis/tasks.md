# Implementation Plan: Business Risk Analysis

## Overview

Implementación del módulo de Análisis de Riesgos de Negocio dentro de la app `servicios` existente en Django. Se crean 8 modelos nuevos, clases Admin con SAP Fiori Horizon, vistas de dashboard y mapa de calor, tareas Celery para exportaciones y notificaciones, y tests basados en propiedades con Hypothesis.

## Tasks

- [x] 1. Modelos de datos y migraciones
  - [x] 1.1 Crear archivo `servicios/models_riesgos.py` con los modelos Riesgo, EvaluacionRiesgo y ConfiguracionRiesgoServicio
    - Implementar modelo `Riesgo` con todos los campos, choices, validaciones, ForeignKeys a Servicio/User, M2M a KPI
    - Implementar método `save()` para generación automática de código (`[CÓDIGO_SERVICIO]-R-[0001]`)
    - Implementar modelo `EvaluacionRiesgo` con cálculo automático de `nivel_riesgo` (P×I) y `zona_riesgo` en `save()`
    - Implementar modelo `ConfiguracionRiesgoServicio` con validación `clean()` de apetito + offset ≤ 25
    - Importar los nuevos modelos desde `servicios/models.py` o `models/__init__.py`
    - _Requirements: 1.1, 1.2, 1.3, 1.5, 2.1, 2.2, 2.3, 2.4, 2.6, 3.1, 3.2, 3.8_

  - [x] 1.2 Crear modelos PlanTratamiento, AccionTratamiento y RevisionRiesgo en `servicios/models_riesgos.py`
    - Implementar `PlanTratamiento` con validación `clean()` de fecha_limite > fecha_inicio
    - Implementar `AccionTratamiento` con estados y fecha_completada
    - Implementar `RevisionRiesgo` con validadores de rango en probabilidad/impacto
    - _Requirements: 4.1, 4.4, 4.5, 5.1, 5.4_

  - [x] 1.3 Crear modelo RiesgoHistorial con inmutabilidad y modelo RiesgoKPI (tabla intermedia)
    - Implementar `RiesgoHistorial` con override de `delete()` y `save()` para impedir modificación/eliminación
    - Implementar tabla intermedia `RiesgoKPI` si se necesita validación de mismo Servicio (o usar signal en M2M through)
    - Implementar permisos personalizados en `Meta.permissions` del modelo `Riesgo` (`approve_plantratamiento`, `configure_apetito`)
    - _Requirements: 6.1, 6.2, 6.4, 7.1, 7.2, 11.4_

  - [x] 1.4 Generar y aplicar migraciones
    - Ejecutar `python manage.py makemigrations servicios`
    - Ejecutar `python manage.py migrate`
    - Verificar que las migraciones se aplican sin errores
    - _Requirements: 1.1, 2.1, 3.1, 4.1, 5.1, 6.1_

- [x] 2. Lógica de negocio en modelos
  - [x] 2.1 Implementar lógica de generación de código único por Servicio
    - Método en `Riesgo.save()` que busca el último código secuencial del Servicio y genera el siguiente
    - Manejar concurrencia con `select_for_update` o `F()` expressions
    - _Requirements: 1.5_

  - [ ]* 2.2 Write property test: Risk Code Generation Uniqueness and Format
    - **Property 2: Risk Code Generation Uniqueness and Format**
    - **Validates: Requirements 1.5**
    - Generar secuencias aleatorias de creación de riesgos para múltiples servicios, verificar formato y unicidad

  - [x] 2.3 Implementar lógica de clasificación de estado por apetito/tolerancia
    - Método en `Riesgo` que calcula `estado_apetito` basado en riesgo residual vs umbrales del Servicio
    - Signal o método llamado al guardar `EvaluacionRiesgo` de tipo RESIDUAL
    - _Requirements: 3.3, 3.4, 3.5_

  - [ ]* 2.4 Write property test: Risk Level Calculation and Zone Classification
    - **Property 3: Risk Level Calculation and Zone Classification**
    - **Validates: Requirements 2.3, 2.4, 8.2**
    - Generar todas combinaciones P∈[1,5], I∈[1,5] y verificar cálculo correcto

  - [ ]* 2.5 Write property test: Risk State Classification by Appetite and Tolerance
    - **Property 4: Risk State Classification by Appetite and Tolerance**
    - **Validates: Requirements 3.3, 3.4, 3.5**
    - Generar tuplas (residual, apetito, offset) y verificar clasificación correcta

  - [x] 2.6 Implementar recálculo masivo de estados al cambiar apetito/tolerancia
    - Task o método que recalcula `estado_apetito` de todos los riesgos activos del Servicio
    - Debe completarse en <5 segundos para 200 riesgos
    - _Requirements: 3.7_

  - [ ]* 2.7 Write property test: Batch Recalculation on Appetite/Tolerance Change
    - **Property 6: Batch Recalculation on Appetite/Tolerance Change**
    - **Validates: Requirements 3.7**
    - Generar conjuntos de riesgos con nueva configuración y verificar recálculo completo

  - [x] 2.8 Implementar auto-transición de PlanTratamiento a "Implementado"
    - Signal o método post-save en `AccionTratamiento` que verifica si todas las acciones no-canceladas están completadas
    - _Requirements: 4.6_

  - [ ]* 2.9 Write property test: Plan Auto-Implementation on Action Completion
    - **Property 9: Plan Auto-Implementation on Action Completion**
    - **Validates: Requirements 4.6**
    - Generar sets de acciones con estados mezclados y verificar transición automática

  - [x] 2.10 Implementar cálculo de próxima revisión y estado de revisión
    - Método que suma días del ciclo a la fecha de revisión completada
    - Property computed para `estado_revision` basado en días restantes
    - _Requirements: 5.4, 5.5_

  - [ ]* 2.11 Write property test: Review Cycle Next-Date Calculation
    - **Property 10: Review Cycle Next-Date Calculation**
    - **Validates: Requirements 5.4**
    - Generar fechas y ciclos aleatorios, verificar cálculo de próxima_revisión

  - [ ]* 2.12 Write property test: Review Status Classification
    - **Property 11: Review Status Classification**
    - **Validates: Requirements 5.5**
    - Generar fechas próxima_revisión vs today y verificar clasificación de estado_revision

- [x] 3. Checkpoint - Verificar modelos y lógica de negocio
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Validaciones y restricciones
  - [x] 4.1 Implementar validaciones de creación de Riesgo (campos obligatorios, longitudes)
    - Validaciones en `clean()` y/o formulario admin para campos obligatorios
    - Validaciones de longitud máxima con mensajes de error específicos
    - Preservar datos del formulario en caso de error
    - _Requirements: 1.7, 1.8_

  - [ ]* 4.2 Write property test: Risk Creation Validation
    - **Property 1: Risk Creation Validation**
    - **Validates: Requirements 1.1, 1.7, 1.8**
    - Generar conjuntos de datos random con longitudes variadas, verificar aceptación/rechazo

  - [x] 4.3 Implementar validación de vinculación KPI mismo Servicio y límite de 20
    - Validar en signal `m2m_changed` o en modelo through que KPI pertenece al mismo Servicio
    - Validar máximo 20 KPIs por Riesgo
    - _Requirements: 1.4, 7.1, 7.2_

  - [ ]* 4.4 Write property test: KPI Linking Same-Service Constraint
    - **Property 7: KPI Linking Same-Service Constraint**
    - **Validates: Requirements 1.4, 7.1, 7.2**
    - Generar combinaciones riesgo-KPI-servicio y verificar aceptación/rechazo

  - [x] 4.5 Implementar validación condicional de PlanTratamiento por estrategia
    - Si estrategia ∈ {Mitigar, Transferir, Evitar}: requerir al menos una acción
    - Si estrategia = Aceptar: requerir justificación, no requerir acciones
    - Validación de nivel_riesgo_esperado vs nivel_riesgo residual actual (advertencia)
    - _Requirements: 4.2, 4.3, 4.8, 4.9_

  - [ ]* 4.6 Write property test: Treatment Plan Strategy-Conditional Validation
    - **Property 8: Treatment Plan Strategy-Conditional Validation**
    - **Validates: Requirements 4.2, 4.3**
    - Generar planes con estrategia y acciones aleatorias, verificar validación condicional

  - [ ]* 4.7 Write property test: Appetite/Tolerance Configuration Validation
    - **Property 5: Appetite/Tolerance Configuration Validation**
    - **Validates: Requirements 3.1, 3.2, 3.8**
    - Generar pares (apetito, offset) aleatorios y verificar aceptación/rechazo

- [x] 5. Historial y trazabilidad
  - [x] 5.1 Implementar creación automática de registros de historial
    - Signal o método post-save en EvaluacionRiesgo para crear RiesgoHistorial
    - Signal en AccionTratamiento para registrar cambios de estado
    - Signal en RevisionRiesgo para registrar revisión completada
    - Signal en KPI para registrar desvinculación por eliminación
    - _Requirements: 6.1, 6.2, 7.7_

  - [ ]* 5.2 Write property test: Audit Trail Creation on Modifications
    - **Property 12: Audit Trail Creation on Modifications**
    - **Validates: Requirements 6.1, 6.2**
    - Generar cambios aleatorios en evaluaciones y verificar creación de historial

  - [ ]* 5.3 Write property test: History Record Immutability
    - **Property 13: History Record Immutability**
    - **Validates: Requirements 6.4**
    - Crear registros de historial e intentar delete/update, verificar PermissionError

- [x] 6. Checkpoint - Verificar validaciones e historial
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Django Admin con SAP Fiori Horizon
  - [x] 7.1 Crear archivo `servicios/admin_riesgos.py` con RiesgoAdmin
    - Heredar de `ImportExportModelAdmin`
    - Configurar `change_list_template` con SAP Fiori Horizon (misma plantilla que KPIAdmin)
    - Incluir variables CSS Fiori y enlace "Editar Fiori"
    - Configurar `list_display`, `list_filter` (Servicio, Categoría, Zona, Estado), `search_fields`
    - Ordenamiento por defecto por `nivel_riesgo` descendente
    - Inline de `EvaluacionRiesgo` (StackedInline)
    - _Requirements: 11.1, 1.6_

  - [x] 7.2 Implementar acciones masivas en RiesgoAdmin
    - Acción: Reasignar Responsable_Riesgo (con selección de usuario)
    - Acción: Cambiar Ciclo_Revisión (con selección de periodicidad)
    - Acción: Exportar selección en Excel via django-import-export
    - Validación: cancelar si no se selecciona usuario destino válido
    - _Requirements: 11.2, 11.6_

  - [x] 7.3 Crear PlanTratamientoAdmin y configurar admin de modelos auxiliares
    - `PlanTratamientoAdmin` con inline de `AccionTratamiento`
    - Validación de permiso `approve_plantratamiento` al cambiar estado a "Aprobado"
    - Registrar `ConfiguracionRiesgoServicio` con permiso `configure_apetito`
    - _Requirements: 11.1, 11.4, 11.5_

  - [x] 7.4 Agregar RiesgoInline en ServicioAdmin existente
    - TabularInline de solo lectura con resumen de riesgos por Zona_Riesgo
    - Enlace a la Matriz_Riesgos del Servicio
    - _Requirements: 11.3_

  - [x] 7.5 Crear `servicios/resources_riesgos.py` con RiesgoResource y PlanTratamientoResource
    - Configurar campos de exportación Excel según columnas requeridas (código, título, categoría, etc.)
    - Integrar con django-import-export
    - _Requirements: 10.1, 10.4_

- [x] 8. Checkpoint - Verificar Django Admin
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Vistas: Panel de Riesgos (Dashboard)
  - [x] 9.1 Crear `servicios/views_riesgos.py` con `panel_riesgos_view`
    - Calcular indicadores: total activos, distribución por zona (cantidad y %), distribución por categoría (cantidad y %), % planes implementados
    - Top 10 riesgos por nivel_riesgo residual descendente
    - Hasta 20 revisiones vencidas y 20 acciones vencidas ordenadas por antigüedad
    - Filtros por Servicio, Categoría, período de tiempo
    - Default: todos los Servicios, últimos 12 meses
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.7_

  - [x] 9.2 Crear template `servicios/templates/servicios/riesgos/panel_riesgos.html`
    - Layout SAP Fiori Horizon con cards para indicadores
    - Sección de KPIs en riesgo (incumplimiento/parcial con zona Alta/Crítica, máx 10)
    - Mensaje cuando no hay resultados para los filtros aplicados
    - _Requirements: 7.6, 9.1, 9.7_

  - [ ]* 9.3 Write property test: Dashboard Statistics Calculation
    - **Property 15: Dashboard Statistics Calculation**
    - **Validates: Requirements 9.1**
    - Generar conjuntos de riesgos con atributos variados y verificar cálculos estadísticos

- [x] 10. Vistas: Mapa de Calor
  - [x] 10.1 Implementar `mapa_calor_view` y `mapa_calor_consolidado_view`
    - Grid 5×5 con eje X = Impacto, eje Y = Probabilidad
    - Codificación por colores: verde (Bajo), amarillo (Medio), naranja (Alto), rojo (Crítico)
    - Mostrar riesgo inherente (borde punteado) y residual (borde sólido) por cada riesgo
    - Toggle para mostrar solo inherente, solo residual o ambos
    - Tooltip con código y título (máx 10 riesgos por celda + indicador de total)
    - Líneas de Apetito_Riesgo y Tolerancia_Riesgo en la matriz
    - Navegación a detalle del riesgo al seleccionar
    - Mensaje para Servicios sin riesgos activos
    - Mapa consolidado: agrupa todos los Servicios, muestra conteo por celda
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8, 3.6_

  - [x] 10.2 Crear template `servicios/templates/servicios/riesgos/mapa_calor.html`
    - Implementar grid 5×5 con Canvas o SVG
    - Tooltips interactivos con JavaScript
    - Controles de toggle para tipo de visualización
    - Estilo SAP Fiori Horizon
    - _Requirements: 8.1, 8.3, 8.6, 8.8_

  - [ ]* 10.3 Write property test: Filter Results Correctness
    - **Property 14: Filter Results Correctness**
    - **Validates: Requirements 1.6, 2.5**
    - Generar conjuntos de riesgos con filtros aleatorios y verificar resultados correctos

- [x] 11. Vistas: Historial y Timeline
  - [x] 11.1 Implementar `historial_riesgo_view`
    - Timeline cronológica descendente con paginación de 20 registros
    - Filtros por tipo de evento (evaluación, tratamiento, revisión) y rango de fechas
    - Gráfico de tendencia (línea) con Chart.js si hay ≥2 evaluaciones
    - Mensaje informativo si hay <2 evaluaciones
    - _Requirements: 6.3, 6.5, 6.6, 6.7_

  - [x] 11.2 Crear template `servicios/templates/servicios/riesgos/historial.html`
    - Layout de timeline con registros paginados
    - Gráfico Chart.js con eje X = fecha, eje Y = nivel_riesgo (1-25)
    - Filtros interactivos
    - _Requirements: 6.3, 6.5_

- [x] 12. URL routing y navegación
  - [x] 12.1 Crear `servicios/urls_riesgos.py` y registrar en URLconf principal
    - Definir URL patterns para todas las vistas: panel, mapa-calor, historial, exports
    - Incluir en `servicios/urls.py` o directamente en el URLconf del proyecto
    - _Requirements: 9.1, 8.1, 6.3, 10.1_

- [x] 13. Checkpoint - Verificar vistas y templates
  - Ensure all tests pass, ask the user if questions arise.

- [x] 14. Tareas Celery asíncronas
  - [x] 14.1 Crear `servicios/tasks_riesgos.py` con tareas de exportación
    - `export_riesgos_excel_task`: genera XLSX async para >100 registros, archivo disponible 72h
    - `export_matriz_pdf_task`: genera PDF con mapa calor y resumen ejecutivo
    - Timeout de 300 segundos, notificación de error si falla
    - Fallback síncrono si Celery no disponible (CELERY_TASK_ALWAYS_EAGER)
    - _Requirements: 10.1, 10.2, 10.3, 10.5, 10.6_

  - [x] 14.2 Crear tareas de notificación periódica
    - `check_review_notifications`: notificar revisiones a 7 días y revisiones vencidas
    - `check_overdue_actions`: notificar acciones de planes con fecha límite vencida
    - Escalamiento a responsable de Servicio si revisión vencida >15 días
    - Configurar en Celery Beat schedule (ejecución diaria)
    - _Requirements: 4.7, 5.2, 5.3, 5.6, 5.7_

  - [x] 14.3 Implementar signal para alertas de cambio de estado KPI
    - Signal post-save en KPI: si cambia a INCUMPLIMIENTO, generar alerta en Panel y detalle de riesgos asociados
    - Signal pre-delete en KPI: registrar desvinculación en historial de riesgos afectados
    - _Requirements: 7.3, 7.7_

- [x] 15. Exportación y reportes
  - [x] 15.1 Implementar vistas de exportación con lógica sync/async
    - `export_riesgos_excel_view`: si ≤100 registros exportar sync, si >100 dispatch Celery task
    - `export_matriz_pdf_view`: generar PDF con template + wkhtmltopdf o weasyprint
    - Filtro por estado (activo/cerrado/ambos) antes de exportar
    - Mantener filtros para reintento en caso de error
    - _Requirements: 10.1, 10.2, 10.3, 10.5, 10.6_

  - [x] 15.2 Crear template PDF `servicios/templates/servicios/riesgos/export_pdf.html`
    - Mapa de calor 5×5 renderizado estáticamente
    - Tabla de riesgos con código, título, zona, responsable
    - Resumen ejecutivo: total por zona, % planes completados, revisiones vencidas, fecha generación
    - Reporte de tendencias: gráfico de evolución mensual (1-24 meses)
    - _Requirements: 10.2, 10.3_

- [x] 16. Integración KPI y Panel de alertas
  - [x] 16.1 Implementar sección KPIs en detalle de Riesgo y Riesgos en detalle de KPI
    - En detalle de Riesgo: mostrar KPIs vinculados con estado actual, ordenados por criticidad
    - En detalle/admin de KPI: mostrar Riesgos vinculados con Zona_Riesgo, ordenados por nivel descendente
    - Sección en Panel: KPIs en INCUMPLIMIENTO/PARCIAL con riesgos en zona Alta/Crítica (máx 10)
    - _Requirements: 7.4, 7.5, 7.6_

- [x] 17. Checkpoint - Verificar integración completa
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 18. Tests unitarios y de integración
  - [ ]* 18.1 Escribir tests unitarios para modelos (`test_riesgos_models.py`)
    - Test creación correcta de Riesgo con estado inicial "Activo"
    - Test cálculo P×I para casos conocidos
    - Test transiciones de estado de PlanTratamiento
    - Test validación de fechas en PlanTratamiento
    - Test generación de código secuencial
    - _Requirements: 1.1, 1.3, 2.3, 4.5, 1.5_

  - [ ]* 18.2 Escribir tests de admin y permisos (`test_riesgos_admin.py`)
    - Test permisos `approve_plantratamiento` (rechazo sin permiso)
    - Test acciones masivas (reasignar responsable, cambiar ciclo)
    - Test inline de solo lectura en ServicioAdmin
    - _Requirements: 11.4, 11.5, 11.2, 11.3, 11.6_

  - [ ]* 18.3 Escribir tests de vistas y dashboard (`test_riesgos_views.py`)
    - Test panel carga con datos correctos
    - Test filtros de panel
    - Test mapa de calor renderiza grid correcto
    - Test historial con paginación
    - _Requirements: 9.1, 9.4, 8.1, 6.3_

  - [ ]* 18.4 Escribir tests de tareas Celery (`test_riesgos_tasks.py`)
    - Test export_riesgos_excel_task genera archivo
    - Test check_review_notifications envía notificaciones correctas
    - Test check_overdue_actions detecta acciones vencidas
    - _Requirements: 10.5, 5.2, 5.3, 4.7_

  - [ ]* 18.5 Escribir tests de exportación (`test_riesgos_export.py`)
    - Test columnas Excel correctas según requirement
    - Test generación PDF con estructura requerida
    - Test fallback síncrono cuando Celery no disponible
    - _Requirements: 10.1, 10.2, 10.6_

- [x] 19. Final checkpoint - Verificar suite completa de tests
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties defined in the design document
- Unit tests validate specific examples and edge cases
- The project uses Python/Django, django-import-export, Celery, and Hypothesis for property-based tests
- All admin classes follow the SAP Fiori Horizon styling pattern established in KPIAdmin and AuditoriaAdmin
- Templates reuse `core/fiori_tokens.html` for consistent CSS variables

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "1.3"] },
    { "id": 2, "tasks": ["1.4"] },
    { "id": 3, "tasks": ["2.1", "2.3", "2.6", "2.8", "2.10", "4.1", "4.3", "4.5"] },
    { "id": 4, "tasks": ["2.2", "2.4", "2.5", "2.7", "2.9", "2.11", "2.12", "4.2", "4.4", "4.6", "4.7"] },
    { "id": 5, "tasks": ["5.1"] },
    { "id": 6, "tasks": ["5.2", "5.3"] },
    { "id": 7, "tasks": ["7.1", "7.5"] },
    { "id": 8, "tasks": ["7.2", "7.3", "7.4"] },
    { "id": 9, "tasks": ["9.1", "10.1", "11.1", "12.1"] },
    { "id": 10, "tasks": ["9.2", "9.3", "10.2", "10.3", "11.2"] },
    { "id": 11, "tasks": ["14.1", "14.2", "14.3"] },
    { "id": 12, "tasks": ["15.1", "15.2", "16.1"] },
    { "id": 13, "tasks": ["18.1", "18.2", "18.3", "18.4", "18.5"] }
  ]
}
```
