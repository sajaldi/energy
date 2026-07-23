# Manual de Usuario — Sistema Energy (SoftCom-CCG)

## Introducción

Energy es una plataforma integral de gestión industrial diseñada para plantas de energía. El sistema centraliza la administración de activos, mantenimiento preventivo y correctivo, presupuestos, seguridad industrial, inventarios, proyectos, documentos técnicos y más.

### Acceso al Sistema

- **URL**: Proporcionada por el administrador del sistema
- **Credenciales**: Usuario y contraseña asignados por el administrador
- **Navegadores compatibles**: Chrome, Edge, Firefox (versiones recientes)

---

## 1. Dashboard Principal

Al iniciar sesión, el usuario accede al dashboard principal que muestra:

- Resumen de órdenes de trabajo pendientes
- Indicadores clave de rendimiento (KPIs)
- Accesos rápidos a módulos frecuentes
- Notificaciones pendientes

---

## 2. Gestión de Activos

### 2.1 Explorador de Activos

El módulo de activos permite administrar toda la infraestructura física de la planta.

**Acceso**: Menú lateral → Activos

#### Funcionalidades principales:

- **Vista de árbol jerárquico**: Navega la estructura Sitio → Edificio → Área → Equipo
- **Ficha del activo**: Cada equipo tiene una ficha con:
  - Datos técnicos (marca, modelo, serie, código EPC)
  - Estado actual (Operativo, En Mantenimiento, Fuera de Servicio)
  - Historial de mantenimiento
  - Documentos asociados
  - Ubicación en plano técnico

#### Cómo buscar un activo:

1. Usa la barra de búsqueda por código o nombre
2. O navega el árbol de ubicaciones en el panel lateral
3. Haz clic en el activo para ver su ficha completa

### 2.2 Visor de Planos

Permite localizar activos sobre planos técnicos de la planta.

- Los activos aparecen como pines sobre el plano
- Haz clic en un pin para ver los detalles del equipo
- Usa los controles de zoom para acercar/alejar
- Navega entre páginas del plano con los botones de paginación

### 2.3 Scanner QR

- Escanea el código QR de un equipo con la cámara del dispositivo
- El sistema mostrará automáticamente la ficha del activo

---

## 3. Mantenimiento

### 3.1 Órdenes de Trabajo (OT)

El motor de ejecución operativa del sistema. Gestiona mantenimientos preventivos y correctivos.

**Acceso**: Menú lateral → Mantenimiento → Órdenes de Trabajo

#### Tipos de OT:

| Tipo | Descripción |
|------|-------------|
| Preventiva | Generada automáticamente desde rutinas programadas |
| Correctiva | Creada manualmente ante una falla o aviso |

#### Crear una OT Correctiva:

1. Ir a Mantenimiento → Órdenes de Trabajo → Nueva OT
2. Seleccionar el equipo afectado
3. Describir la falla o situación
4. Asignar prioridad (Baja, Media, Alta, Crítica)
5. Asignar técnico responsable
6. Guardar

#### Cerrar una OT:

1. Abrir la OT desde el listado
2. Ir a la pestaña "Cierre"
3. Registrar:
   - Horas hombre empleadas
   - Materiales utilizados
   - Hallazgos y observaciones
   - Evidencia fotográfica
4. Confirmar cierre

### 3.2 Rutinas de Mantenimiento

Plantillas de tareas preventivas con frecuencias configurables.

- **Frecuencias disponibles**: Diaria, Semanal, Quincenal, Mensual, Trimestral, Semestral, Anual
- Cada rutina contiene procedimientos paso a paso
- Se generan OTs automáticamente según el cronograma

### 3.3 Cronograma

Visualizador interactivo de planificación anual/mensual.

- Vista por mes o por año
- Código de colores según estado (Pendiente, En Ejecución, Completada)
- Filtros por ubicación, técnico y tipo de rutina

### 3.4 Avisos de Mantenimiento

Solicitudes de mantenimiento (reportes de falla) levantadas por usuarios.

| Tipo | Código | Descripción |
|------|--------|-------------|
| Servicio | M1 | Solicitud de servicio programable |
| Avería | M2 | Reporte de falla que requiere atención inmediata |

---

## 4. Presupuestos y Finanzas

### 4.1 Cost Sheet (Hoja de Costos)

Monitoreo en tiempo real del presupuesto.

**Acceso**: Menú lateral → Presupuestos → Cost Sheet

Muestra por cada partida:
- Presupuesto original
- Presupuesto vigente (con transferencias y adicionales)
- Comprometido (contratos y órdenes de compra activos)
- Gastado (facturas registradas)
- Disponible (vigente - comprometido - gastado)

### 4.2 Partidas Presupuestarias

Control por disciplina técnica:
- Eléctrico
- Mecánico
- Civil
- Instrumentación
- Otros

### 4.3 Requisiciones

Gestión de solicitudes de compra integradas con Microsoft Dynamics 365.

#### Flujo de una requisición:

1. **Creación**: El usuario genera la solicitud con los artículos requeridos
2. **Aprobación**: Pasa por flujo de aprobación según monto
3. **Sincronización**: Se envía automáticamente a Dynamics 365
4. **Seguimiento**: Estado actualizado periódicamente desde el ERP

#### Crear una requisición:

1. Ir a Presupuestos → Requisiciones → Nueva
2. Seleccionar la partida presupuestaria
3. Agregar artículos (descripción, cantidad, unidad, precio estimado)
4. Adjuntar documentos de soporte
5. Enviar a aprobación

### 4.4 Cotizaciones

Formulario multi-disciplina para registro de cotizaciones de proveedores.

- Agregar secciones por disciplina
- Cada sección contiene ítems con descripción, cantidad, precio unitario y descuento
- Totales calculados automáticamente por sección y general
- Cargar ítems predefinidos por disciplina

### 4.5 Solicitudes de Pago

Gestión de pagos a proveedores vinculados a compromisos.

---

## 5. Seguridad Industrial

### 5.1 Permisos de Trabajo

Flujos de aprobación para trabajos de alto riesgo.

**Tipos de permisos disponibles:**
- LOCKOUT/TAGOUT (Bloqueo/Etiquetado)
- Espacio Confinado
- Trabajo en Alturas
- Trabajo en Caliente
- Excavaciones

#### Solicitar un permiso:

1. Ir a Seguridad → Permisos de Trabajo → Nuevo
2. Seleccionar tipo de permiso
3. Completar información del trabajo (ubicación, duración, personal)
4. Verificar requisitos por tipo de permiso
5. Enviar a aprobación del área de seguridad

### 5.2 Análisis de Seguridad en el Trabajo (AST)

Identificación proactiva de peligros por actividad.

- Definir los pasos del trabajo
- Identificar riesgos por cada paso
- Establecer controles de mitigación
- Documentar equipo de protección requerido

### 5.3 Inspecciones de Seguridad

- Checklists configurables por tipo de inspección
- Registro con evidencia fotográfica
- Seguimiento de hallazgos y acciones correctivas

### 5.4 Equipos de Protección Personal (EPP)

- Control de asignación a cada trabajador
- Registro de vida útil y fechas de vencimiento
- Alertas de reemplazo

### 5.5 Incidentes

Registro y seguimiento de incidentes de seguridad:
- Tipo de incidente
- Descripción y circunstancias
- Personal involucrado
- Acciones correctivas

---

## 6. Inventarios y Almacén

### 6.1 Catálogo de Materiales

**Acceso**: Menú lateral → Inventarios → Materiales

- Búsqueda por código, nombre o categoría
- Ficha de material con especificaciones y compatibilidades
- Precio estimado y proveedores

### 6.2 Control de Stock

- Vista multi-almacén con stock por ubicación
- Niveles mínimos y máximos configurables
- Alertas de reabastecimiento

### 6.3 Movimientos de Inventario

| Tipo | Descripción |
|------|-------------|
| Entrada | Recepción de material de proveedor |
| Salida | Consumo en orden de trabajo o despacho |
| Transferencia | Movimiento entre almacenes |

### 6.4 Rack 3D (Visualización de Almacén)

Vista tridimensional de los racks del almacén que muestra:

- Materiales apilados con dimensiones reales (ancho × alto × profundidad)
- Código de colores por tipo de material
- Indicador de desbordamiento cuando el material excede la capacidad de la celda
- Interacción: hover para resaltar, clic para detalle

#### Asignar material a una posición:

1. Hacer clic derecho en una celda vacía del rack
2. Seleccionar "Asignar Material"
3. Buscar el material por código o nombre
4. Ingresar cantidad y dimensiones (si no están registradas)
5. Confirmar asignación

### 6.5 Solicitudes de Material

- Los técnicos pueden solicitar materiales desde campo
- Aprobación por jefe de almacén
- Despacho con registro de trazabilidad

---

## 7. Proyectos

### 7.1 Vista General de Proyectos

**Acceso**: Menú lateral → Proyectos

Cada proyecto incluye:
- Código automático (PROY-AAAA-NNNN)
- Responsable asignado
- Fechas de inicio y fin planificadas
- Estado (Planificación, En Ejecución, Completado, Suspendido)

### 7.2 Detalle del Proyecto

La vista de detalle se organiza en pestañas:

| Pestaña | Contenido |
|---------|-----------|
| General | Información básica, responsable, fechas |
| Cronograma / Actividades | Tabla de actividades con Gantt |
| Tareas (Kanban) | Tablero visual drag & drop |
| Documentos | Documentos vinculados al proyecto |
| Planos PDF | Planos técnicos con visor interactivo |
| Observaciones | Hallazgos y observaciones de campo |
| Órdenes de Trabajo | OTs vinculadas al proyecto |

### 7.3 Tablero Kanban de Tareas

Gestión visual de actividades con 4 columnas:

| Columna | Estado |
|---------|--------|
| Pendiente | Tareas por iniciar |
| En Progreso | Tareas en ejecución |
| Completada | Tareas terminadas |
| Bloqueada | Tareas con impedimentos |

#### Operaciones disponibles:

- **Arrastrar y soltar**: Mover tarjetas entre columnas para cambiar estado
- **Crear tarea**: Clic en "+ Agregar Tarea" en cualquier columna
- **Editar**: Clic en la tarjeta para abrir panel de edición
- **Filtrar**: Por responsable y/o prioridad
- **Eliminar**: Desde el panel de edición

### 7.4 Planos PDF del Proyecto

#### Subir un plano:

1. Ir a la pestaña "Planos PDF"
2. Arrastrar el archivo PDF al área de dropzone (o hacer clic para seleccionar)
3. Ingresar título y descripción opcional
4. Confirmar carga

#### Visor de Planos con Pines:

- Visualización PDF con zoom y navegación por páginas
- **Agregar pin**: Clic derecho en el plano → "Agregar Pin de Observación"
- **Seleccionar observación**: Elegir una observación existente o crear una nueva
- **Crear observación inline**: Toggle "Nueva observación" → Ingresar texto y documento vinculado
- **Ver detalle del pin**: Clic en el pin para ver la observación completa
- **Fotos en pines**: Adjuntar hasta 5 fotos por pin de observación
- **Áreas**: Definir zonas rectangulares sobre el plano para agrupar pines

### 7.5 Chatbot de Proyecto

Asistente con IA (Gemini) para consultar información del proyecto de forma conversacional.

---

## 8. Gestión Documental

### 8.1 Repositorio de Documentos

**Acceso**: Menú lateral → Documentos

Cada documento tiene:
- Código único de identificación
- Título y tipo de documento
- Disciplina asociada
- Estado (Borrador, En Revisión, Aprobado, Vigente)
- Historial de revisiones

### 8.2 Control de Revisiones

- Cada carga de archivo genera una nueva revisión
- Se conserva el historial completo con fecha, usuario y archivo
- Almacenamiento seguro en MinIO/S3

### 8.3 Visor de PDF con Comentarios

- Abre documentos PDF directamente en el navegador
- Agrega pines/comentarios en coordenadas específicas del documento
- Los comentarios quedan asociados a página y posición

### 8.4 Búsqueda Inteligente

- Búsqueda por código, título o contenido del PDF
- Búsqueda con Inteligencia Artificial (integración con n8n)
- Chat con IA para preguntas sobre documentos técnicos

### 8.5 Firmas Electrónicas

- Perfiles de firma por usuario
- Flujo de firmas requeridas por documento
- Auditoría completa de todas las firmas realizadas

### 8.6 Metadatos Personalizados

- Campos dinámicos configurables por tipo de documento
- Facilitan la clasificación y búsqueda avanzada

---

## 9. Comunicaciones y Transmittals

### 9.1 Tipos de Comunicados

| Tipo | Uso |
|------|-----|
| RFI | Solicitud de información |
| MEMO | Memorando interno |
| Transmittal | Envío formal de documentación técnica |

### 9.2 Crear un Comunicado

1. Ir a Comunicaciones → Nuevo Comunicado
2. Seleccionar tipo (RFI, MEMO, Transmittal)
3. Agregar destinatarios
4. Redactar contenido
5. Adjuntar documentos o activos
6. Enviar (cambia de BORRADOR a ENVIADO)

### 9.3 Bandeja de Entrada

- Lista de comunicados recibidos
- Seguimiento de lectura por destinatario
- Hilos de conversación (respuestas encadenadas)

---

## 10. Call Center / Tickets

### 10.1 Levantar un Ticket

**Acceso**: Menú lateral → Call Center → Nuevo Ticket

1. Describir la falla o necesidad
2. Indicar la ubicación o equipo afectado
3. Seleccionar prioridad
4. Enviar

El sistema asigna un consecutivo automático y monitorea tiempos de respuesta (SLA).

### 10.2 Seguimiento

- Estado del ticket (Abierto, En Proceso, Resuelto, Cerrado)
- Historial de acciones y comentarios
- Tiempo transcurrido vs. SLA comprometido

---

## 11. Servicios y KPIs

### 11.1 Indicadores de Rendimiento

Tableros de control para medir:
- Disponibilidad de equipos
- Confiabilidad operativa
- Costos de mantenimiento
- Cumplimiento del cronograma preventivo

### 11.2 Reportes

- Generación de informes ejecutivos en PDF y Excel
- Filtros por período, ubicación y disciplina
- Gráficas interactivas

---

## 12. Auditorías

### 12.1 Inventario Ciego de Activos

Proceso de verificación física:

1. Iniciar auditoría (asignar alcance y auditores)
2. Recorrer la planta escaneando códigos QR/RFID de equipos
3. Registrar hallazgos (equipos encontrados, faltantes, nuevos)
4. Conciliación automática contra el sistema
5. Generar reporte de discrepancias

### 12.2 Scanner QR/RFID

- Identificación rápida de equipos en campo
- Compatible con dispositivos móviles
- Registro en tiempo real durante la auditoría

---

## 13. Administración de Usuarios

### 13.1 Invitación de Usuarios

El sistema permite invitar nuevos usuarios por correo electrónico:

1. El administrador ingresa email y nombre de usuario
2. Se envía un enlace de invitación (válido por 72 horas)
3. El invitado completa su registro (nombre, contraseña)
4. El usuario queda activo en el sistema

### 13.2 Permisos y Grupos

- Los permisos se gestionan por grupos de Django
- Cada módulo tiene permisos granulares (ver, crear, editar, eliminar)
- El perfil del usuario incluye ubicación por defecto y jefe directo

---

## 14. Notificaciones

- **Push notifications**: Alertas en el navegador para eventos importantes
- **Notificaciones internas**: Asociadas a comunicados y tareas asignadas
- **Integración WhatsApp**: Notificaciones por WhatsApp para eventos críticos

---

## 15. Integraciones Externas

| Sistema | Función |
|---------|---------|
| Microsoft Dynamics 365 | Sincronización de requisiciones y compras |
| Power Automate | Envío de correos de invitación y notificaciones |
| n8n | Flujos de IA, extracción de metadatos, vectorización |
| MinIO/S3 | Almacenamiento de documentos y archivos |
| Google Gemini | Chatbot inteligente en proyectos |
| Mayan EDMS | Integración documental legacy |

---

## 16. Acceso Móvil

El sistema incluye interfaces optimizadas para dispositivos móviles:

- **Dashboard móvil**: Resumen de indicadores y accesos rápidos
- **Scanner QR**: Identificación de activos con la cámara
- **Carrito de técnico**: Solicitud de materiales desde campo
- **Detalle de activo móvil**: Ficha simplificada del equipo
- **Ubicaciones móviles**: Navegación del árbol de ubicaciones

---

## 17. Importación y Exportación de Datos

### Importaciones disponibles:

| Dato | Formato | Notas |
|------|---------|-------|
| Rutinas de mantenimiento | CSV/Excel | Procesamiento asíncrono con Celery |
| Ubicaciones técnicas | CSV/Excel | Estructura jerárquica |
| Activos | Excel | Validación de integridad |
| Requisiciones | Dynamics 365 | Sincronización automática |
| Materiales | Excel | Con categorías y precios |
| Consumos energéticos | Excel | Datos de medidores |

### Exportaciones:

- Reportes en PDF y Excel desde cada módulo
- Exportación de datos tabulares con filtros aplicados

---

## 18. Preguntas Frecuentes (FAQ)

**¿Cómo cambio mi contraseña?**
Ir al menú de usuario (esquina superior derecha) → Cambiar contraseña.

**¿Qué hago si una OT no aparece en el cronograma?**
Verifica que la rutina asociada tenga una programación activa y que las fechas correspondan al período visualizado.

**¿Cómo agrego un documento a un proyecto?**
Desde el detalle del proyecto → pestaña "Documentos" → buscar y vincular un documento existente del repositorio.

**¿Puedo subir archivos que no sean PDF?**
Para planos de proyecto, solo se aceptan archivos PDF (máximo 50 MB). Para documentos generales y adjuntos, se aceptan múltiples formatos según el módulo.

**¿Cómo funciona la búsqueda con IA?**
El sistema vectoriza el contenido de los documentos PDF. Al buscar, la IA encuentra los fragmentos más relevantes semánticamente, incluso si no contienen las palabras exactas de tu búsqueda.

**¿Qué pasa si el enlace de invitación expira?**
El administrador puede reenviar la invitación desde el panel de administración. Se genera un nuevo enlace válido por 72 horas.

**¿Cómo sé si un material excede la capacidad del rack?**
En la vista 3D del rack, las celdas con desbordamiento muestran un borde rojo pulsante y el porcentaje de exceso en el tooltip.

---

## 19. Requisitos del Sistema

| Componente | Requisito |
|------------|-----------|
| Navegador | Chrome 90+, Edge 90+, Firefox 88+ |
| Resolución | 1280×720 mínimo (recomendado 1920×1080) |
| Red | Conexión a internet estable |
| Móvil | Android 10+ / iOS 14+ (para funciones móviles) |
| Cámara | Requerida para scanner QR |

---

## 20. Soporte Técnico

Para reportar problemas o solicitar ayuda:

1. **Call Center interno**: Levantar un ticket desde el módulo de Call Center
2. **Administrador del sistema**: Contactar al área de TI de la planta
3. **Documentación técnica**: Consultar `SYSTEM_DOCUMENTATION.md` para detalles de arquitectura

---

*Versión del manual: 1.0 — Julio 2026*
*Sistema: Energy (SoftCom-CCG) — Django 5.1+*
