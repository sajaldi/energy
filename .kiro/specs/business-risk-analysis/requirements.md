# Requirements Document

## Introduction

Este módulo implementa un sistema de Análisis de Riesgos de Negocio dentro de la app "servicios" existente en Django. El módulo está basado en las metodologías internacionales ISO 31000:2018, ISO 31010, COSO ERM y conceptos de FMEA/Bow-tie adaptados a riesgos empresariales. Se enfoca exclusivamente en riesgos de negocio (operacionales, financieros, estratégicos, de cumplimiento y reputacionales), no en seguridad ocupacional.

Cada Servicio contará con su propia matriz de riesgos, permitiendo identificación, evaluación, tratamiento, monitoreo y revisión continua de los riesgos que puedan afectar el desempeño del servicio y sus KPIs asociados.

## Glossary

- **Sistema_Riesgos**: El módulo de Análisis de Riesgos de Negocio dentro de la app "servicios"
- **Matriz_Riesgos**: Representación visual bidimensional de probabilidad vs impacto para un Servicio específico
- **Riesgo**: Evento potencial que puede afectar negativamente los objetivos de un Servicio
- **Servicio**: Unidad organizacional existente en el modelo `Servicio` de la app "servicios"
- **Categoría_Riesgo**: Clasificación del riesgo según su naturaleza: Operacional, Financiero, Estratégico, Cumplimiento o Reputacional
- **Nivel_Probabilidad**: Escala cuantitativa de la frecuencia esperada de ocurrencia (1-5: Muy Baja, Baja, Media, Alta, Muy Alta)
- **Nivel_Impacto**: Escala cuantitativa de la severidad del efecto (1-5: Insignificante, Menor, Moderado, Mayor, Catastrófico)
- **Nivel_Riesgo**: Resultado calculado de Nivel_Probabilidad × Nivel_Impacto (rango 1-25)
- **Zona_Riesgo**: Clasificación del Nivel_Riesgo en zonas: Bajo (1-4), Medio (5-9), Alto (10-16), Crítico (17-25)
- **Apetito_Riesgo**: Nivel máximo de riesgo que la organización acepta perseguir en busca de sus objetivos
- **Tolerancia_Riesgo**: Variación aceptable alrededor del Apetito_Riesgo
- **Plan_Tratamiento**: Conjunto de acciones definidas para mitigar, transferir, evitar o aceptar un Riesgo
- **Responsable_Riesgo**: Usuario del sistema asignado como dueño de un Riesgo y su Plan_Tratamiento
- **Ciclo_Revisión**: Período definido para la reevaluación obligatoria de los riesgos
- **Control_Existente**: Medida ya implementada que reduce la probabilidad o el impacto de un Riesgo
- **Riesgo_Residual**: Nivel_Riesgo remanente después de aplicar los controles y planes de tratamiento
- **Mapa_Calor**: Visualización gráfica de la distribución de riesgos en la Matriz_Riesgos codificada por colores
- **KPI**: Indicador Clave de Desempeño existente en la app "servicios", vinculable a riesgos
- **Panel_Riesgos**: Vista tipo dashboard para el monitoreo consolidado de riesgos

## Requirements

### Requisito 1: Registro e Identificación de Riesgos

**User Story:** Como gestor de servicios, quiero registrar riesgos de negocio asociados a cada Servicio, para tener un inventario completo y estructurado de amenazas potenciales.

#### Criterios de Aceptación

1. THE Sistema_Riesgos SHALL permitir crear un Riesgo asociado a un Servicio con los siguientes campos obligatorios: título (máximo 200 caracteres), descripción (máximo 2000 caracteres), Categoría_Riesgo, fuente del riesgo (máximo 500 caracteres) y consecuencias potenciales (máximo 1000 caracteres); y el campo opcional: Control_Existente (máximo 1000 caracteres)
2. THE Sistema_Riesgos SHALL clasificar cada Riesgo en exactamente una Categoría_Riesgo de las siguientes: Operacional, Financiero, Estratégico, Cumplimiento o Reputacional
3. WHEN un usuario crea un Riesgo, THE Sistema_Riesgos SHALL asignar automáticamente la fecha de identificación, el usuario creador y el estado inicial "Activo"
4. THE Sistema_Riesgos SHALL permitir asociar un Riesgo a uno o más KPIs del mismo Servicio que podrían verse afectados, limitado a un máximo de 20 KPIs por Riesgo
5. THE Sistema_Riesgos SHALL generar un código único por Riesgo siguiendo el formato: [CÓDIGO_SERVICIO]-R-[NÚMERO_SECUENCIAL_4_DÍGITOS], comenzando en 0001 para cada Servicio e incrementando en 1 por cada nuevo Riesgo creado en ese Servicio
6. WHEN un usuario consulta la lista de riesgos, THE Sistema_Riesgos SHALL permitir filtrar por Servicio, Categoría_Riesgo, Zona_Riesgo y estado (Activo o Cerrado), mostrando los resultados ordenados por Nivel_Riesgo descendente como orden por defecto
7. IF un usuario intenta guardar un Riesgo sin completar alguno de los campos obligatorios (título, descripción, Categoría_Riesgo, fuente del riesgo, consecuencias potenciales), THEN THE Sistema_Riesgos SHALL rechazar la creación y mostrar un mensaje de error indicando los campos faltantes sin perder los datos ya ingresados en el formulario
8. IF un usuario intenta crear un Riesgo y el título ingresado excede los 200 caracteres o la descripción excede los 2000 caracteres, THEN THE Sistema_Riesgos SHALL rechazar la creación y mostrar un mensaje de error indicando el campo que excede el límite permitido

### Requisito 2: Evaluación y Matriz de Riesgos

**User Story:** Como gestor de servicios, quiero evaluar cada riesgo usando una matriz de probabilidad e impacto basada en ISO 31000, para priorizar las acciones de tratamiento.

#### Criterios de Aceptación

1. THE Sistema_Riesgos SHALL proporcionar una escala de Nivel_Probabilidad de 5 niveles (1: Muy Baja, 2: Baja, 3: Media, 4: Alta, 5: Muy Alta) con un descriptor cualitativo (definición textual del escenario) y un rango cuantitativo de frecuencia esperada para cada nivel
2. THE Sistema_Riesgos SHALL proporcionar una escala de Nivel_Impacto de 5 niveles (1: Insignificante, 2: Menor, 3: Moderado, 4: Mayor, 5: Catastrófico) con criterios de evaluación definidos para cada combinación de nivel y Categoría_Riesgo (Operacional, Financiero, Estratégico, Cumplimiento, Reputacional)
3. WHEN un usuario asigna Nivel_Probabilidad y Nivel_Impacto a un Riesgo, THE Sistema_Riesgos SHALL calcular el Nivel_Riesgo multiplicando ambos valores (rango resultante: 1 a 25)
4. WHEN el Nivel_Riesgo es calculado, THE Sistema_Riesgos SHALL asignar la Zona_Riesgo correspondiente: Bajo (1-4), Medio (5-9), Alto (10-16), Crítico (17-25)
5. THE Sistema_Riesgos SHALL mantener una Matriz_Riesgos por cada Servicio que muestre únicamente los riesgos con estado activo, posicionados según su Nivel_Probabilidad (eje Y) y Nivel_Impacto (eje X)
6. WHEN un usuario evalúa un Riesgo, THE Sistema_Riesgos SHALL requerir la asignación de Nivel_Probabilidad y Nivel_Impacto tanto para el riesgo inherente (sin controles) como para el Riesgo_Residual (con controles aplicados), calculando Nivel_Riesgo y Zona_Riesgo de forma independiente para cada uno
7. THE Sistema_Riesgos SHALL requerir una justificación textual obligatoria de entre 10 y 1000 caracteres para cada evaluación de Nivel_Probabilidad y Nivel_Impacto asignada
8. IF un usuario intenta guardar una evaluación de Riesgo sin haber completado Nivel_Probabilidad, Nivel_Impacto o justificación para ambas evaluaciones (inherente y residual), THEN THE Sistema_Riesgos SHALL impedir el guardado y mostrar un mensaje de error indicando los campos faltantes
9. WHEN un usuario modifica la evaluación de un Riesgo previamente evaluado, THE Sistema_Riesgos SHALL requerir una nueva justificación y recalcular automáticamente el Nivel_Riesgo y la Zona_Riesgo para la evaluación modificada

### Requisito 3: Apetito y Tolerancia al Riesgo

**User Story:** Como director de operaciones, quiero definir niveles de apetito y tolerancia al riesgo por Servicio, para establecer límites claros de aceptabilidad.

#### Criterios de Aceptación

1. THE Sistema_Riesgos SHALL permitir configurar un Apetito_Riesgo por cada Servicio, expresado como el Nivel_Riesgo máximo aceptable (valor entero entre 1 y 25)
2. THE Sistema_Riesgos SHALL permitir configurar una Tolerancia_Riesgo por cada Servicio, expresada como un valor entero de compensación (offset) entre 1 y 10 puntos por encima del Apetito_Riesgo, donde el umbral de tolerancia resultante no podrá exceder 25
3. WHEN el Riesgo_Residual de un Riesgo supera el umbral de Tolerancia_Riesgo (Apetito_Riesgo + offset) del Servicio asociado, THE Sistema_Riesgos SHALL marcar ese Riesgo con estado "Requiere Acción Inmediata"
4. WHEN el Riesgo_Residual de un Riesgo es mayor que el Apetito_Riesgo y menor o igual al umbral de Tolerancia_Riesgo (Apetito_Riesgo + offset), THE Sistema_Riesgos SHALL marcar ese Riesgo con estado "En Vigilancia"
5. WHEN el Riesgo_Residual de un Riesgo es menor o igual al Apetito_Riesgo del Servicio asociado, THE Sistema_Riesgos SHALL marcar ese Riesgo con estado "Aceptable"
6. THE Sistema_Riesgos SHALL mostrar visualmente en la Matriz_Riesgos las líneas de Apetito_Riesgo y Tolerancia_Riesgo configuradas para el Servicio, diferenciando ambos umbrales
7. WHEN un usuario modifica el Apetito_Riesgo o la Tolerancia_Riesgo de un Servicio, THE Sistema_Riesgos SHALL recalcular el estado de todos los Riesgos activos de ese Servicio conforme a los nuevos umbrales en un tiempo máximo de 5 segundos para hasta 200 riesgos activos
8. IF un usuario intenta configurar una Tolerancia_Riesgo cuyo umbral resultante (Apetito_Riesgo + offset) excede 25, THEN THE Sistema_Riesgos SHALL rechazar la configuración y mostrar un mensaje de error indicando que el umbral de tolerancia no puede superar el valor máximo de Nivel_Riesgo (25)

### Requisito 4: Plan de Tratamiento de Riesgos

**User Story:** Como gestor de servicios, quiero crear planes de tratamiento para los riesgos identificados, para reducir su probabilidad o impacto a niveles aceptables.

#### Criterios de Aceptación

1. THE Sistema_Riesgos SHALL permitir crear un Plan_Tratamiento para cada Riesgo con los campos obligatorios: estrategia de tratamiento (Mitigar, Transferir, Evitar, Aceptar), descripción de acciones (máximo 2000 caracteres), Responsable_Riesgo, fecha de inicio, fecha límite y recursos requeridos (máximo 1000 caracteres), donde la fecha límite debe ser posterior a la fecha de inicio
2. IF un Plan_Tratamiento tiene estrategia "Mitigar", "Transferir" o "Evitar", THEN THE Sistema_Riesgos SHALL requerir al menos una acción con descripción, fecha límite y Responsable_Riesgo asignado antes de permitir guardar el plan
3. IF un Plan_Tratamiento tiene estrategia "Aceptar", THEN THE Sistema_Riesgos SHALL requerir una justificación de aceptación (máximo 2000 caracteres) y no requerir acciones obligatorias
4. THE Sistema_Riesgos SHALL permitir registrar de 1 a 50 acciones dentro de un Plan_Tratamiento, cada una con los campos: descripción (máximo 500 caracteres), fecha límite, Responsable_Riesgo asignado y estado (Pendiente, En Progreso, Completada, Cancelada), donde el estado inicial es "Pendiente"
5. THE Sistema_Riesgos SHALL gestionar el Plan_Tratamiento con los estados: Borrador, Aprobado, En Ejecución, Implementado y Cancelado, donde el estado inicial es "Borrador"
6. WHEN todas las acciones no canceladas de un Plan_Tratamiento tienen estado "Completada" y existe al menos una acción con estado "Completada", THE Sistema_Riesgos SHALL cambiar el estado del Plan_Tratamiento a "Implementado"
7. WHEN la fecha límite de una acción del Plan_Tratamiento se cumple y su estado es "Pendiente" o "En Progreso", THE Sistema_Riesgos SHALL generar una notificación en el sistema para el Responsable_Riesgo asignado a dicha acción dentro de las 24 horas siguientes al vencimiento
8. THE Sistema_Riesgos SHALL registrar el Nivel_Riesgo esperado (valor entre 1 y 25) después de la implementación completa del Plan_Tratamiento, ingresado manualmente por el usuario al crear o editar el plan
9. IF el Nivel_Riesgo esperado ingresado es mayor o igual al Nivel_Riesgo residual actual del Riesgo asociado, THEN THE Sistema_Riesgos SHALL mostrar una advertencia indicando que el plan no reduciría el nivel de riesgo

### Requisito 5: Monitoreo y Ciclos de Revisión

**User Story:** Como gestor de servicios, quiero establecer ciclos de revisión periódica de los riesgos, para asegurar que las evaluaciones se mantienen actualizadas.

#### Criterios de Aceptación

1. THE Sistema_Riesgos SHALL permitir configurar un Ciclo_Revisión por cada Riesgo con periodicidad seleccionable: Mensual (30 días), Bimestral (60 días), Trimestral (90 días), Semestral (180 días) o Anual (365 días), siendo obligatoria la asignación de un Ciclo_Revisión para todo Riesgo con estado activo
2. WHEN se cumplen 7 días naturales antes de la fecha del próximo Ciclo_Revisión de un Riesgo, THE Sistema_Riesgos SHALL generar una notificación al Responsable_Riesgo indicando que la revisión se aproxima y la fecha exacta en que será requerida
3. WHEN se cumple la fecha del próximo Ciclo_Revisión de un Riesgo, THE Sistema_Riesgos SHALL generar una notificación al Responsable_Riesgo indicando que la revisión es requerida y cambiar el estado de revisión a "Revisión vencida"
4. WHEN un Responsable_Riesgo completa una revisión, THE Sistema_Riesgos SHALL requerir la nueva evaluación de Nivel_Probabilidad y Nivel_Impacto, una justificación textual del cambio o confirmación de valores (mínimo 10 caracteres, máximo 500 caracteres), calcular el nuevo Nivel_Riesgo y actualizar la fecha de la próxima revisión sumando el período del Ciclo_Revisión configurado a la fecha de la revisión completada
5. THE Sistema_Riesgos SHALL mantener un indicador visual del estado de revisión de cada Riesgo basado en días naturales restantes hasta la próxima fecha de revisión: "Al día" (más de 7 días restantes), "Próxima revisión" (entre 1 y 7 días restantes) o "Revisión vencida" (0 o menos días restantes)
6. WHILE un Riesgo tiene estado de revisión "Revisión vencida", THE Sistema_Riesgos SHALL resaltar ese Riesgo en color rojo en todas las vistas de listado y en el Panel_Riesgos
7. IF un Riesgo permanece con estado "Revisión vencida" por más de 15 días naturales, THEN THE Sistema_Riesgos SHALL generar una notificación de escalamiento al responsable del Servicio asociado indicando el código del Riesgo, el Responsable_Riesgo asignado y la cantidad de días de atraso

### Requisito 6: Historial y Trazabilidad

**User Story:** Como auditor interno, quiero consultar el historial completo de cada riesgo, para verificar la evolución de las evaluaciones y las acciones tomadas.

#### Criterios de Aceptación

1. WHEN un usuario modifica la evaluación de un Riesgo (Nivel_Probabilidad, Nivel_Impacto o Control_Existente), THE Sistema_Riesgos SHALL crear un registro histórico que contenga: los valores anteriores, los valores nuevos, la fecha y hora del cambio, el usuario que realizó el cambio y una justificación obligatoria de al menos 10 caracteres
2. WHEN una acción de un Plan_Tratamiento cambia de estado o se completa una revisión del Ciclo_Revisión, THE Sistema_Riesgos SHALL crear un registro histórico con el tipo de evento, los valores anteriores y nuevos, la fecha y hora, y el usuario que realizó la operación
3. THE Sistema_Riesgos SHALL permitir visualizar la línea de tiempo de un Riesgo mostrando todos los registros históricos (cambios de evaluación, cambios de estado de acciones de tratamiento y revisiones realizadas) en orden cronológico descendente con paginación de 20 registros por página
4. THE Sistema_Riesgos SHALL mantener el historial de cambios de forma inmutable, impidiendo la eliminación o modificación de registros históricos a todos los usuarios del sistema incluidos superusuarios
5. WHEN un usuario consulta el historial de un Riesgo que cuenta con 2 o más evaluaciones registradas, THE Sistema_Riesgos SHALL mostrar un gráfico de línea con el eje X representando la fecha de cada evaluación y el eje Y representando el Nivel_Riesgo (escala 1-25)
6. IF un Riesgo tiene menos de 2 evaluaciones registradas, THEN THE Sistema_Riesgos SHALL mostrar un mensaje indicando que se requieren al menos 2 evaluaciones para generar el gráfico de tendencia
7. WHEN un usuario consulta la línea de tiempo de un Riesgo, THE Sistema_Riesgos SHALL permitir filtrar los registros históricos por tipo de evento (evaluación, tratamiento, revisión) y por rango de fechas

### Requisito 7: Integración con KPIs Existentes

**User Story:** Como gestor de servicios, quiero vincular riesgos con KPIs existentes, para identificar qué indicadores podrían verse comprometidos si un riesgo se materializa.

#### Criterios de Aceptación

1. THE Sistema_Riesgos SHALL permitir vincular un Riesgo a uno o más KPIs del mismo Servicio mediante una relación muchos a muchos, con un máximo de 20 KPIs vinculados por Riesgo
2. IF un usuario intenta vincular un KPI que pertenece a un Servicio diferente al del Riesgo, THEN THE Sistema_Riesgos SHALL rechazar la operación y mostrar un mensaje indicando que solo se pueden vincular KPIs del mismo Servicio
3. WHEN un KPI vinculado cambia su estado de "CUMPLIMIENTO" o "PARCIAL" a "INCUMPLIMIENTO", THE Sistema_Riesgos SHALL generar una alerta visible en el Panel_Riesgos y en la vista de detalle de cada Riesgo asociado, dirigida al Responsable_Riesgo, indicando posible materialización del riesgo
4. THE Sistema_Riesgos SHALL mostrar en la vista de detalle de un Riesgo los KPIs vinculados con su estado actual (Cumplimiento, Parcial, Incumplimiento) ordenados por estado de mayor a menor criticidad (Incumplimiento primero, luego Parcial, luego Cumplimiento)
5. THE Sistema_Riesgos SHALL mostrar en la vista de detalle de un KPI los Riesgos vinculados con su Zona_Riesgo actual, ordenados por Nivel_Riesgo de mayor a menor
6. WHEN un usuario consulta el Panel_Riesgos, THE Sistema_Riesgos SHALL mostrar una sección con los KPIs en estado "INCUMPLIMIENTO" o "PARCIAL" que tienen Riesgos asociados en Zona_Riesgo Alta o Crítica, limitada a un máximo de 10 registros ordenados por Zona_Riesgo descendente
7. IF un KPI vinculado a uno o más Riesgos es eliminado, THEN THE Sistema_Riesgos SHALL eliminar la vinculación y registrar en el historial de cada Riesgo afectado que el KPI fue desvinculado por eliminación

### Requisito 8: Mapa de Calor y Visualizaciones

**User Story:** Como director de operaciones, quiero visualizar los riesgos en un mapa de calor interactivo, para tener una visión rápida de la postura de riesgo de cada servicio.

#### Criterios de Aceptación

1. THE Sistema_Riesgos SHALL generar un Mapa_Calor de 5×5 para cada Servicio, con el eje X representando Nivel_Impacto (1-5) y el eje Y representando Nivel_Probabilidad (1-5)
2. THE Sistema_Riesgos SHALL codificar las celdas del Mapa_Calor según la Zona_Riesgo correspondiente al producto de sus coordenadas: verde (Bajo, 1-4), amarillo (Medio, 5-9), naranja (Alto, 10-16) y rojo (Crítico, 17-25)
3. WHEN un usuario posiciona el cursor sobre una celda del Mapa_Calor, THE Sistema_Riesgos SHALL mostrar un tooltip con el código y título de cada Riesgo posicionado en esa celda, mostrando un máximo de 10 riesgos y un indicador del total restante si existen más de 10
4. THE Sistema_Riesgos SHALL generar un Mapa_Calor consolidado que agrupe únicamente los riesgos con estado activo de todos los Servicios, mostrando el conteo total de riesgos por celda
5. WHEN un usuario selecciona un Riesgo en el Mapa_Calor, THE Sistema_Riesgos SHALL navegar a la vista de detalle del Riesgo seleccionado
6. THE Sistema_Riesgos SHALL mostrar en cada celda del Mapa_Calor dos marcadores por cada Riesgo: uno con borde punteado para el riesgo inherente y otro con borde sólido para el Riesgo_Residual, posicionados según sus respectivos valores de Nivel_Probabilidad y Nivel_Impacto
7. WHEN un usuario accede al Mapa_Calor de un Servicio que no tiene riesgos activos registrados, THE Sistema_Riesgos SHALL mostrar la cuadrícula 5×5 vacía con un mensaje indicando que no existen riesgos registrados para ese Servicio
8. THE Sistema_Riesgos SHALL permitir alternar la visualización del Mapa_Calor entre mostrar solo riesgo inherente, solo Riesgo_Residual o ambos simultáneamente

### Requisito 9: Panel de Riesgos (Dashboard)

**User Story:** Como director de operaciones, quiero un panel centralizado de riesgos, para monitorear el estado general de todos los servicios de forma ejecutiva.

#### Criterios de Aceptación

1. THE Sistema_Riesgos SHALL presentar un Panel_Riesgos con los siguientes indicadores consolidados: total de riesgos activos (conteo numérico), distribución por Zona_Riesgo expresada en cantidad y porcentaje por cada zona (Bajo, Medio, Alto, Crítico), distribución por Categoría_Riesgo expresada en cantidad y porcentaje por cada categoría, y porcentaje de planes de tratamiento con estado "Implementado" respecto al total de planes de tratamiento existentes
2. THE Sistema_Riesgos SHALL mostrar en el Panel_Riesgos un listado de los riesgos con mayor Nivel_Riesgo residual ordenados de mayor a menor, mostrando un máximo de 10 riesgos o todos los riesgos activos si existen menos de 10
3. THE Sistema_Riesgos SHALL mostrar en el Panel_Riesgos un listado de hasta 20 riesgos con revisiones vencidas y hasta 20 acciones de planes de tratamiento con fecha límite vencida, ambos ordenados por antigüedad de vencimiento de mayor a menor
4. THE Sistema_Riesgos SHALL permitir filtrar el Panel_Riesgos por Servicio, Categoría_Riesgo y período de tiempo definido por fecha de inicio y fecha de fin
5. WHEN un usuario accede al Panel_Riesgos sin aplicar filtros, THE Sistema_Riesgos SHALL mostrar por defecto los datos consolidados de todos los Servicios correspondientes a los últimos 12 meses
6. WHEN un usuario accede al Panel_Riesgos, THE Sistema_Riesgos SHALL cargar los datos en un tiempo menor a 3 segundos para hasta 500 riesgos activos
7. IF los filtros aplicados no retornan resultados, THEN THE Sistema_Riesgos SHALL mostrar un mensaje indicando que no existen riesgos para los criterios seleccionados y mantener los filtros visibles para que el usuario pueda modificarlos

### Requisito 10: Exportación y Reportes

**User Story:** Como auditor interno, quiero exportar los datos de riesgos en formatos estándar, para generar reportes ejecutivos y documentar las revisiones realizadas.

#### Criterios de Aceptación

1. THE Sistema_Riesgos SHALL permitir exportar el registro de riesgos de un Servicio en formato Excel (.xlsx) incluyendo las columnas en este orden: código, título, Categoría_Riesgo, Nivel_Probabilidad, Nivel_Impacto, Nivel_Riesgo, Zona_Riesgo, Responsable_Riesgo, estado del Plan_Tratamiento (Pendiente, En Progreso, Implementado), estado del riesgo (activo/cerrado) y fecha de última revisión, con opción de filtrar por estado activo, cerrado o ambos antes de exportar
2. THE Sistema_Riesgos SHALL permitir exportar la Matriz_Riesgos de un Servicio en formato PDF incluyendo: el Mapa_Calor de 5×5, la tabla de riesgos con código, título, Zona_Riesgo y Responsable_Riesgo, y un resumen ejecutivo que contenga el total de riesgos por Zona_Riesgo, el porcentaje de planes de tratamiento completados, la cantidad de revisiones vencidas y la fecha de generación del reporte
3. THE Sistema_Riesgos SHALL permitir generar un reporte de tendencias en formato PDF que muestre la evolución del Nivel_Riesgo de todos los riesgos activos de un Servicio en un período seleccionado con un rango mínimo de 1 mes y máximo de 24 meses, con granularidad mensual en el eje temporal
4. THE Sistema_Riesgos SHALL integrar la funcionalidad de exportación Excel con la librería django-import-export para mantener consistencia con el resto de la aplicación
5. WHEN un usuario solicita una exportación con más de 100 riesgos, THE Sistema_Riesgos SHALL procesar la exportación de forma asíncrona mediante Celery, notificar al usuario cuando el archivo esté disponible y mantener el archivo disponible para descarga durante 72 horas desde su generación
6. IF la generación de un archivo de exportación falla por error de procesamiento o timeout después de 300 segundos, THEN THE Sistema_Riesgos SHALL notificar al usuario con un mensaje indicando que la exportación no pudo completarse y permitir reintentar la operación sin pérdida de los filtros seleccionados

### Requisito 11: Administración en Django Admin

**User Story:** Como administrador del sistema, quiero gestionar los riesgos desde el Django Admin con la misma experiencia SAP Fiori del resto de la aplicación, para mantener consistencia en la interfaz.

#### Criterios de Aceptación

1. THE Sistema_Riesgos SHALL registrar en el Django Admin los modelos Riesgo, Plan_Tratamiento, Control_Existente y Ciclo_Revisión utilizando clases basadas en ImportExportModelAdmin, con el mismo change_list_template, variables CSS SAP Fiori Horizon y enlace "Editar Fiori" empleados en KPIAdmin y AuditoriaAdmin
2. THE Sistema_Riesgos SHALL proporcionar acciones masivas en la vista de lista del modelo Riesgo para: reasignar Responsable_Riesgo a un usuario seleccionable del sistema, cambiar Ciclo_Revisión a una periodicidad seleccionable (Mensual, Bimestral, Trimestral, Semestral, Anual) y exportar la selección en formato Excel (.xlsx) mediante django-import-export
3. THE Sistema_Riesgos SHALL mostrar en el ServicioAdmin una sección inline de solo lectura (TabularInline) con el resumen de riesgos asociados mostrando: conteo de riesgos por cada Zona_Riesgo (Bajo, Medio, Alto, Crítico) y un enlace a la Matriz_Riesgos del Servicio
4. THE Sistema_Riesgos SHALL implementar los siguientes permisos Django asignables por grupo: `riesgos.view_riesgo` (visualizar riesgos), `riesgos.change_riesgo` (crear y editar riesgos), `riesgos.approve_plantratamiento` (aprobar planes de tratamiento) y `riesgos.configure_apetito` (configurar apetito y tolerancia)
5. WHEN un usuario sin el permiso `riesgos.approve_plantratamiento` intenta cambiar el estado de un Plan_Tratamiento a "Aprobado", THE Sistema_Riesgos SHALL rechazar la operación sin modificar el estado actual del Plan_Tratamiento y mostrar un mensaje indicando que no cuenta con permisos suficientes para aprobar planes de tratamiento
6. IF una acción masiva de reasignar Responsable_Riesgo se ejecuta sin seleccionar un usuario destino válido, THEN THE Sistema_Riesgos SHALL cancelar la operación sin modificar ningún registro y mostrar un mensaje indicando que se debe seleccionar un responsable válido
