# Requirements Document

## Introduction

Este documento define los requisitos para agregar áreas rectangulares al visor de planos PDF de proyecto. Las áreas permiten demarcar zonas con nombre y color sobre el plano, y los pines de observación se asocian dinámicamente a un área según su posición geométrica. Las áreas se definen por página y se crean mediante el menú contextual existente del visor.

## Glossary

- **Visor**: El componente de visualización de planos PDF del proyecto (`visor_plano_proyecto`), que incluye zoom, pan, capa de pines, y menú contextual.
- **Area**: Región rectangular definida sobre una página del plano, con nombre editable y color personalizable. Se almacena con coordenadas absolutas del viewport base.
- **Pin**: Instancia de `PinObservacionProyecto` con coordenadas (x, y) y página, que marca una observación sobre el plano.
- **Viewport_Base**: El sistema de coordenadas en píxeles absolutos del canvas PDF sin escalar, independiente del zoom/pan actual.
- **Contención_Dinámica**: Relación computada en tiempo de ejecución entre un Pin y un Area basada en si las coordenadas del Pin caen dentro del rectángulo del Area en la misma página.
- **Sistema**: El módulo de áreas del visor de planos de proyecto (backend Django + frontend JavaScript vanilla).

## Requirements

### Requirement 1: Creación de Área

**User Story:** Como usuario staff, quiero crear un área rectangular sobre el plano haciendo clic derecho y arrastrando, para demarcar zonas de interés en el plano del proyecto.

#### Acceptance Criteria

1. WHEN the user right-clicks on the pin layer and selects "Agregar Área" from the context menu, THE Sistema SHALL enter area creation mode, changing the cursor to crosshair.
2. WHEN the user clicks and drags on the canvas while in area creation mode, THE Sistema SHALL display a live preview rectangle from the click point to the current cursor position with a dashed border.
3. WHEN the user releases the mouse button after dragging in area creation mode, THE Sistema SHALL display a creation form requesting the area name and color.
4. WHEN the user submits the creation form with a valid name and color, THE Sistema SHALL send a POST request to the area creation endpoint with coordinates (x1, y1, x2, y2), page number, name, and color.
5. WHEN the backend receives a valid area creation request, THE Sistema SHALL persist the area with normalized coordinates (x1 <= x2, y1 <= y2) in Viewport_Base units and return the created area data.
6. WHEN the user presses Escape while in area creation mode, THE Sistema SHALL cancel the creation and return to normal mode without creating an area.
7. IF the user drags a rectangle with width or height less than 10 pixels in Viewport_Base units, THEN THE Sistema SHALL reject the creation and display a message indicating the area is too small.

### Requirement 2: Visualización de Áreas

**User Story:** Como usuario staff, quiero ver las áreas definidas sobre el plano con relleno semi-transparente y borde, para identificar visualmente las zonas demarcadas.

#### Acceptance Criteria

1. WHEN a page is rendered in the Visor, THE Sistema SHALL display all areas belonging to that page as rectangles with semi-transparent fill and solid border using the area color.
2. THE Sistema SHALL render each Area with fill opacity of 0.15 and border opacity of 0.7.
3. WHILE the Visor zoom or pan state changes, THE Sistema SHALL reposition and resize all visible areas maintaining their correct relative position on the PDF content using the transformation: screenX = x * scale + translateX, screenY = y * scale + translateY.
4. WHEN the user hovers over an Area, THE Sistema SHALL display a tooltip showing the area name.
5. WHEN a page change occurs, THE Sistema SHALL display only the areas belonging to the current page.

### Requirement 3: Edición de Área

**User Story:** Como usuario staff, quiero editar el nombre y color de un área existente, para mantener actualizada la información de las zonas demarcadas.

#### Acceptance Criteria

1. WHEN the user double-clicks on an Area, THE Sistema SHALL display an edit form pre-populated with the current name and color of the area.
2. WHEN the user submits the edit form with a modified name or color, THE Sistema SHALL send a POST request to the area update endpoint with the new values.
3. WHEN the backend receives a valid area update request, THE Sistema SHALL persist the updated name and color and return the updated area data.
4. IF the user submits an empty name in the edit form, THEN THE Sistema SHALL reject the submission and display a validation message indicating the name is required.
5. WHEN the area is successfully updated, THE Sistema SHALL immediately reflect the new color and name in the Visor without requiring a page reload.

### Requirement 4: Eliminación de Área

**User Story:** Como usuario staff, quiero eliminar un área que ya no es necesaria, para mantener el plano organizado.

#### Acceptance Criteria

1. WHEN the user right-clicks on an Area, THE Sistema SHALL display a context menu with the option "Eliminar Área".
2. WHEN the user selects "Eliminar Área" from the context menu, THE Sistema SHALL display a confirmation dialog with the area name.
3. WHEN the user confirms the deletion, THE Sistema SHALL send a POST request to the area deletion endpoint.
4. WHEN the backend receives a valid deletion request, THE Sistema SHALL remove the area from the database and return a success response.
5. WHEN the area is successfully deleted, THE Sistema SHALL remove the area rectangle from the Visor immediately without a page reload.
6. WHEN an Area is deleted, THE Sistema SHALL preserve all Pin records unchanged, as the relationship is computed dynamically.

### Requirement 5: Contención Dinámica Pin-Área

**User Story:** Como usuario staff, quiero saber qué pines están dentro de cada área sin configuración manual, para agrupar observaciones por zona automáticamente.

#### Acceptance Criteria

1. THE Sistema SHALL compute pin-area membership dynamically: a Pin belongs to an Area when the pin coordinates (x, y) fall within the area rectangle (x1 <= pin.x <= x2 AND y1 <= pin.y <= y2) and both are on the same page.
2. WHEN a Pin is moved to a new position, THE Sistema SHALL recompute its area membership based on the new coordinates without storing any foreign key relationship.
3. WHEN a user requests the list of pins within an area, THE Sistema SHALL return all pins whose coordinates satisfy the containment condition for that area on the same page.
4. THE Sistema SHALL allow a Pin to belong to multiple overlapping areas simultaneously when its coordinates fall within more than one area rectangle.
5. WHEN a user hovers over or selects an Area, THE Sistema SHALL visually highlight the pins contained within that area.

### Requirement 6: Panel Lateral de Áreas

**User Story:** Como usuario staff, quiero ver un listado de las áreas del plano con la cantidad de pines contenidos, para tener una visión general de las zonas y sus observaciones.

#### Acceptance Criteria

1. THE Sistema SHALL display an areas panel in the sidebar listing all areas for the current page with their name, color indicator, and pin count.
2. WHEN the user clicks on an area in the panel, THE Sistema SHALL center the Visor on that area and highlight it visually.
3. WHEN an area is created, updated, or deleted, THE Sistema SHALL update the areas panel immediately to reflect the change.
4. THE Sistema SHALL display the pin count for each area computed dynamically based on current pin positions.
5. WHEN the user navigates to a different page, THE Sistema SHALL update the areas panel to show only areas belonging to the new current page.

### Requirement 7: Persistencia y API

**User Story:** Como usuario staff, quiero que las áreas se guarden en el servidor y se carguen automáticamente al abrir el visor, para que persistan entre sesiones.

#### Acceptance Criteria

1. THE Sistema SHALL store each area with the fields: plano (FK), name (CharField), color (ColorField), x1, y1, x2, y2 (FloatField), page number (PositiveIntegerField), and creation timestamp.
2. WHEN the Visor loads, THE Sistema SHALL inject all areas for the plano as JSON data in the template context to avoid an additional AJAX request on load.
3. WHEN the area creation endpoint receives a request, THE Sistema SHALL validate that the plano belongs to the same project referenced in the URL.
4. WHEN the area update endpoint receives a request, THE Sistema SHALL validate that the area belongs to the plano referenced in the URL.
5. WHEN the area deletion endpoint receives a request, THE Sistema SHALL validate that the area belongs to the plano referenced in the URL.
6. THE Sistema SHALL expose three API endpoints: POST crear (create), POST editar (update), and POST eliminar (delete), following the existing JsonResponse pattern with {status: "success"/"error"}.

### Requirement 8: Seguridad y Autorización

**User Story:** Como administrador, quiero que solo usuarios staff autenticados puedan gestionar áreas, para mantener el control de acceso del sistema.

#### Acceptance Criteria

1. THE Sistema SHALL protect all area API endpoints with the @staff_member_required decorator.
2. IF an unauthenticated user requests any area endpoint, THEN THE Sistema SHALL respond with HTTP 302 redirect to the login page.
3. THE Sistema SHALL validate that request method is POST for create, update, and delete endpoints, rejecting other methods with HTTP 405.

### Requirement 9: Áreas por Página

**User Story:** Como usuario staff, quiero que las áreas se definan por página del plano, para que al navegar entre páginas solo vea las áreas correspondientes.

#### Acceptance Criteria

1. THE Sistema SHALL store the page number for each area, associating the area exclusively to one page of the plano.
2. WHEN computing Contención_Dinámica, THE Sistema SHALL only match pins and areas that share the same page number.
3. WHEN the user creates an area, THE Sistema SHALL associate the area with the currently displayed page number.
