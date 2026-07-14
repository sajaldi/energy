# Requirements Document

## Introduction

Este feature transforma el renderizado de materiales en la vista 3D de racks (`/inventarios/racks/{id}/3d/`) para que los materiales se visualicen con sus dimensiones físicas reales (ancho, alto, profundidad) en lugar de usar un tamaño basado en la cantidad de stock. Los materiales se apilan verticalmente dentro de cada celda conforme se agregan, respetando la gravedad y agrupándose visualmente cuando coexisten en la misma posición.

## Glossary

- **Rack_3D_View**: La vista de Three.js que renderiza el rack tridimensional en el navegador, accesible en `/inventarios/racks/{id}/3d/`.
- **Material_Box**: La representación 3D (mesh de caja) de un material individual dentro de una celda del rack.
- **Cell**: El espacio disponible dentro de un nivel y sección del rack donde se almacenan materiales. Sus dimensiones se derivan del rack (ancho de sección, alto de nivel, profundidad del rack).
- **Stacking_Engine**: El algoritmo responsable de calcular la posición vertical de cada Material_Box dentro de una Cell, apilando de abajo hacia arriba.
- **Material**: El modelo de datos que describe un insumo/repuesto con campos `ancho` (cm), `alto` (cm), `peso` (lb), y opcionalmente `profundidad` (cm).
- **RackPosition**: El modelo que vincula un Material a una Cell específica (nivel, sección) con una cantidad asociada.
- **Overflow_Indicator**: Indicador visual que se muestra cuando los materiales apilados exceden la altura disponible de la Cell.
- **Depth_Default**: El valor de profundidad por defecto (en cm) asignado cuando un Material no tiene el campo `profundidad` definido.

## Requirements

### Requisito 1: Campo de profundidad en el modelo Material

**Historia de Usuario:** Como administrador del inventario, quiero registrar la profundidad de cada material, para que la vista 3D pueda renderizar cajas con dimensiones completas.

#### Criterios de Aceptación

1. THE Material SHALL incluir un campo `profundidad` de tipo DecimalField (max_digits=8, decimal_places=2, null=True, blank=True, verbose_name="Profundidad (cm)") con help_text "Profundidad del material en cm" y un validador MinValueValidator(0.01) que rechace valores menores a 0.01.
2. WHEN la vista rack_3d_view serializa las posiciones del rack, THE System SHALL incluir la clave `profundidad` con el valor float del campo `profundidad` del Material asociado, o null si el Material no tiene valor asignado.
3. WHEN un Material tiene el campo `profundidad` con valor null, THE Rack_3D_View SHALL utilizar el valor por defecto de 10 cm para la profundidad de la Material_Box.
4. WHEN un Material tiene el campo `ancho` con valor null, THE Rack_3D_View SHALL utilizar un valor por defecto de 10 cm para el ancho de la Material_Box.
5. WHEN un Material tiene el campo `alto` con valor null, THE Rack_3D_View SHALL utilizar un valor por defecto de 10 cm para la altura de la Material_Box.

### Requisito 2: Renderizado basado en dimensiones reales

**Historia de Usuario:** Como usuario del sistema de inventario, quiero ver los materiales renderizados según sus dimensiones físicas reales, para tener una representación visual precisa del espacio ocupado en el rack.

#### Criterios de Aceptación

1. THE Rack_3D_View SHALL renderizar cada Material_Box con dimensiones proporcionales a los valores `ancho`, `alto` y `profundidad` del Material, donde 1 cm del Material corresponde a 1 unidad Three.js en el espacio del rack.
2. WHEN cualquier dimensión del Material (ancho o profundidad) excede la dimensión correspondiente de la Cell, THE Rack_3D_View SHALL calcular el factor de escala mínimo entre (cellW * 0.95 / ancho) y (cellD * 0.95 / profundidad), y aplicar ese factor uniformemente a las tres dimensiones (ancho, alto, profundidad) para mantener la proporción.
3. WHEN ninguna dimensión del Material excede su dimensión correspondiente de la Cell, THE Rack_3D_View SHALL renderizar la Material_Box con las dimensiones exactas del Material sin escalar.
4. THE Rack_3D_View SHALL centrar horizontalmente (eje X) y en profundidad (eje Z) cada Material_Box dentro de la Cell.
5. THE API de datos del rack SHALL incluir el campo `profundidad` en la respuesta JSON de cada posición con su valor float o null.

### Requisito 3: Apilamiento vertical de materiales

**Historia de Usuario:** Como usuario del sistema, quiero que los materiales se apilen de abajo hacia arriba dentro de cada celda, para visualizar cómo se llenan las posiciones de manera realista.

#### Criterios de Aceptación

1. THE Stacking_Engine SHALL posicionar la primera Material_Box con su base sobre la superficie inferior de la Cell (shelf surface), donde la posición Y base es igual a `nivel * levelHeight`.
2. WHEN se agrega un nuevo material a una Cell que ya contiene materiales, THE Stacking_Engine SHALL posicionar la nueva Material_Box directamente encima del material más alto existente, sin espacio entre ambas cajas.
3. THE Stacking_Engine SHALL calcular la posición Y de cada Material_Box como `nivel * levelHeight` más la suma de las alturas de todos los materiales apilados debajo de la Material_Box actual.
4. WHEN la cantidad de un RackPosition es mayor a 1, THE Stacking_Engine SHALL renderizar múltiples instancias de la Material_Box apiladas verticalmente, una por cada unidad de cantidad.
5. THE Stacking_Engine SHALL apilar los materiales de abajo hacia arriba siguiendo el orden ascendente del ID de RackPosition.
6. IF la suma total de alturas de los materiales apilados en una Cell excede la altura disponible de la Cell (levelHeight), THEN THE Stacking_Engine SHALL continuar renderizando los materiales en sus posiciones calculadas, permitiendo que sobresalgan visualmente del límite superior de la celda.
7. THE Stacking_Engine SHALL utilizar la propiedad de altura definida en la Material_Box de cada RackPosition para calcular el desplazamiento vertical de los materiales subsiguientes en la pila.

### Requisito 4: Detección y señalización de desbordamiento

**Historia de Usuario:** Como usuario del sistema, quiero recibir una señal visual cuando los materiales apilados exceden el espacio de la celda, para identificar rápidamente posiciones sobrecargadas.

#### Criterios de Aceptación

1. WHEN la altura total de los materiales apilados excede la altura disponible de la Cell (altura combinada > cellH), THE Rack_3D_View SHALL mostrar el Overflow_Indicator en la Cell afectada en un tiempo no mayor a 500 ms tras el cambio de estado.
2. THE Overflow_Indicator SHALL consistir en un borde pulsante de color rojo con opacidad entre 0.4 y 0.7, frecuencia de pulso entre 1 Hz y 2 Hz, y un grosor de borde entre 2 y 4 unidades de pantalla alrededor de la Cell desbordada.
3. WHEN un material desborda la Cell, THE Rack_3D_View SHALL recortar (clip) la Material_Box visualmente en el límite superior de la Cell, sin modificar los datos del material.
4. WHILE una Cell se encuentra en estado de desbordamiento, THE Rack_3D_View SHALL mostrar en el tooltip de la Cell el porcentaje de exceso calculado como ((altura_total - cellH) / cellH) × 100, redondeado al entero más cercano y expresado con el sufijo "%".
5. WHEN la altura total de los materiales apilados deja de exceder la altura disponible de la Cell (altura combinada ≤ cellH), THE Rack_3D_View SHALL ocultar el Overflow_Indicator y restaurar la visualización normal de la Cell en un tiempo no mayor a 500 ms.

### Requisito 5: Agrupación visual de materiales en la misma celda

**Historia de Usuario:** Como usuario del sistema, quiero distinguir visualmente los diferentes materiales dentro de una misma celda, para identificar rápidamente qué contiene cada posición.

#### Criterios de Aceptación

1. THE Rack_3D_View SHALL asignar un color fijo y distinto a cada Material_Box según el valor de `tipo_material` del modelo Material, utilizando un mapa determinístico de 7 colores (uno por cada valor de TIPO_MATERIAL_CHOICES: INSUMO, REPUESTO, CONSUMIBLE, MEDICAMENTO, HERRAMIENTA, EPP, OTRO) de modo que el mismo tipo siempre produzca el mismo color en cualquier celda.
2. WHEN dos Material_Boxes adyacentes verticalmente en la misma Cell pertenecen a materiales con diferente `tipo_material`, THE Rack_3D_View SHALL renderizar un separador visual (gap de 0.5 cm escalado) entre ellas; Material_Boxes del mismo material apiladas por cantidad no tendrán separador entre sí.
3. WHEN el usuario pasa el cursor sobre una Material_Box específica, THE Rack_3D_View SHALL resaltar únicamente esa Material_Box cambiando su opacidad de 0.85 (base) a 1.0.
4. WHEN el cursor del usuario deja de estar sobre una Material_Box previamente resaltada, THE Rack_3D_View SHALL restaurar la opacidad de dicha Material_Box a su valor base de 0.85.
5. THE Rack_3D_View SHALL mostrar una etiqueta flotante (sprite de texto) encima de cada grupo de Material_Boxes que comparten el mismo ID de Material dentro de una Cell, indicando el nombre del material (máximo 30 caracteres, truncado con "…") y la cantidad de unidades del grupo.

### Requisito 6: Actualización dinámica al agregar/quitar materiales

**Historia de Usuario:** Como usuario del sistema, quiero que el apilamiento se actualice en tiempo real cuando agrego o quito materiales, para ver inmediatamente el efecto de mis cambios.

#### Criterios de Aceptación

1. WHEN se asigna un material exitosamente via la API, THE Rack_3D_View SHALL recalcular y re-renderizar el apilamiento completo de la Cell afectada con una animación de transición.
2. WHEN se quita un material exitosamente via la API, THE Rack_3D_View SHALL recalcular las posiciones de los materiales restantes, desplazando verticalmente hacia abajo los materiales superiores al material removido para eliminar el espacio vacío, con animación de transición.
3. THE Rack_3D_View SHALL completar la animación de transición de apilamiento en un máximo de 300 milisegundos.
4. WHILE la animación de apilamiento está en curso, THE Rack_3D_View SHALL deshabilitar click de selección, hover de tooltip y cualquier acción de asignación o remoción sobre la Cell afectada hasta que la animación finalice.
5. IF la llamada a la API de asignación o remoción falla, THEN THE Rack_3D_View SHALL mantener el estado visual previo de la Cell sin modificaciones y mostrar una notificación de error al usuario indicando que la operación no se completó.
6. IF se recibe una nueva operación de asignación o remoción sobre la misma Cell mientras una animación está en curso, THEN THE Rack_3D_View SHALL encolar la operación y ejecutarla secuencialmente una vez finalizada la animación actual, procesando un máximo de 5 operaciones encoladas.

### Requisito 7: Integración del campo profundidad en el modal de asignación

**Historia de Usuario:** Como usuario del sistema, quiero poder ingresar la profundidad del material al asignarlo a una posición del rack, para que la visualización 3D sea completa.

#### Criterios de Aceptación

1. WHEN un Material no tiene valor de `profundidad` y se selecciona para asignar, THE Rack_3D_View SHALL mostrar un campo de entrada adicional para "Profundidad (cm)" en el modal de asignación junto a los campos de Ancho y Alto.
2. WHEN el usuario ingresa un valor de profundidad en el modal de asignación, THE API de asignación SHALL guardar el valor en el campo `profundidad` del Material si el valor es mayor a 0.
3. THE modal de asignación SHALL mostrar las dimensiones existentes del Material en formato "ancho × alto × profundidad cm" cuando los tres valores estén disponibles.
4. WHEN un Material ya tiene los tres campos de dimensiones (ancho, alto, profundidad) con valores asignados, THE modal de asignación SHALL no mostrar campos de entrada para dimensiones, solo la información existente.
5. THE campo de profundidad en el modal SHALL aceptar valores numéricos positivos con hasta 2 decimales y rechazar valores menores o iguales a 0.
