# Requirements Document

## Introduction

Esta funcionalidad permite colocar marcadores (pines) sobre los planos PDF de un proyecto, vinculando cada pin a una observación existente del mismo proyecto. El objetivo es proveer una referencia visual directa entre las observaciones documentadas y su ubicación física en los planos técnicos del proyecto, de manera análoga al sistema de pines existente en el visor de planos de activos.

## Glossary

- **Visor_Plano_Proyecto**: Página web que renderiza un plano PDF de un proyecto con capacidades de zoom, pan y navegación de páginas.
- **Pin_Observacion**: Marcador visual posicionado sobre el plano PDF en coordenadas específicas, vinculado a una ObservacionProyecto.
- **PlanoProyecto**: Modelo que almacena archivos PDF de planos técnicos asociados a un proyecto.
- **ObservacionProyecto**: Registro de una observación o hallazgo asociado a un proyecto, con estado, fecha y descripción.
- **Capa_Pines**: Elemento HTML superpuesto al canvas del PDF que contiene los marcadores visuales posicionados por coordenadas absolutas.
- **Menu_Contextual**: Menú emergente activado por clic derecho sobre el plano que ofrece la opción de agregar un pin en la posición seleccionada.
- **Sistema**: El conjunto de backend (Django) y frontend (JavaScript) que implementa la funcionalidad de pines.

## Requirements

### Requisito 1: Modelo de datos para Pin de Observación en Proyecto

**Historia de Usuario:** Como desarrollador, quiero un modelo de datos que almacene la posición de un pin y su vínculo con una observación del proyecto, para persistir la información de pines de forma estructurada.

#### Criterios de Aceptación

1. THE Sistema SHALL almacenar cada Pin_Observacion con los campos: plano (FK a PlanoProyecto), observacion (FK a ObservacionProyecto), coordenada_x (float), coordenada_y (float), pagina (entero), color (texto con valor por defecto), nota opcional (texto), y fecha de creación automática.
2. WHEN un PlanoProyecto es eliminado, THE Sistema SHALL eliminar en cascada todos los Pin_Observacion asociados a ese plano.
3. WHEN una ObservacionProyecto es eliminada, THE Sistema SHALL eliminar en cascada todos los Pin_Observacion vinculados a esa observación.
4. THE Sistema SHALL aplicar una restricción de unicidad para la combinación de plano y observación, impidiendo vincular la misma observación más de una vez al mismo plano.

### Requisito 2: Visualización de pines existentes en el visor PDF

**Historia de Usuario:** Como usuario del sistema, quiero ver marcadores visuales sobre el plano PDF indicando las observaciones vinculadas, para identificar rápidamente dónde se localizan los hallazgos.

#### Criterios de Aceptación

1. WHEN el Visor_Plano_Proyecto carga un plano PDF, THE Sistema SHALL consultar todos los Pin_Observacion de la página actual y renderizarlos en la Capa_Pines.
2. THE Sistema SHALL representar cada Pin_Observacion como un marcador SVG con forma de gota posicionado en las coordenadas (x, y) almacenadas, usando el color del pin.
3. WHILE el usuario aplica zoom o pan al plano, THE Sistema SHALL mantener la posición relativa de los pines respecto al contenido del PDF.
4. WHEN el usuario cambia de página en un plano multipágina, THE Sistema SHALL mostrar únicamente los pines correspondientes a la página activa.
5. WHEN el usuario posiciona el cursor sobre un pin, THE Sistema SHALL mostrar un tooltip con el texto de la observación vinculada (primeros 80 caracteres).

### Requisito 3: Creación de un nuevo pin vinculado a una observación

**Historia de Usuario:** Como usuario del sistema, quiero hacer clic derecho sobre el plano y vincular una observación existente a esa ubicación, para documentar la localización exacta de un hallazgo.

#### Criterios de Aceptación

1. WHEN el usuario hace clic derecho sobre la Capa_Pines, THE Sistema SHALL mostrar un Menu_Contextual con la opción "Agregar Pin de Observación".
2. WHEN el usuario selecciona "Agregar Pin de Observación", THE Sistema SHALL abrir un modal que muestre un selector con las observaciones del mismo proyecto que aún no están vinculadas a ese plano.
3. THE Sistema SHALL permitir al usuario seleccionar un color para el pin desde una paleta predefinida.
4. THE Sistema SHALL permitir al usuario ingresar una nota opcional para el pin.
5. WHEN el usuario confirma la creación del pin, THE Sistema SHALL enviar las coordenadas (x, y), la página actual, el ID de la observación seleccionada, el color y la nota al backend vía solicitud AJAX POST.
6. WHEN el backend recibe la solicitud de creación, THE Sistema SHALL validar que la observación pertenece al mismo proyecto que el plano y crear el Pin_Observacion.
7. IF la observación seleccionada ya está vinculada al mismo plano, THEN THE Sistema SHALL retornar un error con mensaje descriptivo indicando la duplicidad.
8. WHEN el pin se guarda exitosamente, THE Sistema SHALL agregar el marcador visual al plano sin recargar la página.

### Requisito 4: Visualización del detalle de un pin

**Historia de Usuario:** Como usuario del sistema, quiero hacer clic en un pin para ver los detalles de la observación vinculada, para consultar la información completa del hallazgo.

#### Criterios de Aceptación

1. WHEN el usuario hace clic izquierdo sobre un Pin_Observacion, THE Sistema SHALL mostrar un panel o modal con los detalles de la observación vinculada.
2. THE Sistema SHALL mostrar en el detalle: el texto de la observación, el estado (Abierta, En Proceso, Resuelta, Cerrada), la fecha de observación, el usuario que la creó, y la nota del pin.
3. THE Sistema SHALL indicar visualmente el estado de la observación mediante un badge con color diferenciado (rojo para Abierta, amarillo para En Proceso, verde para Resuelta, gris para Cerrada).

### Requisito 5: Eliminación de un pin

**Historia de Usuario:** Como usuario del sistema, quiero poder eliminar un pin de un plano, para corregir errores de ubicación o remover marcadores obsoletos.

#### Criterios de Aceptación

1. WHEN el usuario visualiza el detalle de un pin, THE Sistema SHALL mostrar un botón "Eliminar Pin".
2. WHEN el usuario presiona "Eliminar Pin", THE Sistema SHALL solicitar confirmación antes de proceder.
3. WHEN el usuario confirma la eliminación, THE Sistema SHALL enviar una solicitud AJAX POST al backend para eliminar el Pin_Observacion.
4. WHEN la eliminación es exitosa, THE Sistema SHALL remover el marcador visual del plano sin recargar la página.
5. THE Sistema SHALL eliminar únicamente el vínculo pin-plano, preservando la ObservacionProyecto original intacta.

### Requisito 6: Endpoint API para gestión de pines

**Historia de Usuario:** Como desarrollador, quiero endpoints REST para crear, listar y eliminar pines de un plano de proyecto, para soportar la interacción frontend-backend.

#### Criterios de Aceptación

1. THE Sistema SHALL exponer un endpoint GET en la ruta `proyecto/<pk>/planos/<plano_id>/pines/` que retorne la lista de pines del plano en formato JSON con campos: id, x, y, pagina, color, nota, observacion_id, y un resumen de la observación (texto truncado, estado).
2. THE Sistema SHALL exponer un endpoint POST en la ruta `proyecto/<pk>/planos/<plano_id>/pines/crear/` que reciba x, y, pagina, observacion_id, color y nota, y cree un nuevo Pin_Observacion.
3. THE Sistema SHALL exponer un endpoint POST en la ruta `proyecto/<pk>/planos/<plano_id>/pines/<pin_id>/eliminar/` que elimine el pin especificado.
4. WHEN una solicitud a cualquier endpoint de pines es realizada por un usuario no autenticado, THE Sistema SHALL retornar un código HTTP 403.
5. WHEN el endpoint de creación recibe un observacion_id que no pertenece al mismo proyecto, THE Sistema SHALL retornar un código HTTP 400 con mensaje descriptivo.

### Requisito 7: Carga de pines en la vista del visor

**Historia de Usuario:** Como usuario del sistema, quiero que al abrir el visor de un plano se carguen automáticamente los pines existentes, para ver el estado actual de las observaciones ubicadas.

#### Criterios de Aceptación

1. WHEN el Visor_Plano_Proyecto renderiza la página, THE Sistema SHALL inyectar los pines existentes como datos JSON en el template para evitar una solicitud AJAX adicional en la carga inicial.
2. THE Sistema SHALL pasar al template un contexto con la lista de observaciones disponibles del proyecto (no vinculadas al plano) para popular el selector del modal de creación.
3. WHEN el visor completa la renderización del PDF, THE Sistema SHALL posicionar los pines de la página 1 en la Capa_Pines.
