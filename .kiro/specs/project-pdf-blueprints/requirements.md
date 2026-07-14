# Requirements Document

## Introduction

Esta funcionalidad agrega una nueva pestaña "Planos PDF" en la vista de detalle del proyecto (`/proyectos/proyecto/<id>/`). La pestaña permite a los usuarios cargar, visualizar y gestionar planos en formato PDF asociados a un proyecto, reutilizando el visor de PDF existente en el módulo de activos como referencia de implementación.

## Glossary

- **Sistema_Proyecto**: Módulo de proyectos de la aplicación Energy (Django app `proyectos`)
- **Vista_Detalle**: Página de detalle estilo SAP Fiori del proyecto, accesible en `/proyectos/proyecto/<pk>/`
- **Pestaña_Planos**: Nueva pestaña dentro de la Vista_Detalle que muestra los planos PDF asociados al proyecto
- **Plano_Proyecto**: Registro que vincula un archivo PDF (plano) con un proyecto específico
- **Visor_PDF**: Componente de visualización de PDF basado en PDF.js, usado actualmente en `/activos/visor-pdf/<id>/`
- **MinIO_Storage**: Sistema de almacenamiento de archivos S3-compatible usado por la aplicación
- **Usuario_Staff**: Usuario autenticado con permisos de staff (`is_staff=True`)

## Requirements

### Requisito 1: Pestaña de Planos PDF en la Vista de Detalle

**Historia de Usuario:** Como usuario de gestión de proyectos, quiero ver una pestaña dedicada a planos PDF en la vista de detalle del proyecto, para poder acceder rápidamente a los planos técnicos asociados.

#### Criterios de Aceptación

1. THE Vista_Detalle SHALL mostrar una pestaña denominada "Planos PDF" en la barra de navegación de pestañas del proyecto
2. WHEN el usuario hace clic en la pestaña "Planos PDF", THE Sistema_Proyecto SHALL mostrar la sección de planos ocultando las demás secciones y resaltar visualmente la pestaña activa
3. THE Pestaña_Planos SHALL ubicarse después de la pestaña "Documentos vinculados" y antes de la pestaña "Órdenes de Trabajo" en el orden de pestañas
4. IF no existen planos asociados al proyecto, THEN THE Pestaña_Planos SHALL mostrar un estado vacío con un mensaje descriptivo y un botón para subir el primer plano

### Requisito 2: Carga de Planos PDF

**Historia de Usuario:** Como usuario de gestión de proyectos, quiero poder subir archivos PDF de planos directamente desde la pestaña de planos, para asociar documentación técnica al proyecto.

#### Criterios de Aceptación

1. THE Pestaña_Planos SHALL mostrar un área de carga (dropzone) donde el usuario pueda arrastrar archivos o seleccionar mediante un botón
2. WHEN el usuario sube un archivo PDF de tamaño menor o igual a 50 MB, THE Sistema_Proyecto SHALL almacenar el archivo en MinIO_Storage y crear un registro Plano_Proyecto vinculado al proyecto
3. IF el usuario intenta subir un archivo cuyo Content-Type no es application/pdf o cuya extensión no es .pdf, THEN THE Sistema_Proyecto SHALL rechazar la carga y mostrar un mensaje indicando que solo se aceptan archivos PDF
4. IF el usuario intenta subir un archivo que excede 50 MB, THEN THE Sistema_Proyecto SHALL rechazar la carga y mostrar un mensaje indicando el tamaño máximo permitido
5. WHEN la carga se completa exitosamente, THE Sistema_Proyecto SHALL actualizar la lista de planos sin recargar la página completa
6. THE Sistema_Proyecto SHALL requerir que el usuario ingrese un título de entre 1 y 150 caracteres, y opcionalmente una descripción de hasta 500 caracteres, al momento de cargar cada plano
7. IF el almacenamiento en MinIO_Storage falla durante la carga, THEN THE Sistema_Proyecto SHALL mostrar un mensaje de error indicando que la carga no pudo completarse y no crear el registro Plano_Proyecto

### Requisito 3: Listado de Planos PDF

**Historia de Usuario:** Como usuario de gestión de proyectos, quiero ver un listado de todos los planos PDF asociados al proyecto, para poder identificar y acceder a cada uno.

#### Criterios de Aceptación

1. THE Pestaña_Planos SHALL mostrar una tabla con los planos vinculados al proyecto, incluyendo las columnas: título del plano, fecha de carga (formato dd/mm/aaaa), nombre del usuario que lo cargó, y acciones (botón para visualizar el PDF y botón para descargar el archivo)
2. IF no existen planos asociados al proyecto, THEN THE Pestaña_Planos SHALL mostrar un mensaje indicando que aún no se han agregado planos y un botón para subir el primero
3. THE Sistema_Proyecto SHALL ordenar los planos por fecha de carga en orden descendente (más recientes primero) y mostrar un máximo de 20 planos por página con controles de paginación cuando el total exceda ese límite
4. IF el usuario selecciona la acción de visualizar un plano cuyo archivo PDF no se encuentra disponible en el servidor, THEN THE Pestaña_Planos SHALL mostrar un mensaje de error indicando que el archivo no pudo ser recuperado, sin redirigir al usuario fuera de la pestaña

### Requisito 4: Visualización de Planos PDF

**Historia de Usuario:** Como usuario de gestión de proyectos, quiero poder visualizar los planos PDF directamente desde la pestaña, para revisar los documentos técnicos sin descargarlos.

#### Criterios de Aceptación

1. WHEN el usuario hace clic en el botón "Ver" de un plano, THE Sistema_Proyecto SHALL abrir el visor de PDF en una nueva pestaña del navegador utilizando la ruta `/proyectos/proyecto/<pk>/planos/<plano_id>/visor/`
2. THE Visor_PDF SHALL renderizar el plano completo e incluir los siguientes controles: zoom in/out (rango 25% a 400%), indicador de página actual y total, botones de navegación anterior/siguiente página, y panel lateral de miniaturas de páginas
3. WHEN el usuario hace clic en el botón "Descargar" de un plano, THE Sistema_Proyecto SHALL iniciar la descarga del archivo PDF con cabecera Content-Disposition de tipo attachment y nombre de archivo igual al título del plano con extensión .pdf
4. IF el archivo PDF del plano no existe en MinIO_Storage o no es accesible, THEN THE Sistema_Proyecto SHALL mostrar un mensaje de error indicando que el archivo no se encuentra disponible, tanto en el visor como en el intento de descarga
5. THE Visor_PDF SHALL soportar la renderización de archivos PDF de hasta 50 MB de tamaño sin bloquear la interacción del usuario durante la carga, mostrando un indicador de progreso mientras se procesa el documento

### Requisito 5: Eliminación de Planos PDF

**Historia de Usuario:** Como usuario de gestión de proyectos, quiero poder eliminar planos que ya no son relevantes para el proyecto, para mantener la documentación actualizada.

#### Criterios de Aceptación

1. WHEN el usuario hace clic en el botón "Eliminar" de un plano, THE Sistema_Proyecto SHALL mostrar un diálogo de confirmación que incluya el título del plano a eliminar y solicite confirmación explícita antes de proceder
2. IF el usuario cancela el diálogo de confirmación, THEN THE Sistema_Proyecto SHALL cerrar el diálogo sin realizar cambios en el registro Plano_Proyecto ni en la lista de planos
3. WHEN el usuario confirma la eliminación, THE Sistema_Proyecto SHALL eliminar el registro Plano_Proyecto, eliminar el archivo asociado en MinIO_Storage y actualizar la lista de planos sin recargar la página
4. IF ocurre un error durante la eliminación, THEN THE Sistema_Proyecto SHALL mostrar un mensaje de error indicando que la operación no se completó y mantener el plano visible en la lista sin modificaciones

### Requisito 6: Modelo de Datos para Planos de Proyecto

**Historia de Usuario:** Como desarrollador, quiero un modelo de datos dedicado para los planos de proyecto, para mantener la separación de responsabilidades con el módulo de activos.

#### Criterios de Aceptación

1. THE Sistema_Proyecto SHALL almacenar cada Plano_Proyecto con los siguientes campos: proyecto (FK), título (CharField, máximo 200 caracteres), descripción (TextField, opcional), archivo PDF (FileField, máximo 50 MB), usuario que lo cargó (FK a User) y fecha de carga (DateTimeField auto_now_add)
2. THE Sistema_Proyecto SHALL almacenar los archivos PDF usando MinIO_Storage en la ruta `proyectos/planos/`
3. WHEN se elimina un proyecto, THE Sistema_Proyecto SHALL eliminar en cascada todos los registros Plano_Proyecto asociados junto con sus archivos almacenados en MinIO_Storage
4. WHEN un usuario carga un archivo en Plano_Proyecto, THE Sistema_Proyecto SHALL validar que el archivo tenga extensión `.pdf` y un content-type `application/pdf` antes de aceptar la carga
5. IF la validación del archivo falla por extensión no permitida o content-type no coincidente, THEN THE Sistema_Proyecto SHALL rechazar la carga y retornar un mensaje de error indicando que solo se aceptan archivos PDF

### Requisito 7: API de Gestión de Planos

**Historia de Usuario:** Como desarrollador del frontend, quiero endpoints API para gestionar planos, para que la interfaz pueda operar de manera asíncrona.

#### Criterios de Aceptación

1. THE Sistema_Proyecto SHALL exponer un endpoint POST en `/proyectos/proyecto/<pk>/planos/upload/` que acepte multipart/form-data con los campos: archivo (requerido), titulo (requerido) y descripcion (opcional) para subir planos PDF
2. THE Sistema_Proyecto SHALL exponer un endpoint GET en `/proyectos/proyecto/<pk>/planos/` que retorne la lista de planos del proyecto en formato JSON, incluyendo por cada plano: id, titulo, descripcion, fecha_carga, usuario_nombre y url_archivo
3. THE Sistema_Proyecto SHALL exponer un endpoint DELETE en `/proyectos/proyecto/<pk>/planos/<plano_id>/delete/` para eliminar un plano específico
4. WHEN un usuario no autenticado intenta acceder a los endpoints, THE Sistema_Proyecto SHALL responder con código HTTP 403
5. THE Sistema_Proyecto SHALL responder con formato JSON consistente incluyendo campos `status`, `message` y opcionalmente `data` en todas las respuestas de los endpoints
6. WHEN el endpoint GET recibe el parámetro `page`, THE Sistema_Proyecto SHALL retornar los resultados paginados con 20 elementos por página e incluir en la respuesta los campos `total`, `page` y `total_pages`
