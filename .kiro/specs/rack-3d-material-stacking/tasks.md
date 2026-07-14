# Implementation Plan: Rack 3D Material Stacking

## Overview

Transform the 3D rack view to render materials with their real physical dimensions (width, height, depth) and stack them vertically within each cell. Implementation covers backend model changes, serialization updates, a new stacking engine, overflow detection, color-coded rendering, animations, and modal integration.

## Tasks

- [x] 1. Backend: Add profundidad field and migration
  - [x] 1.1 Add `profundidad` field to Material model
    - Add `profundidad = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, verbose_name="Profundidad (cm)", help_text="Profundidad del material en cm", validators=[MinValueValidator(Decimal('0.01'))])` to the Material model in `inventarios/models.py`
    - Run `python manage.py makemigrations inventarios` and `python manage.py migrate`
    - _Requirements: 1.1_

  - [ ]* 1.2 Write unit test for profundidad field validation
    - Test that values > 0.01 are accepted
    - Test that values ≤ 0 and exactly 0.01 boundary are handled correctly by MinValueValidator
    - Add tests in `inventarios/tests.py` or `inventarios/tests/test_material_profundidad.py`
    - **Property 1: Profundidad validation accepts only positive values**
    - **Validates: Requirements 1.1, 7.5**
    - _Requirements: 1.1_

- [x] 2. Backend: Update rack_3d_view serialization
  - [x] 2.1 Include `profundidad` and `tipo_material` in rack_data JSON
    - In `inventarios/views.py`, locate the `rack_3d_view` function
    - Add `'profundidad': float(p.material.profundidad) if p.material and p.material.profundidad else None` to each position dict
    - Add `'tipo_material': p.material.tipo_material if p.material else None` to each position dict
    - Ensure the serialized JSON matches the structure defined in design (Data Models section)
    - _Requirements: 1.2, 2.5_

  - [ ]* 2.2 Write unit test for rack_data serialization
    - Verify `profundidad` field is present in JSON context with correct float value
    - Verify `tipo_material` field is present
    - Verify null handling when material has no profundidad
    - _Requirements: 1.2, 2.5_

- [x] 3. Backend: Update API assign_position to handle profundidad
  - [x] 3.1 Modify `api_rack_assign_position` to save profundidad
    - Parse `profundidad` from request data
    - Validate that profundidad > 0 when provided
    - Save to material's profundidad field if valid
    - Return `profundidad` and `tipo_material` in the API response JSON
    - Return HTTP 400 with `{"error": "profundidad debe ser mayor a 0"}` if invalid
    - _Requirements: 7.2, 7.5_

  - [ ]* 3.2 Write integration test for API assign with profundidad
    - Test successful assignment saves profundidad to Material
    - Test response includes profundidad and tipo_material
    - Test validation rejects profundidad ≤ 0
    - _Requirements: 7.2, 7.5_

- [x] 4. Checkpoint - Backend complete
  - Ensure all backend tests pass, ask the user if questions arise.

- [x] 5. Frontend: Implement Stacking Engine
  - [x] 5.1 Create the `computeStackLayout` function
    - Implement in `inventarios/templates/inventarios/rack_3d.html` as an inline module (or separate `<script>` block)
    - Implement the sorting by position ID ascending
    - Apply default dimensions (10 cm) when values are null
    - Calculate uniform scaling when material exceeds cell bounds (cellW × 0.95, cellD × 0.95)
    - Calculate cumulative Y positions (stacking from bottom)
    - Handle quantity expansion (N instances per RackPosition)
    - Insert gap (0.5 cm × scale) between different tipo_material groups
    - Mark `isOverflow` flag when box top exceeds cellHeight
    - Return array of StackedBox objects as defined in design
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

  - [ ]* 5.2 Write property test: Dimension preservation when material fits
    - Use fast-check to generate materials with dimensions ≤ cellW × 0.95 and ≤ cellD × 0.95
    - Assert resulting StackedBox has w = ancho, h = alto, d = profundidad
    - **Property 2: Dimension preservation when material fits within cell**
    - **Validates: Requirements 2.1, 2.3**

  - [ ]* 5.3 Write property test: Uniform scaling preserves aspect ratio
    - Use fast-check to generate materials exceeding cell bounds
    - Assert w/ancho == h/alto == d/profundidad and w ≤ cellW × 0.95 and d ≤ cellD × 0.95
    - **Property 3: Uniform scaling preserves aspect ratio**
    - **Validates: Requirements 2.2**

  - [ ]* 5.4 Write property test: Centering invariant
    - Use fast-check to generate arbitrary materials and cell dimensions
    - Assert all StackedBox results have x = 0 and z = 0
    - **Property 4: Centering invariant**
    - **Validates: Requirements 2.4**

  - [ ]* 5.5 Write property test: Cumulative stacking positions
    - Use fast-check to generate sequences of materials
    - Assert baseY of box[n] equals sum of heights of boxes 0..n-1
    - **Property 5: Cumulative stacking positions**
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.7**

  - [ ]* 5.6 Write property test: Quantity expansion produces correct instance count
    - Use fast-check to generate RackPositions with cantidad 1..20
    - Assert output contains exactly N boxes with instanceIndex 0..N-1
    - **Property 6: Quantity expansion produces correct instance count**
    - **Validates: Requirements 3.4**

  - [ ]* 5.7 Write property test: ID ordering determines vertical position
    - Use fast-check to generate two or more positions with distinct IDs
    - Assert all boxes of lower-ID position have lower Y center than higher-ID position
    - **Property 7: ID ordering determines vertical position**
    - **Validates: Requirements 3.5**

  - [ ]* 5.8 Write property test: Completeness – all materials rendered
    - Use fast-check to generate positions with various quantities
    - Assert total output box count equals sum of all cantidades
    - **Property 8: Completeness – all materials rendered regardless of overflow**
    - **Validates: Requirements 3.6**

  - [ ]* 5.9 Write property test: Type-change gap logic
    - Use fast-check to generate sequences with same and different tipo_material
    - Assert gap exists between different types and no gap between same types
    - **Property 11: Type-change gap logic**
    - **Validates: Requirements 5.2**

- [x] 6. Frontend: Implement Overflow Detector
  - [x] 6.1 Create the `detectOverflow` function
    - Implement detection logic: overflow = totalHeight > cellHeight
    - Calculate percent = Math.round(((totalHeight - cellH) / cellH) × 100) when overflow
    - Return {overflow: boolean, percent: number}
    - _Requirements: 4.1, 4.4, 4.5_

  - [ ]* 6.2 Write property test: Overflow percentage computation
    - Use fast-check to generate layouts with various total heights
    - Assert correct percentage calculation and edge cases (exactly at boundary)
    - **Property 9: Overflow percentage computation**
    - **Validates: Requirements 4.4**

- [x] 7. Frontend: Box Factory and Color Map
  - [x] 7.1 Implement color map and box creation
    - Define `TIPO_COLOR_MAP` with 7 distinct colors as specified in design
    - Create mesh factory that generates BoxGeometry with dimensions from StackedBox
    - Apply MeshStandardMaterial with color from tipo_material mapping
    - Set base opacity to 0.85 with transparent: true
    - Use fallback color (gray 0x6b7280) for unknown tipo_material values
    - _Requirements: 5.1_

  - [ ]* 7.2 Write property test: Deterministic color mapping
    - Use fast-check to generate tipo_material values from the enum
    - Assert same input always returns same color, and all 7 types map to distinct colors
    - **Property 10: Deterministic color mapping**
    - **Validates: Requirements 5.1**

- [x] 8. Frontend: Integrate stacking into the render pipeline
  - [x] 8.1 Replace existing material rendering with stacking-based rendering
    - Remove the old `sizeFrac = stock / 10` logic and Z-axis distribution
    - For each cell, call `computeStackLayout` with position data and cell dimensions
    - Create meshes via Box Factory using StackedBox results
    - Position meshes at calculated (x, y, z) relative to cell origin
    - Apply clipping planes (`localClippingEnabled`) at cell top boundary for overflow boxes
    - _Requirements: 2.1, 3.1, 3.6, 4.3_

  - [x] 8.2 Implement Overflow Indicator
    - For each cell, call `detectOverflow` after computing layout
    - When overflow is true, render a pulsating red border (opacity 0.4–0.7, frequency 1–2 Hz, border width 2–4 units)
    - Show/hide indicator within 500ms of state change
    - Include overflow percentage in cell tooltip
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [x] 9. Checkpoint - Core rendering complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Frontend: Labels and hover interactions
  - [x] 10.1 Implement text labels and hover effects
    - Create text sprite labels above each material group showing: material name (max 30 chars, truncated with "…") and quantity
    - Implement raycasting for hover detection on Material_Boxes
    - On hover: change opacity from 0.85 to 1.0
    - On hover exit: restore opacity to 0.85
    - _Requirements: 5.3, 5.4, 5.5_

  - [ ]* 10.2 Write property test: Label truncation
    - Use fast-check to generate strings of varying lengths
    - Assert truncation to 30 chars + "…" when length > 30, unchanged otherwise
    - **Property 12: Label truncation**
    - **Validates: Requirements 5.5**

  - [ ]* 10.3 Write property test: Dimension format string
    - Use fast-check to generate three positive numbers
    - Assert format matches `${ancho} × ${alto} × ${profundidad} cm`
    - **Property 13: Dimension format string**
    - **Validates: Requirements 7.3**

- [x] 11. Frontend: Animation System
  - [x] 11.1 Implement `animateTransition` for stacking updates
    - Interpolate mesh positions from current to target using requestAnimationFrame
    - Complete animation within 300ms maximum
    - Disable interactions (click, hover, assign/remove) on the affected cell during animation
    - Call onComplete callback when animation finishes
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [x] 11.2 Implement operation queue for concurrent requests
    - Queue new assign/remove operations that arrive during an active animation
    - Process queued operations sequentially after current animation completes
    - Limit queue to 5 operations maximum; ignore additional operations above limit
    - _Requirements: 6.6_

- [x] 12. Frontend: Dynamic update on assign/remove
  - [x] 12.1 Wire API responses to re-render pipeline
    - On successful assign: parse response (including profundidad, tipo_material), recompute layout for affected cell, trigger animated transition
    - On successful remove: recompute layout, animate remaining boxes collapsing downward
    - On API failure: maintain previous visual state, show toast notification "Error: la operación no se completó"
    - _Requirements: 6.1, 6.2, 6.5_

- [x] 13. Frontend: Modal integration for profundidad field
  - [x] 13.1 Update assignment modal to handle profundidad
    - When a Material lacks profundidad value, show an input field "Profundidad (cm)" alongside Ancho and Alto fields
    - When all three dimensions exist, display them as "ancho × alto × profundidad cm" (read-only) instead of input fields
    - Validate profundidad input: numeric, positive, up to 2 decimals, reject ≤ 0
    - Disable "Agregar" button when required dimensions are missing with message "Debes ingresar dimensiones"
    - Send profundidad value in API assign request body
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 14. Final checkpoint - All features integrated
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties using fast-check
- Unit tests validate specific examples and edge cases
- Backend tasks (1-3) are independent of frontend tasks (5-13)
- The stacking engine (task 5) is the core dependency for all rendering tasks
- The `computeStackLayout` function should be extractable for testing in isolation (Node.js environment with fast-check)

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "2.1", "3.1"] },
    { "id": 1, "tasks": ["1.2", "2.2", "3.2", "5.1"] },
    { "id": 2, "tasks": ["5.2", "5.3", "5.4", "5.5", "5.6", "5.7", "5.8", "5.9", "6.1"] },
    { "id": 3, "tasks": ["6.2", "7.1"] },
    { "id": 4, "tasks": ["7.2", "8.1"] },
    { "id": 5, "tasks": ["8.2", "10.1", "11.1"] },
    { "id": 6, "tasks": ["10.2", "10.3", "11.2"] },
    { "id": 7, "tasks": ["12.1"] },
    { "id": 8, "tasks": ["13.1"] }
  ]
}
```
