# Manual Detallado — Módulo de Mantenimiento

## Introducción

El módulo de Mantenimiento es el motor de ejecución operativa del sistema Energy. Gestiona todo el ciclo de vida del mantenimiento industrial: desde la definición de rutinas preventivas y su programación automática, hasta la ejecución en campo por técnicos móviles y el cierre técnico con evidencia.

**Acceso**: Menú lateral → Mantenimiento

---

## 1. Dashboard Principal

Al ingresar al módulo de Mantenimiento, el dashboard muestra un resumen ejecutivo en tiempo real.

### Métricas mostradas:

| Indicador | Descripción |
|-----------|-------------|
| OTs Activas | Total de órdenes no finalizadas |
| OTs Pendientes | Órdenes en estado "En Espera" |
| OTs en Ejecución | Órdenes actualmente siendo trabajadas |
| OTs Preventivas | Cantidad de órdenes preventivas activas |
| OTs Correctivas | Cantidad de órdenes correctivas activas |
| Avisos Abiertos | Reportes de falla sin atender |
| Avisos Críticos | Reportes con prioridad crítica |
| Técnicos Disponibles | Personal activo vs. total |
| Tickets del Departamento | Tickets abiertos del mes para tu departamento |

### Secciones del dashboard:

- **Próximas OTs del día**: Las 15 órdenes más próximas programadas para hoy
- **Avisos Prioritarios**: Los 8 avisos más urgentes (Abiertos y En Proceso)
- **Creación rápida de OTNP**: Botón para crear una Orden de Trabajo No Programada directamente

---

## 2. Conceptos Fundamentales

### 2.1 Jerarquía de Tipos

Los tipos clasifican las rutinas de mantenimiento en una estructura jerárquica (árbol):

```
Eléctrica
├── Subestaciones
│   ├── Transformadores
│   └── Interruptores
├── Iluminación
└── Tableros
Mecánica
├── Bombas
├── Compresores
└── Válvulas
Civil
├── Estructura
└── Acabados
```

Cada tipo puede vincularse a:
- Una categoría de activo (para generar OTs automáticas por tipo de equipo)
- Un servicio y KPIs (para medición de desempeño)

### 2.2 Frecuencias

Define cada cuánto se ejecuta una rutina:

| Frecuencia | Días |
|------------|------|
| Diaria | 1 |
| Semanal | 7 |
| Quincenal | 14 |
| Mensual | 30 |
| Bimestral | 60 |
| Trimestral | 90 |
| Semestral | 180 |
| Anual | 365 |

### 2.3 Horarios

Los horarios definen las ventanas laborales disponibles para programar mantenimiento:

- **Días de la semana**: Selección de lunes a domingo
- **Hora de inicio y fin**: Por cada día activo
- **Color**: Para identificación visual en el cronograma
- **Horas semanales**: Calculadas automáticamente

Ejemplo: "Turno Diurno L-V 07:00-16:00" o "Turno Nocturno L-J 22:00-06:00"

### 2.4 Restricciones de Calendario

Fechas no laborables que el sistema respeta al programar:
- Feriados nacionales
- Vacaciones colectivas
- Paros programados de planta
- Cualquier día que no debe tener actividad de mantenimiento

---

## 3. Rutinas de Mantenimiento

### 3.1 ¿Qué es una Rutina?

Una rutina es la plantilla que define QUÉ se debe hacer. Contiene:

| Campo | Descripción |
|-------|-------------|
| Código | Identificador único (ej: RUT-ELE-001) |
| Nombre | Nombre descriptivo (auto-generado si se deja vacío) |
| Tipo | Clasificación jerárquica (Eléctrica → Subestaciones) |
| Frecuencia | Cada cuántos días se ejecuta |
| Tiempo estimado | Duración esperada (ej: 02:00:00) |
| Cantidad de técnicos | Personal requerido |
| Puesto de trabajo | Perfil responsable de ejecutarla |
| Herramientas | Listado de herramientas y materiales necesarios |
| Es invasiva | Si requiere apagar equipos (se marca en rojo en el cronograma) |
| Ubicación predeterminada | Lugar habitual de ejecución |
| Categoría de activo | Tipo de equipo al que aplica |
| Horario predeterminado | Horario sugerido para la ejecución |

### 3.2 Dashboard de Rutinas

**Acceso**: Mantenimiento → Rutinas → Dashboard

Interfaz visual tipo explorador de archivos con:

- **Panel izquierdo**: Árbol de Tipos (expandible/colapsable)
- **Panel derecho**: Listado de rutinas del tipo seleccionado
- **Acciones disponibles**:
  - Crear/editar/eliminar tipos y rutinas
  - Mover rutinas entre tipos (drag & drop)
  - Generar código QR de la rutina
  - Imprimir PDF del procedimiento
  - Exportar a Excel
  - Vincular KPIs a tipos y rutinas

### 3.3 Pasos de Rutina (Procedimiento)

Cada rutina contiene una lista ordenada de pasos que el técnico debe seguir:

| Tipo de Paso | Descripción | Ejemplo |
|--------------|-------------|---------|
| INSTRUCCIÓN | Texto informativo (solo lectura) | "Asegúrese de usar EPP completo" |
| CHECK | Verificación Sí/No/NA | "¿El nivel de aceite es correcto?" |
| NUMÉRICO | Valor medido con rango válido | "Temperatura del motor: ___°C (Rango: 60-90)" |
| TEXTO | Campo de texto libre | "Observaciones generales:" |
| MEDICIÓN | Vinculado a punto de medición del activo | "Registrar lectura del manómetro P-101" |
| FOTO | Solicita evidencia fotográfica | "Fotografiar el estado del filtro" |
| ENCABEZADO | Separador de secciones | "=== VERIFICACIONES ELÉCTRICAS ===" |

Cada paso numérico puede tener:
- Unidad de medida (Bar, °C, Amperios, etc.)
- Valor objetivo
- Rango mínimo y máximo (el sistema alerta si el valor está fuera de rango)

Los pasos también pueden tener **archivos multimedia de referencia** (fotos o videos) que guían al técnico sobre cómo realizar la actividad.

### 3.4 Importación Masiva de Rutinas

**Acceso**: Mantenimiento → Importar Rutinas

Para cargas masivas de rutinas y pasos:

1. Descargar la plantilla Excel/CSV
2. Llenar los datos según el formato requerido
3. Subir el archivo
4. El sistema procesa en segundo plano (Celery) con:
   - Modo verificación (solo valida sin importar)
   - Modo importación (aplica los cambios)
   - Barra de progreso en tiempo real
   - Reporte de errores detallado

**Campos de importación de rutinas**: código, nombre, tipo (soporta formato jerárquico "Padre → Hijo"), frecuencia, tiempo estimado, categoría de activo.

**Campos de importación de pasos**: código de rutina, orden, descripción, tipo de respuesta, unidad, valor objetivo, rango mínimo/máximo.

---

## 4. Programación (Scheduling)

### 4.1 ¿Qué es una Programación?

Una Programación vincula una rutina con un contexto de ejecución:

- **Rutina**: Qué se hace
- **Horarios**: Cuándo se puede hacer (ventanas laborales)
- **Áreas**: Dónde se hace (ubicaciones del árbol)
- **Activos específicos**: En qué equipos (opcional)
- **Fecha inicio / fin**: Período de vigencia

Al crear una programación, el sistema puede:
1. **Generar órdenes inmediatamente**: Crea las OTs para todo el período
2. **Solo proyectar**: Muestra las fechas futuras sin crear OTs reales

### 4.2 Wizard de Programación

**Acceso**: Mantenimiento → Programar Rutina (o desde el dashboard de rutinas)

Asistente paso a paso:

**Paso 1 — Seleccionar Rutina**
- Buscar o seleccionar la rutina a programar
- Se muestra la frecuencia, tiempo estimado y tipo

**Paso 2 — Definir Horarios**
- Seleccionar uno o más horarios de trabajo
- El sistema solo generará OTs en los días y horas del horario

**Paso 3 — Seleccionar Áreas y Activos**
- Elegir áreas del árbol de ubicaciones (se expande a descendientes)
- Opcionalmente, seleccionar activos específicos
- Si la rutina tiene categoría de activo, el sistema filtra automáticamente los equipos compatibles

**Paso 4 — Definir Período**
- Fecha de inicio
- Fecha de fin (opcional, un año por defecto)
- Opción de solo proyectar vs. generar

**Resultado**: El sistema calcula las fechas, asigna técnicos por Round Robin respetando capacidad semanal, y crea las OTs.

### 4.3 Algoritmo de Generación de Órdenes

El sistema utiliza un algoritmo inteligente para crear órdenes:

1. **Expansión de áreas**: Las áreas seleccionadas se expanden a todos sus descendientes
2. **Filtrado de activos**: Se buscan equipos que coincidan con la categoría de la rutina
3. **Búsqueda de slot**: Para cada ciclo de frecuencia, busca el primer horario disponible que:
   - No sea día restringido (feriado/vacación)
   - Corresponda a un día laborable del horario
   - Tenga tiempo suficiente para la duración de la rutina
4. **Asignación de técnico**: Round-Robin entre técnicos del puesto, respetando horas máximas semanales
5. **Agrupación**: OTs del mismo día, área y técnico se agrupan en una sola orden con múltiples activos

### 4.4 Proyecciones ("Ghost OTs")

En el cronograma visual, además de las OTs reales, se muestran **proyecciones**:
- Son OTs futuras que el sistema calculó pero no ha materializado
- Se muestran con estilo diferente (más tenue)
- Permiten planificar visualmente sin comprometer recursos
- Se pueden materializar manualmente o esperar la generación automática

### 4.5 Reprogramación Automática

Cuando una OT preventiva se cierra:
- El sistema puede recalcular las fechas de las OTs futuras de la misma cadena
- Basándose en la fecha real de finalización (no la programada)
- Esto mantiene la frecuencia correcta incluso con atrasos

---

## 5. Cronograma Visual

### 5.1 Vista Anual por Semanas

**Acceso**: Mantenimiento → Cronograma

Visualización de 52 semanas en un año con las OTs representadas como puntos de color:

- **Agrupación por Sistema (Tipo)**: Vista jerárquica Disciplina → Subtipo → Rutina
- **Agrupación por Ubicación**: Vista jerárquica Edificio → Piso → Área
- **Colores**: Cada horario tiene un color asignado; las rutinas invasivas se muestran en rojo

**Filtros disponibles**:
- Por ubicación (selección múltiple del árbol)
- Por tipo/categoría (selección múltiple)
- Por programación específica
- Modo de vista: sistema o ubicación

**Interacciones**:
- Hover sobre un punto muestra tooltip con detalle de la OT
- Clic abre el detalle completo

### 5.2 Vista Mensual (Matriz)

**Acceso**: Mantenimiento → Cronograma → Matriz Mensual

Vista detallada día a día para un mes específico:

- **Filas**: Ubicación Raíz → Sub-ubicación → Categoría → Rutina → Activo
- **Columnas**: Días del mes (1-31)
- **Celdas**: Cada celda muestra las OTs de ese día con:
  - Color del horario
  - Estado (icono diferente para cada estado)
  - Indicador de multi-día (OTs que abarcan más de un día)

**Funcionalidades**:
- Expandir/colapsar niveles del árbol
- Filtrar por ubicación y tipo
- Clic en celda para ver detalle de la OT

### 5.3 Wizard de Cronograma

Interfaz simplificada para generar el cronograma mensual:
- Seleccionar mes y año
- Configurar filtros
- Visualizar antes de generar
- Generar OTs del período seleccionado

### 5.4 Operaciones sobre el Cronograma

Desde la vista de cronograma se pueden realizar operaciones en lote:

| Operación | Descripción |
|-----------|-------------|
| Mover OT | Cambiar fecha de una orden arrastrándola |
| Separar activos | Dividir una OT con múltiples activos en OTs individuales |
| Fusionar OTs | Combinar varias OTs en una sola |
| Actualización masiva de fechas | Mover múltiples OTs simultáneamente |
| Eliminar OTs | Borrar órdenes seleccionadas |

---

## 6. Órdenes de Trabajo (OT)

### 6.1 Tipos de Orden de Trabajo

| Tipo | Código | Origen | Descripción |
|------|--------|--------|-------------|
| Preventiva | OT-XXXXXXXXX | Programación automática | Generada desde una rutina programada |
| Correctiva | OT-XXXXXXXXX | Aviso de mantenimiento | Creada para atender una falla reportada |
| No Programada | OTNP-YYYY-##### | Creación manual | Para trabajos urgentes o no planificados |

### 6.2 Estados de una OT

```
En Espera → Programada → En Ejecución → Realizada
                                    └──→ Cancelada
```

| Estado | Significado |
|--------|-------------|
| En Espera | Creada pero sin técnico o fecha confirmada |
| Programada | Técnico asignado, fecha confirmada |
| En Ejecución | El técnico ya inició el trabajo |
| Realizada | Trabajo completado y cierre registrado |
| Cancelada | Orden cancelada (no se ejecutará) |

### 6.3 Campos de una Orden de Trabajo

**Información General:**
- Código de orden (auto-generado)
- Tipo (Preventiva/Correctiva/No Programada)
- Prioridad (Baja, Media, Alta, Crítica)
- Rutina vinculada (para preventivas)
- Aviso vinculado (para correctivas)
- Descripción corta y detallada

**Asignación:**
- Técnico responsable (líder)
- Colaboradores (equipo de apoyo)
- Supervisor
- Empresa responsable (para subcontratistas)
- Equipo/Grupo de trabajo

**Ubicación y Activos:**
- Ubicación técnica
- Activos asociados (múltiples)
- Proyecto vinculado (opcional)

**Programación:**
- Fecha/hora inicio programado
- Fecha/hora fin programado
- Fecha de ejecución real

**Seguridad:**
- ¿Requiere permiso de trabajo?
- Tipo de permiso sugerido (LOTO, Espacio Confinado, etc.)
- ¿Equipo parado?

### 6.4 Crear una OT No Programada (OTNP)

Desde el dashboard o la interfaz móvil:

1. Clic en "Crear OT No Programada"
2. Completar:
   - Descripción del trabajo
   - Ubicación
   - Activos afectados
   - Prioridad
   - Técnico/empresa responsable
   - Fecha deseada
   - Tipo de permiso (si aplica)
3. Guardar → Se genera código OTNP-2026-00001

### 6.5 Crear OT desde un Aviso (Correctiva)

Desde el tablero Kanban de avisos:

1. Localizar el aviso en la columna "Abierto"
2. Clic en "Crear OT"
3. Asignar técnico y fecha de inicio
4. El aviso pasa automáticamente a "En Proceso"
5. Se genera una OT Correctiva vinculada

### 6.6 Crear OT desde Escaneo QR

Desde la app móvil:

1. Escanear el código QR de una rutina
2. Se precargan los datos de la rutina
3. Seleccionar ubicación y activos
4. Confirmar creación

---

## 7. Ejecución en Campo (Interfaz Móvil)

### 7.1 Mis Órdenes

**Acceso móvil**: Mantenimiento → Mis Órdenes

Lista de OTs asignadas al usuario con:
- Filtro por estado
- Búsqueda por texto
- Código de color por prioridad
- Indicador de estado actual

### 7.2 Detalle de OT (Móvil)

Vista completa de la orden con acciones disponibles:

- **Información general**: Código, tipo, prioridad, fechas
- **Asignación**: Cambiar técnico líder, agregar/remover colaboradores, asignar supervisor y empresa
- **Ubicación**: Cambiar ubicación si no está definida
- **Descripción**: Editar descripción detallada
- **Archivos**: Subir fotos/documentos (antes, durante o al cierre)
- **Checklist**: Resultados del procedimiento (si la OT tiene rutina)
- **Acciones**: Iniciar, Finalizar, Eliminar, Enviar notificación

### 7.3 Flujo de Ejecución

```
1. Técnico ve la OT en "Mis Órdenes"
2. Abre el detalle → Clic "Iniciar"
   → Estado cambia a "En Ejecución"
   → Se registra fecha_ejecucion

3. Ejecuta el checklist paso a paso:
   - CHECK: Marca Sí / No / No Aplica
   - NUMÉRICO: Ingresa valor medido
     (El sistema valida si está en rango)
   - TEXTO: Escribe observaciones
   - MEDICIÓN: Registra lectura del punto
   - FOTO: Captura evidencia fotográfica
   - ENCABEZADO: Solo lectura (separador)

4. Sube fotos de evidencia (Inicio/Durante/Cierre)

5. Clic "Finalizar" → Se abre formulario de cierre:
   - Fecha/hora inicio real
   - Fecha/hora fin real
   - Horas hombre totales
   - Comentarios técnicos / hallazgos
   - Materiales utilizados

6. Confirmar cierre
   → Estado cambia a "Realizada"
   → Se genera PDF automáticamente
   → Se reprograman futuras OTs si aplica
```

### 7.4 Subida de Archivos

Durante la ejecución, el técnico puede subir:

| Momento | Descripción |
|---------|-------------|
| Al Iniciar | Estado previo del equipo/área |
| Durante la Tarea | Evidencia del proceso |
| Al Finalizar | Estado final, resultado del trabajo |

Formatos soportados:
- Imágenes: JPG, PNG, GIF, WebP (se comprimen automáticamente)
- Documentos: PDF, DOC, DOCX, XLS, XLSX

### 7.5 Puntos de Medición

Para pasos tipo MEDICIÓN, el sistema vincula con el punto de medición del activo:
- Muestra el historial de lecturas anteriores
- Valida rangos configurados
- Registra la nueva medición en el historial del equipo

### 7.6 Generación de PDF

Al cerrar una OT, el sistema genera automáticamente un PDF que incluye:
- Datos generales de la orden
- Resultados del checklist completo
- Fotos de evidencia
- Datos del cierre (HH, materiales, comentarios)
- Firma digital del técnico

El PDF se almacena como archivo adjunto de la OT y se puede descargar posteriormente.

### 7.7 Notificaciones

Desde el detalle de la OT se puede:
- **Enviar webhook**: Notifica vía n8n (puede disparar email, Teams, etc.)
- **Enviar WhatsApp**: Notifica al técnico asignado por WhatsApp

---

## 8. Avisos de Mantenimiento

### 8.1 ¿Qué es un Aviso?

Un aviso es una solicitud o reporte de situación anormal que requiere atención de mantenimiento.

### 8.2 Tipos de Aviso

| Tipo | Código | Uso |
|------|--------|-----|
| Avería / Falla | M2 | Equipo dañado o funcionando mal |
| Solicitud de Servicio | M1 | Necesidad de servicio programable |
| Mejora / Modificación | — | Sugerencia de mejora técnica |
| Requerimiento Legal | — | Obligación normativa o de seguridad |
| Mal Uso de Instalaciones | — | Reporte de uso inadecuado |

### 8.3 Estados de un Aviso

| Estado | Significado |
|--------|-------------|
| Abierto | Recién creado, pendiente de atención |
| En Proceso | Se está trabajando en ello (OT creada o técnico asignado) |
| Cerrado | Resuelto satisfactoriamente |
| Cancelado | No procede o fue resuelto de otra forma |

### 8.4 Crear un Aviso (Móvil)

**Acceso**: App → Crear Aviso (o desde ficha de activo)

1. Seleccionar **tipo de aviso** (Avería, Solicitud, etc.)
2. Elegir **ubicación** (se sugiere la del perfil del usuario)
3. Seleccionar **activo** afectado (opcional)
4. Elegir **falla** del catálogo jerárquico:
   - El catálogo se filtra según el puesto del técnico
   - Se muestran solo fallas relevantes al tipo de aviso
5. Escribir **descripción** detallada (obligatorio)
6. Seleccionar **prioridad** (Baja, Media, Alta, Crítica)
7. Asignar **responsable** y **departamento** (opcional)
8. Marcar si hay **equipo parado** (registra tiempos de parada)
9. Adjuntar **fotos** con descripción (apertura/cierre)
10. Enviar

### 8.5 Tablero Kanban de Avisos

**Acceso**: Mantenimiento → Avisos → Dashboard

Vista Kanban con 4 columnas (Abierto, En Proceso, Cerrado, Cancelado):

**Funcionalidades**:
- **Drag & Drop**: Arrastrar avisos entre columnas para cambiar estado
- **Búsqueda**: Filtrar por texto en descripción o ubicación
- **Filtro por departamento**: Ver solo avisos de un departamento
- **Crear OT desde aviso**: Botón que genera una OT correctiva
- **Asignar responsable**: Desde el modal de edición
- **Notificar responsable**: Enviar notificación vía n8n/WhatsApp

**Cada tarjeta muestra**:
- Código (AV-123)
- Descripción truncada
- Ubicación y activo
- Prioridad (color)
- Solicitante
- Responsable asignado
- Indicador de OT vinculada
- Foto (si tiene)

### 8.6 Notificación Automática

Cuando se asigna un responsable a un aviso:
- Se dispara un webhook a n8n automáticamente
- El payload incluye: datos del aviso, ubicación, activo, foto, datos del técnico
- n8n puede enviar por email, WhatsApp, Teams, etc.

### 8.7 Catálogo de Fallas

Estructura jerárquica para clasificar problemas:

```
Fallas Mecánicas
├── Vibración excesiva
├── Fuga de aceite
│   ├── Por sello
│   └── Por empaque
└── Ruido anormal
Fallas Eléctricas
├── Cortocircuito
├── Sobrecalentamiento
└── Fase abierta
```

Cada nodo raíz puede vincularse a **puestos de trabajo** específicos, filtrando las opciones que ve cada técnico según su perfil.

---

## 9. Cierre Técnico

### 9.1 Datos del Cierre

Al finalizar una OT, se registra:

| Campo | Descripción |
|-------|-------------|
| Fecha inicio real | Cuándo realmente se empezó el trabajo |
| Fecha fin real | Cuándo se terminó |
| Horas hombre | Total de HH consumidas |
| Comentarios técnicos | Hallazgos, observaciones, recomendaciones |
| Materiales utilizados | Listado de repuestos/materiales consumidos |
| Técnico responsable | Quién realizó el cierre |

### 9.2 Efectos del Cierre

Al guardar el cierre:
1. La OT pasa automáticamente a estado **REALIZADA**
2. Se registra la fecha de ejecución
3. Se genera el **PDF de la OT** en segundo plano
4. Si tiene programación, se pueden **reprogramar las OTs futuras**
5. Los materiales se pueden vincular con movimientos de inventario

### 9.3 Cierre desde la Interfaz Móvil

El flujo de cierre en móvil incluye:
- Formulario de fechas y HH
- Campo de comentarios
- Revisión del checklist completado
- Confirmación final
- Generación automática del PDF

---

## 10. Personal y Empresas

### 10.1 Gestión de Personal (TécnicoPuesto)

Cada miembro del equipo técnico tiene un perfil con:

| Campo | Descripción |
|-------|-------------|
| Nombre / Apellido | Datos personales |
| Usuario del sistema | Vinculación con cuenta (opcional) |
| Puesto de trabajo | Mecánico, Electricista, etc. |
| Empresa | Si es subcontratista |
| Departamento | Área organizacional |
| Jefe inmediato | Relación jerárquica |
| DNI | Documento de identidad |
| Tipo de sangre | Para emergencias |
| Fecha de alta | Ingreso a la empresa |
| Horas semanales máx. | Capacidad del técnico (default: 40h) |
| Código QR de carnet | ID del carnet físico |
| Foto de perfil | Identificación visual |
| Disponible | Si está activo para asignación |
| Vigente | Si puede ingresar al recinto |

### 10.2 Gestión de Empresas (Subcontratistas)

Cada empresa subcontratista requiere:

**Documentos maestros (únicos)**:
- RTN / Identidad Tributaria
- Acta Constitutiva / Poder
- Contrato Marco

**Documentos mensuales** (con período de gracia hasta el día 10):
- Planilla IHSS
- Altas y Bajas
- Expediente Mensual
- Reportes / Entregables

El sistema valida automáticamente si la empresa tiene documentación completa antes de permitir el acceso QR de su personal.

### 10.3 Control de Asistencia

**Acceso**: Mantenimiento → Asistencia → Estación

Sistema de control de ingreso/egreso mediante escaneo QR:

1. **Estación de escaneo**: Interfaz de kiosko para registro
2. **Procesamiento**: El sistema valida:
   - Vigencia del técnico
   - Documentación de la empresa (si es subcontratista)
   - Registro de entrada/salida
3. **Reporte**: Vista diaria de asistencia con filtros
4. **Vista en vivo**: Panel en tiempo real del personal presente
5. **Gestión de personal**: Vincular códigos QR, buscar personal sin vincular

---

## 11. Dashboard de Cargas de Trabajo

**Acceso**: Mantenimiento → Dashboard Cargas

Visualización de la carga de trabajo por técnico:

- **Horas asignadas vs. capacidad**: Barra de progreso por técnico
- **Distribución semanal**: Carga por semana
- **Asignación rápida**: Reasignar puestos desde el dashboard
- **Alertas de sobrecarga**: Cuando un técnico excede su capacidad

---

## 12. Búsqueda y Consultas

### 12.1 Búsqueda de Órdenes

El sistema ofrece búsqueda por:
- Código de orden (OT-XXXXXXXXX, OTNP-YYYY-#####)
- Nombre de rutina
- Ubicación
- Activo (nombre o código)
- Estado
- Técnico asignado
- Rango de fechas

### 12.2 Búsqueda Global

La búsqueda global cruza información entre:
- Órdenes de trabajo
- Avisos
- Rutinas
- Activos
- Ubicaciones

### 12.3 Detalle de OT via API

Para integraciones externas o uso programático:
- `GET /mantenimiento/api/ot/<pk>/detalle/` → JSON completo de la OT
- `POST /mantenimiento/api/ot/<pk>/update/` → Actualizar estado y notas

---

## 13. Generación de Reportes PDF

### 13.1 PDF de Orden de Trabajo

Incluye:
- Encabezado con logo y datos de la planta
- Información de la orden (código, tipo, prioridad, fechas)
- Ubicación y activos
- Personal asignado
- Resultados del checklist (si aplica)
- Fotos de evidencia
- Datos del cierre
- Código QR de la orden

### 13.2 PDF de Rutina

Impresión del procedimiento completo:
- Datos de la rutina
- Listado de pasos con tipos de respuesta
- Espacios para llenado manual
- Imágenes de referencia
- Código QR para escaneo rápido

### 13.3 PDF de Aviso

Reporte del aviso con:
- Datos del aviso y solicitante
- Ubicación y activo afectado
- Falla reportada
- Fotos de apertura/cierre
- Acciones realizadas

---

## 14. Planificación Mensual

**Acceso**: Mantenimiento → Cronograma → Wizard Mensual

Permite crear un plan mensual formal:

| Estado | Significado |
|--------|-------------|
| Borrador | En elaboración, puede modificarse libremente |
| Aprobado | Validado por supervisión, listo para ejecución |
| En Ejecución | El mes está en curso |
| Cerrado | Mes finalizado, solo consulta |

Las OTs pueden vincularse a una planificación mensual para trazabilidad.

---

## 15. Notificaciones del Módulo

El sistema genera notificaciones internas para:
- OTs próximas a vencer
- Avisos críticos sin atender
- Resultados de importación (éxito/error)
- Asignaciones de trabajo
- Cambios de estado relevantes

**Tipos de notificación**: Éxito, Error, Información, Advertencia

---

## 16. Integraciones

### 16.1 n8n (Automatizaciones)

- Webhook de asignación de avisos → Notificación al técnico
- Webhook de cierre de OT → Actualización de KPIs
- Disparador manual desde detalle de OT

### 16.2 WhatsApp

- Notificación de OT asignada
- Recordatorio de OT próxima
- Alerta de aviso crítico

### 16.3 Push Notifications (WebPush)

- Avisos cuando se asigna una tarea
- Alertas de cambio de estado
- Recordatorios de cronograma

### 16.4 Generación Automática de PDF (Celery)

- Tarea en segundo plano
- Se puede verificar el estado de generación
- El PDF se adjunta automáticamente a la OT

---

## 17. Importación y Exportación Masiva

### 17.1 Módulos de Importación

| Módulo | Datos | Formato |
|--------|-------|---------|
| Rutinas | Rutinas completas | CSV / Excel |
| Pasos de Rutina | Procedimientos | CSV / Excel |
| Tipos (Categorías) | Árbol jerárquico | CSV / Excel |
| Personal | Técnicos y datos | CSV / Excel |
| Órdenes de Trabajo | OTs históricas | CSV / Excel |
| Avisos | Reportes históricos | CSV / Excel |

### 17.2 Características de la Importación

- **Procesamiento en segundo plano**: No bloquea la interfaz (Celery)
- **Barra de progreso en tiempo real**: Actualización cada 10 filas
- **Modo verificación**: Valida sin aplicar cambios
- **Modo dry-run**: Simula la importación completa
- **Sparse Update**: Solo actualiza campos que tengan valor (no sobreescribe con vacío)
- **Detección de duplicados**: Por código único
- **Resolución jerárquica**: Soporta formato "Padre → Hijo" para tipos
- **Encoding inteligente**: Detecta automáticamente la codificación del archivo
- **Reporte de errores**: Detalla fila por fila los problemas encontrados
- **Registro de importación**: Historial de todas las importaciones realizadas

### 17.3 Proceso de Importación

1. Ir a la sección de importación correspondiente
2. Descargar la plantilla (botón "Descargar Plantilla")
3. Llenar los datos en Excel/CSV
4. Subir el archivo
5. Seleccionar modo (Verificar / Importar)
6. Monitorear progreso
7. Revisar reporte de resultados (nuevos, actualizados, omitidos, errores)

### 17.4 Exportación

- **Rutinas a Excel**: Exporta todas las rutinas con sus datos completos
- **Cronograma**: Se puede exportar la vista actual
- **Reportes PDF**: Generados individualmente por OT, rutina o aviso

---

## 18. Permisos y Seguridad

### 18.1 Permisos Móviles

El sistema controla qué funciones están disponibles para cada usuario:

| Permiso | Funciones habilitadas |
|---------|----------------------|
| `tareas_hoy` | Ver cronograma, detalle de OT, iniciar/finalizar |
| `crear_aviso` | Crear y editar avisos, subir fotos |
| (staff) | Acceso completo a todas las funciones |
| (superuser) | Ve todas las OTs (no solo las suyas) |

### 18.2 Visibilidad de Datos

- **Técnicos**: Solo ven sus OTs asignadas y las de sus grupos
- **Supervisores**: Ven las OTs de su equipo
- **Gerentes**: Acceso completo, pueden modificar OTs finalizadas
- **Superusuarios**: Sin restricciones

### 18.3 Control de Empresas

El sistema verifica la documentación de empresas subcontratistas antes de permitir:
- Ingreso de personal al recinto (vía QR)
- Asignación de OTs a la empresa

---

## 19. Flujos Completos (Resumen)

### 19.1 Flujo Preventivo

```
Crear Rutina → Definir Pasos → Crear Programación (Wizard)
→ Sistema genera OTs automáticamente → Técnico ve en "Mis Órdenes"
→ Inicia OT → Ejecuta Checklist → Sube evidencia → Cierra OT
→ PDF generado → Reprogramación de futuras
```

### 19.2 Flujo Correctivo

```
Usuario reporta Aviso (Falla) → Aparece en Kanban de Avisos
→ Supervisor arrastra a "En Proceso" → Crea OT Correctiva
→ Asigna técnico → Técnico ve en "Mis Órdenes"
→ Ejecuta reparación → Sube fotos → Cierra OT
→ Aviso pasa a "Cerrado"
```

### 19.3 Flujo No Programado

```
Situación urgente → Clic "Crear OTNP" (Dashboard o Móvil)
→ Llenar datos mínimos → Asignar técnico
→ Técnico ejecuta → Cierra OT → PDF
```

### 19.4 Flujo de Asistencia

```
Técnico llega al sitio → Escanea QR de carnet en Estación
→ Sistema valida vigencia y documentación de empresa
→ Registra hora de entrada
→ Al salir: Escanea de nuevo → Registra hora de salida
→ Reporte diario/semanal disponible
```

---

*Versión del manual: 1.0 — Julio 2026*
*Módulo: Mantenimiento — Sistema Energy (SoftCom-CCG)*
