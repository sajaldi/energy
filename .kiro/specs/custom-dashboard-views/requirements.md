# Requirements Document

## Introduction

Esta funcionalidad permite a los usuarios del dashboard de requisiciones (`/presupuestos/requisiciones/dashboard/`) personalizar la tabla de datos mediante la selección de columnas visibles, el ordenamiento ascendente/descendente por cualquier columna, y la capacidad de guardar estas configuraciones como "vistas personalizadas" para reutilizarlas en el futuro.

## Glossary

- **Dashboard_Requisiciones**: Vista principal en `/presupuestos/requisiciones/dashboard/` que muestra la tabla de requisiciones con métricas y acciones.
- **Vista_Personalizada**: Configuración guardada por un usuario que incluye las columnas seleccionadas, el orden de clasificación y la dirección del mismo.
- **Selector_Columnas**: Componente de interfaz que permite al usuario agregar o quitar columnas de la tabla.
- **Indicador_Orden**: Elemento visual en el encabezado de cada columna que muestra la dirección del ordenamiento actual (ascendente o descendente).
- **Columnas_Disponibles**: Conjunto completo de columnas que el usuario puede elegir mostrar: N° Requisición, Fecha, Asunto, Prioridad, Estado, Total, O/C, Tipo, Solicitante, Aprobador, Motivo, Partida Presupuestaria, Proveedor, Acciones.
- **Columnas_Default**: Conjunto predeterminado de columnas visibles al cargar el dashboard sin una vista guardada: N° Requisición, Fecha, Asunto, Prioridad, Estado, Total, O/C, Acciones.
- **Usuario**: Persona autenticada que accede al Dashboard_Requisiciones.

## Requirements

### Requirement 1: Selección de columnas visibles

**User Story:** Como usuario del Dashboard_Requisiciones, quiero agregar o quitar columnas de la tabla de requisiciones, para que pueda enfocarme en la información relevante a mis necesidades.

#### Acceptance Criteria

1. THE Dashboard_Requisiciones SHALL mostrar un botón de Selector_Columnas en el encabezado de la tabla.
2. WHEN el Usuario hace clic en el botón del Selector_Columnas, THE Dashboard_Requisiciones SHALL mostrar un panel con las 14 Columnas_Disponibles (N° Requisición, Fecha, Asunto, Prioridad, Estado, Total, O/C, Tipo, Solicitante, Aprobador, Motivo, Partida Presupuestaria, Proveedor, Acciones) listadas con casillas de verificación, donde las columnas actualmente visibles aparecen marcadas y la columna Acciones aparece marcada y deshabilitada.
3. WHEN el Usuario activa una columna en el Selector_Columnas, THE Dashboard_Requisiciones SHALL agregar la columna a la tabla en su posición predefinida dentro del orden fijo de Columnas_Disponibles, sin recargar la página.
4. WHEN el Usuario desactiva una columna en el Selector_Columnas, THE Dashboard_Requisiciones SHALL remover la columna de la tabla sin recargar la página, preservando los datos de las filas existentes.
5. THE Dashboard_Requisiciones SHALL mantener la columna "Acciones" siempre visible, con su casilla de verificación deshabilitada en el Selector_Columnas para impedir su desactivación.
6. WHILE ninguna Vista_Personalizada está activa, THE Dashboard_Requisiciones SHALL mostrar las Columnas_Default: N° Requisición, Fecha, Asunto, Prioridad, Estado, Total, O/C y Acciones.
7. IF el Usuario intenta desactivar todas las columnas de datos dejando solo Acciones activa, THEN THE Dashboard_Requisiciones SHALL impedir la desactivación de la última columna de datos visible y mostrar un mensaje indicando que al menos una columna de datos debe permanecer activa además de Acciones.
8. WHEN el Usuario hace clic fuera del panel del Selector_Columnas o presiona la tecla Escape, THE Dashboard_Requisiciones SHALL cerrar el panel del Selector_Columnas.
9. WHEN el Usuario modifica la selección de columnas, THE Dashboard_Requisiciones SHALL persistir la configuración en el navegador del Usuario de modo que al recargar la página o volver al dashboard se conserven las columnas seleccionadas.

### Requirement 2: Ordenamiento de columnas

**User Story:** Como usuario del Dashboard_Requisiciones, quiero ordenar las requisiciones de forma ascendente o descendente por cualquier columna, para que pueda localizar información rápidamente según mis criterios.

#### Acceptance Criteria

1. WHEN el Usuario hace clic en el encabezado de una columna ordenable, THE Dashboard_Requisiciones SHALL ordenar la tabla por esa columna en dirección ascendente aplicando las siguientes reglas según tipo de dato: N° Requisición por orden alfanumérico (A-Z), Fecha por orden cronológico (más antigua primero), Asunto por orden alfabético (A-Z), Prioridad por orden de severidad (Normal antes de Urgencia), Estado por orden alfabético (A-Z), y Total por orden numérico (menor a mayor).
2. WHEN el Usuario hace clic nuevamente en el mismo encabezado de columna, THE Dashboard_Requisiciones SHALL invertir la dirección del ordenamiento a descendente.
3. WHEN el Usuario hace clic por tercera vez consecutiva en el mismo encabezado, THE Dashboard_Requisiciones SHALL restablecer el orden predeterminado (columna Fecha en dirección descendente, mostrando las más recientes primero).
4. WHILE una columna tiene ordenamiento activo, THE Dashboard_Requisiciones SHALL mostrar un Indicador_Orden en el encabezado de dicha columna que indique visualmente la dirección actual del ordenamiento (un símbolo para ascendente y un símbolo distinto para descendente).
5. THE Dashboard_Requisiciones SHALL permitir ordenamiento en las siguientes columnas: N° Requisición, Fecha, Asunto, Prioridad, Estado, Total.
6. THE Dashboard_Requisiciones SHALL excluir del ordenamiento las columnas O/C y Acciones, sin mostrar indicador de clic ni cursor interactivo en sus encabezados.
7. WHEN el Usuario hace clic en el encabezado de una columna ordenable, THE Dashboard_Requisiciones SHALL completar el reordenamiento de las filas visibles en un máximo de 1 segundo.
8. WHEN el Usuario aplica un ordenamiento y existen filas con valores iguales en la columna seleccionada, THE Dashboard_Requisiciones SHALL mantener entre esas filas el orden secundario por Fecha descendente.

### Requirement 3: Guardar vistas personalizadas

**User Story:** Como usuario del Dashboard_Requisiciones, quiero guardar mis configuraciones de columnas y ordenamiento como vistas con nombre, para que pueda reutilizar mis preferencias sin reconfigurar cada vez.

#### Acceptance Criteria

1. IF el Usuario ha cambiado al menos una columna visible o el criterio de ordenamiento respecto a la configuración por defecto del Dashboard_Requisiciones, THEN THE Dashboard_Requisiciones SHALL mostrar el botón "Guardar Vista" habilitado.
2. WHEN el Usuario hace clic en "Guardar Vista", THE Dashboard_Requisiciones SHALL mostrar un campo de texto para ingresar el nombre de la Vista_Personalizada, con una longitud máxima de 100 caracteres.
3. WHEN el Usuario confirma el guardado con un nombre válido, THE Dashboard_Requisiciones SHALL almacenar la Vista_Personalizada asociada al Usuario con las columnas seleccionadas y el criterio de ordenamiento actual, y mostrar una notificación de éxito dentro de los 2 segundos siguientes.
4. THE Dashboard_Requisiciones SHALL mostrar un selector de vistas guardadas que liste todas las Vista_Personalizada del Usuario ordenadas alfabéticamente por nombre.
5. WHEN el Usuario selecciona una Vista_Personalizada del selector, THE Dashboard_Requisiciones SHALL aplicar las columnas y ordenamiento de esa vista a la tabla dentro de los 2 segundos siguientes.
6. WHEN el Usuario hace clic en "Eliminar" en una Vista_Personalizada, THE Dashboard_Requisiciones SHALL solicitar confirmación al Usuario mediante un diálogo y eliminar esa vista únicamente si el Usuario confirma la acción.
7. THE Dashboard_Requisiciones SHALL permitir al Usuario guardar un máximo de 10 vistas personalizadas por Usuario.
8. IF el Usuario intenta guardar una Vista_Personalizada con un nombre vacío o que contenga solo espacios en blanco, THEN THE Dashboard_Requisiciones SHALL mostrar un mensaje de validación indicando que el nombre es obligatorio y no proceder con el guardado.
9. IF el Usuario intenta guardar más de 10 vistas, THEN THE Dashboard_Requisiciones SHALL mostrar un mensaje indicando que debe eliminar una vista existente antes de crear una nueva, y no proceder con el guardado.
10. IF el Usuario intenta guardar una Vista_Personalizada con un nombre que ya existe para ese Usuario en el mismo Dashboard, THEN THE Dashboard_Requisiciones SHALL mostrar un mensaje indicando que el nombre ya está en uso y solicitar un nombre diferente.
11. IF el guardado o eliminación de una Vista_Personalizada falla por un error del servidor, THEN THE Dashboard_Requisiciones SHALL mostrar un mensaje de error indicando que la operación no se completó y preservar el estado previo de la tabla sin cambios.

### Requirement 4: Persistencia y carga de preferencias

**User Story:** Como usuario del Dashboard_Requisiciones, quiero que mi última vista utilizada se mantenga al volver al dashboard, para que no tenga que reconfigurar la tabla cada sesión.

#### Acceptance Criteria

1. WHEN el Usuario aplica una Vista_Personalizada guardada (con nombre), THE Dashboard_Requisiciones SHALL registrar esa vista como la última utilizada por el Usuario, asociándola a su cuenta de Usuario autenticado.
2. WHEN el Usuario accede al Dashboard_Requisiciones y existe un registro de última Vista_Personalizada utilizada, THE Dashboard_Requisiciones SHALL cargar automáticamente esa Vista_Personalizada aplicando sus columnas y orden configurados.
3. IF el Usuario accede al Dashboard_Requisiciones y no existe un registro de última vista utilizada (primer acceso o vista restablecida), THEN THE Dashboard_Requisiciones SHALL cargar las Columnas_Default (N° Requisición, Fecha, Asunto, Prioridad, Estado, Total, O/C, Acciones) con orden predeterminado por Fecha descendente.
4. IF la última Vista_Personalizada utilizada fue eliminada, THEN THE Dashboard_Requisiciones SHALL cargar las Columnas_Default con el orden predeterminado por Fecha descendente.
5. THE Dashboard_Requisiciones SHALL almacenar las vistas personalizadas en la base de datos asociadas al Usuario autenticado. Solo las vistas guardadas con nombre se persisten como última vista utilizada; los cambios ad-hoc de columnas sin guardar no actualizan el registro de última vista.
6. WHEN el Usuario presiona el botón "Restablecer Vista", THE Dashboard_Requisiciones SHALL aplicar las Columnas_Default con orden predeterminado por Fecha descendente y eliminar el registro de última vista utilizada del Usuario.

### Requirement 5: Aplicación a ambas pestañas del dashboard

**User Story:** Como usuario del Dashboard_Requisiciones, quiero que la configuración de columnas y ordenamiento se aplique tanto a la pestaña "Resumen General" como a "Mis Requisiciones", para tener una experiencia consistente.

#### Acceptance Criteria

1. WHEN el Usuario aplica una Vista_Personalizada, THE Dashboard_Requisiciones SHALL aplicar la configuración de columnas visibles de esa vista simultáneamente a la tabla de la pestaña "Resumen General" y a la tabla de la pestaña "Mis Requisiciones".
2. WHEN el Usuario aplica una Vista_Personalizada, THE Dashboard_Requisiciones SHALL aplicar el criterio de ordenamiento de esa vista como orden inicial en ambas pestañas.
3. WHEN el Usuario cambia el ordenamiento manualmente en la pestaña activa, THE Dashboard_Requisiciones SHALL aplicar el nuevo orden únicamente a la tabla de la pestaña activa, manteniendo el orden previo en la otra pestaña hasta que el Usuario la seleccione.
4. WHEN el Usuario cambia de pestaña, THE Dashboard_Requisiciones SHALL conservar las columnas visibles definidas por la Vista_Personalizada activa o por la selección manual del Selector_Columnas.
5. WHEN el Usuario modifica las columnas visibles mediante el Selector_Columnas sin una Vista_Personalizada activa, THE Dashboard_Requisiciones SHALL aplicar la misma selección de columnas a ambas pestañas.
