# Documento de Requisitos

## Introducción

Esta funcionalidad rediseña el sistema de cotizaciones para soportar múltiples disciplinas dentro de una misma cotización. En lugar de que una cotización pertenezca a una única disciplina fija en el encabezado, la cotización ahora se organiza en **secciones por disciplina**: cada sección agrupa los ítems de esa disciplina y tiene su propio botón de carga de predefinidos. El encabezado de la cotización contiene únicamente datos generales (proyecto, fecha, versión, notas) sin campo de disciplina. Este cambio requiere una migración de base de datos para hacer `Cotizacion.disciplina` nullable, mientras que `ItemCotizacion.disciplina` (ya nullable) se convierte en el agrupador real de las secciones.

## Glosario

- **Sistema**: La aplicación Django de gestión de energía (módulo `presupuestos`).
- **Cotizacion**: Modelo Django que representa una cotización comercial. El campo `disciplina` a nivel de cabecera pasa a ser opcional (nullable).
- **ItemCotizacion**: Modelo Django que representa un ítem de línea dentro de una cotización. Su campo `disciplina` (ya nullable) identifica a qué sección pertenece el ítem.
- **ItemPredefinido**: Catálogo de ítems base; cada ítem pertenece obligatoriamente a una disciplina.
- **Disciplina**: Categoría de trabajo definida en el modelo `documentos.Disciplina` (p. ej. Electricidad, Mecánica, Civil).
- **Seccion_Disciplina**: Bloque visual dentro del formulario de cotización que muestra el nombre de una disciplina, la tabla de ítems de esa disciplina y los botones de acción propios de esa sección.
- **Encabezado_Cotizacion**: Bloque de datos generales de la cotización (Proyecto, Fecha, Versión, Notas). No contiene campo de Disciplina.
- **Formulario_Cotizacion**: Vista Django en `presupuestos` (template `form_cotizacion.html`) que maneja la creación y edición de cotizaciones.
- **API_Items**: Endpoint `api_items_por_disciplina` que devuelve ítems predefinidos filtrados por el ID de una disciplina.
- **Total_General**: Suma de todos los totales de todas las secciones de la cotización.

---

## Requisitos

### Requisito 1: Encabezado sin campo de disciplina

**User Story:** Como usuario administrativo, quiero que el encabezado de la cotización contenga solo datos generales del proyecto, para que la disciplina se gestione a nivel de cada sección de ítems.

#### Criterios de Aceptación

1. THE Formulario_Cotizacion SHALL mostrar en el bloque de encabezado únicamente los campos: Proyecto, Fecha, Versión, Válida hasta y Notas.
2. THE Formulario_Cotizacion SHALL NOT mostrar un selector de Disciplina en el bloque de encabezado de la cotización, ni en modo creación ni en modo edición.
3. WHEN el Sistema crea o actualiza una Cotizacion, THE Sistema SHALL permitir que el campo `Cotizacion.disciplina` sea nulo sin retornar error de validación.

---

### Requisito 2: Secciones dinámicas por disciplina

**User Story:** Como usuario administrativo, quiero ver los ítems agrupados en secciones por disciplina, para identificar claramente a qué área pertenece cada ítem de la cotización.

#### Criterios de Aceptación

1. THE Formulario_Cotizacion SHALL mostrar una Seccion_Disciplina separada por cada disciplina que tenga al menos un ítem en la cotización.
2. WHEN se muestra una Seccion_Disciplina, THE Formulario_Cotizacion SHALL mostrar el nombre de la disciplina como título de la sección, seguido de la tabla de ítems de esa sección.
3. WHEN la cotización no tiene ningún ítem, THE Formulario_Cotizacion SHALL mostrar el área de secciones vacía junto al botón "Agregar sección de disciplina".
4. THE Formulario_Cotizacion SHALL mostrar el Total_General al final de todas las secciones, calculado como la suma de los totales de cada ítem de todas las secciones.

---

### Requisito 3: Agregar sección de disciplina

**User Story:** Como usuario administrativo, quiero agregar nuevas secciones de disciplina a la cotización, para poder incluir ítems de múltiples áreas de trabajo en una sola cotización.

#### Criterios de Aceptación

1. THE Formulario_Cotizacion SHALL mostrar un botón global "Agregar sección de disciplina" visible debajo de todas las secciones existentes.
2. WHEN el usuario hace clic en "Agregar sección de disciplina", THE Formulario_Cotizacion SHALL mostrar un selector desplegable con todas las disciplinas disponibles en el Sistema.
3. WHEN el usuario selecciona una disciplina del selector, THE Formulario_Cotizacion SHALL añadir una nueva Seccion_Disciplina vacía con el nombre de la disciplina seleccionada.
4. IF el usuario intenta agregar una Seccion_Disciplina para una disciplina que ya existe en la cotización, THEN THE Formulario_Cotizacion SHALL informar al usuario que esa disciplina ya tiene una sección y SHALL NOT crear una sección duplicada.

---

### Requisito 4: Agregar ítems dentro de una sección

**User Story:** Como usuario administrativo, quiero agregar ítems manualmente dentro de una sección de disciplina, para ingresar trabajos específicos de esa área.

#### Criterios de Aceptación

1. WHEN se muestra una Seccion_Disciplina, THE Formulario_Cotizacion SHALL mostrar un botón "+ Agregar ítem" dentro de esa sección.
2. WHEN el usuario hace clic en "+ Agregar ítem" de una Seccion_Disciplina, THE Formulario_Cotizacion SHALL añadir una fila vacía al final de la tabla de ítems de esa sección con campos editables: Descripción, U.M., Cantidad, Precio Unitario y Descuento %.
3. WHEN un ítem es agregado a una Seccion_Disciplina, THE Sistema SHALL asociar ese ItemCotizacion con la disciplina de esa sección.
4. THE Formulario_Cotizacion SHALL NOT permitir mover un ítem de una Seccion_Disciplina a otra sección mediante la UI de tabla; cada ítem pertenece a la sección donde fue creado.

---

### Requisito 5: Cargar ítems predefinidos por sección

**User Story:** Como usuario administrativo, quiero cargar ítems predefinidos de una disciplina directamente en la sección correspondiente, para poblar rápidamente la cotización con ítems del catálogo.

#### Criterios de Aceptación

1. WHEN se muestra una Seccion_Disciplina, THE Formulario_Cotizacion SHALL mostrar un botón "Cargar predefinidos" dentro de esa sección.
2. WHEN el usuario hace clic en "Cargar predefinidos" de una Seccion_Disciplina, THE Sistema SHALL llamar a la API_Items usando el ID de la disciplina de esa sección como parámetro de filtro.
3. WHEN la API_Items retorna ítems para la disciplina, THE Formulario_Cotizacion SHALL agregar esos ítems al final de la tabla de la Seccion_Disciplina correspondiente, sin borrar los ítems ya existentes en esa sección.
4. IF la API_Items retorna una lista vacía para la disciplina de la sección, THEN THE Formulario_Cotizacion SHALL mostrar un mensaje informativo indicando que no hay ítems predefinidos para esa disciplina.
5. WHEN un ítem predefinido es cargado en una Seccion_Disciplina, THE Sistema SHALL asociar ese ItemCotizacion con la disciplina de esa sección.

---

### Requisito 6: Cálculo de totales por sección y total general

**User Story:** Como usuario administrativo, quiero ver el subtotal de cada sección y el total general de la cotización, para conocer el costo por disciplina y el costo total.

#### Criterios de Aceptación

1. WHEN el usuario modifica la cantidad, precio unitario o descuento de un ítem, THE Formulario_Cotizacion SHALL recalcular en tiempo real el total de ese ítem como `cantidad × precio_unitario × (1 − descuento% / 100)`.
2. WHEN el total de cualquier ítem cambia, THE Formulario_Cotizacion SHALL recalcular en tiempo real el subtotal de la Seccion_Disciplina que contiene ese ítem.
3. WHEN el subtotal de cualquier sección cambia, THE Formulario_Cotizacion SHALL recalcular en tiempo real el Total_General sumando los subtotales de todas las secciones.
4. THE Formulario_Cotizacion SHALL mostrar el subtotal al pie de cada Seccion_Disciplina.

---

### Requisito 7: Migración de modelo — Cotizacion.disciplina nullable

**User Story:** Como desarrollador, quiero que el campo `Cotizacion.disciplina` sea nullable en la base de datos, para que una cotización pueda existir sin estar limitada a una única disciplina.

#### Criterios de Aceptación

1. THE Sistema SHALL contar con una migración de Django que modifique el campo `Cotizacion.disciplina` para ser `null=True, blank=True`.
2. WHEN se aplica la migración, THE Sistema SHALL conservar los valores existentes de `Cotizacion.disciplina` en los registros ya guardados en la base de datos.
3. WHEN el Sistema crea una Cotizacion nueva mediante el Formulario_Cotizacion, THE Sistema SHALL crear el objeto con `Cotizacion.disciplina = None`.

---

### Requisito 8: Persistencia de ítems con su disciplina de sección

**User Story:** Como desarrollador, quiero que cada ItemCotizacion almacene la disciplina de la sección a la que pertenece, para que la agrupación por sección se preserve al recargar la cotización.

#### Criterios de Aceptación

1. WHEN el Sistema guarda un ItemCotizacion, THE Sistema SHALL almacenar en `ItemCotizacion.disciplina` el identificador de la Disciplina de la Seccion_Disciplina en la que fue creado el ítem.
2. WHEN el usuario abre el Formulario_Cotizacion en modo edición para una cotización existente, THE Formulario_Cotizacion SHALL reconstruir las Seccion_Disciplina agrupando los ItemCotizacion por su campo `ItemCotizacion.disciplina`.
3. IF un ItemCotizacion tiene `ItemCotizacion.disciplina = None`, THEN THE Formulario_Cotizacion SHALL agrupar ese ítem en una sección etiquetada como "Sin disciplina".

---

### Requisito 9: Eliminar sección de disciplina

**User Story:** Como usuario administrativo, quiero poder eliminar una sección de disciplina completa, para quitar todas las líneas de esa área si ya no aplican a la cotización.

#### Criterios de Aceptación

1. WHEN se muestra una Seccion_Disciplina, THE Formulario_Cotizacion SHALL mostrar un botón o control para eliminar esa sección completa.
2. WHEN el usuario hace clic en el control de eliminar de una Seccion_Disciplina, THE Formulario_Cotizacion SHALL solicitar confirmación antes de eliminar.
3. WHEN el usuario confirma la eliminación de una Seccion_Disciplina, THE Formulario_Cotizacion SHALL eliminar la sección y todos sus ítems de la interfaz.
4. WHEN el Sistema guarda la cotización después de que el usuario eliminó una Seccion_Disciplina, THE Sistema SHALL eliminar de la base de datos todos los ItemCotizacion que pertenecían a esa sección.

---

### Requisito 10: Creación y edición unificadas con secciones múltiples

**User Story:** Como usuario administrativo, quiero que el flujo de creación y edición de cotizaciones soporte múltiples secciones de disciplina desde el primer guardado, para mantener la consistencia de la interfaz.

#### Criterios de Aceptación

1. WHEN el usuario completa el Encabezado_Cotizacion y hace clic en "Crear Cotización", THE Sistema SHALL crear el objeto Cotizacion con los datos del encabezado y SHALL crear cada ItemCotizacion con su `ItemCotizacion.disciplina` correspondiente a su sección.
2. WHEN el usuario edita una cotización existente y guarda los ítems, THE Sistema SHALL reemplazar todos los ItemCotizacion de la cotización con los ítems actualmente visibles en el formulario, preservando la asignación de disciplina por sección.
3. WHEN el formulario tiene al menos una Seccion_Disciplina con al menos un ítem, THE Formulario_Cotizacion SHALL habilitar el botón "Crear Cotización" / "Guardar Items".
4. IF el usuario intenta guardar la cotización sin ningún ítem en ninguna sección, THEN THE Formulario_Cotizacion SHALL permitir el guardado igualmente, creando una cotización sin ítems.
