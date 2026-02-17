# Documentación de Módulos del Sistema SoftCom-CCG

Sistema integral de gestión empresarial desarrollado en Django para la empresa CCG (planta de energía). A continuación se describen todos los módulos disponibles.

---

## 1. Core (Núcleo del Sistema)

**Propósito**: Núcleo del sistema con configuraciones globales y utilidades compartidas.

### Modelos Principales

| Modelo | Descripción |
|--------|-------------|
| Medidor | Gestión de medidores de consumo energético |
| Consumo | Registro de consumo energético |
| InterfaceConsumo | Tabla de staging para importación de datos de consumo |
| TipoMedidor | Catálogo de tipos de medidores |
| UnidadMedida | Catálogo de unidades de medida |
| PuntoMedicion | Puntos de medición técnica |
| DocumentoMedicion | Documentación asociada a mediciones |
| RangoMedicion | Rangos válidos para mediciones |
| Equipo | Equipos técnicos |
| UbicacionTecnica | Ubicaciones técnicas de equipos |
| KPI | Indicadores de rendimiento |
| Servicio | Servicios del sistema |
| PerfilUsuario | Perfiles extendidos de usuarios (ubicación por defecto, jefe directo) |

### Funcionalidades

- Importación de datos de consumo desde Excel
- Reportes de consumo mensual y diario
- Dashboard móvil
- Resolvedor QR

---

## 2. Documentos (Gestión Documental)

**Propósito**: Sistema integral de gestión documental con control de revisiones, comentarios/pines en PDFs y firmas electrónicas.

### Modelos Principales

| Modelo | Descripción |
|--------|-------------|
| Documento | Entidad maestra con código único, título, estado y relación con activos/ubicaciones |
| Revision | Historial de revisiones/cargas de archivos (almacenamiento en MinIO/S3) |
| TipoDocumento | Catálogo de tipos de documento |
| Disciplina | Disciplinas para clasificación de documentos |
| MetadatoConfig | Configuración de campos dinámicos personalizados |
| MetadatoValor | Valores de metadatos personalizados |
| ComentarioDocumento | Pines y comentarios sobre PDFs con posicionamiento (x, y, página) |
| N8nChatHistory | Historial de conversaciones con IA |
| MayanDocumentLink | Integración con Mayan EDMS |

### Modelos de Firmas

| Modelo | Descripción |
|--------|-------------|
| PerfilFirma | Perfiles de firma electrónica |
| DocumentoFirmado | Documentos firmados electrónicamente |
| FirmaRequerida | Firmas requeridas por documento |
| Firma | Registro de firmas realizadas |
| AuditoriaFirmas | Auditoría de todas las firmas |

### Funcionalidades

- Trazabilidad completa de documentos
- Visor de pines y comentarios en PDFs
- Búsqueda avanzada por código, título y contenido de PDF
- Búsqueda con inteligencia artificial
- Proxy de PDF para visualización
- Chat con IA (integración con n8n)

---

## 3. Comunicaciones (Comunicados y Transmittals)

**Propósito**: Sistema de comunicación interna estilo email/transmittals para envío formal de documentos y activos.

### Modelos Principales

| Modelo | Descripción |
|--------|-------------|
| Comunicado | Mensajes con consecutivos automáticos, estados (BORRADOR/ENVIADO) e hilos |
| TipoComunicado | Tipos de comunicados (RFI, MEMO, Transmittal) |
| Destinatario | Destinatarios con seguimiento de lectura |
| AdjuntoComunicado | Adjuntos (documentos, archivos o activos) |
| Notificacion | Notificaciones internas asociadas a comunicados |

### Funcionalidades

- API de creación de transmittals
- Lista de transmittals enviados y recibidos
- Detalle de transmittal con historial

---

## 4. Proyectos (Gestión de Proyectos)

**Propósito**: Planificación y seguimiento de proyectos con actividades, cronogramas y diagramas Gantt.

### Modelos Principales

| Modelo | Descripción |
|--------|-------------|
| Proyecto | Proyectos con código automático (PROY-AAAA-NNNN), estados, fechas y responsable |
| Actividad | Actividades con dependencias (predecesoras), prioridades, estados y ubicación en planos |
| DocumentoProyecto | Relación muchos-a-muchos entre proyectos y documentos |

### Funcionalidades

- API de creación y actualización de actividades
- Cronograma visual
- Diagrama Gantt
- Chatbot asistente con IA (Gemini)

---

## 5. Activos (Gestión de Activos)

**Propósito**: Administración completa del inventario de activos/equipos con ubicación jerárquica, planos y medición.

### Modelos Principales

| Modelo | Descripción |
|--------|-------------|
| Activo | Entidad principal con código interno, EPC, serie, estado, responsable y ubicación |
| Marca | Catálogo de marcas de equipos |
| Modelo | Catálogo de modelos de equipos |
| Categoria | Clasificación jerárquica de activos |
| Familia | Familias de activos |
| Ubicacion | Jerarquía de ubicaciones (árbol padre/hijo) con tipos y orden |
| Plano | Planos técnicos asociados a ubicaciones |
| VisorPlano | Configuración de visualizadores de planos |
| PinPlano | Pines geolocalizados en planos |
| PinFoto | Pines fotográficos en planos |
| PuntoMedicion | Puntos de medición técnica |
| DocumentoMedicion | Documentación de mediciones |
| BienAfecto | Bienes asegurados |
| HistorialBienAfecto | Historial de estados de bienes afectados |
| RegistroImportacion | Tracking de importaciones de activos |

### Funcionalidades

- Visor de planos interactivos
- Explorador jerárquico de activos (vista de árbol)
- API de búsqueda de activos
- Edición de activos
- Dashboard móvil
- Scanner QR
- Detalles de activo para móvil
- Ubicaciones móviles

---

## 6. Mantenimiento (Gestión de Mantenimiento)

**Propósito**: Sistema completo de mantenimiento preventivo y correctivo (CMMS).

### Modelos Principales

| Modelo | Descripción |
|--------|-------------|
| Categoria | Categorías de rutinas de mantenimiento |
| Frecuencia | Frecuencias de ejecución de rutinas |
| Rutina | Plantillas de mantenimiento preventivo |
| Procedimiento | Manual de procedimientos |
| PasoProcedimiento | Pasos con tipos de respuesta (check, numérico, texto, medición) |
| Programacion | Programación de rutinas con generación automática de órdenes |
| OrdenTrabajo | Órdenes de trabajo preventivas y correctivas |
| CierreOrdenTrabajo | Cierre técnico con horas hombre y materiales |
| Aviso | Solicitudes de mantenimiento (M1 - Servicio, M2 - Avería) |
| Falla | Catálogo de fallas jerárquico |
| TecnicoPuesto | Técnicos asignados a puestos |
| PuestoTrabajo | Puestos de trabajo |
| Empresa | Empresas de mantenimiento externo |
| Horario | Horarios de trabajo |
| ValorPasoOrden | Resultados del checklist/ejecución |
| PlanificacionMensual | Planificación mensual de mantenimiento |

---

## 7. Presupuestos (Gestión Presupuestaria)

**Propósito**: Control presupuestario con Cost Sheet, compromisos, gastos y requisiciones.

### Modelos Principales

| Modelo | Descripción |
|--------|-------------|
| PresupuestoAnual | Presupuesto anual por año y moneda |
| PartidaPresupuestaria | Partidas por disciplina con cálculos de presupuesto vigente, comprometido, gastado y disponible |
| CambioPresupuesto | Transferencias, adicionales y reducciones presupuestarias |
| Compromiso | Contratos y órdenes de compra |
| DetalleCompromiso | Detalles de compromisos |
| GastoEjecutado | Gastos/facturas registrados |
| ItemPresupuesto | Desglose de partidas |
| DetallePeriodico | Detalle con recurrencia mensual |
| PresupuestoAgrupado | Agrupación de presupuestos para vista gerencial |
| Requisicion | Requisiciones sincronizadas desde Dynamics 365 |
| ArticuloRequisicion | Artículos de requisición |
| DocumentoRequisicion | Documentos de requisición |
| SolicitudPago | Gestión de pagos |
| ItemSolicitudPago | Items de solicitud de pago |

### Funcionalidades

- Wizard de flujo de requisiciones
- Sincronización con Dynamics 365
- Vista gerencial de presupuestos agrupados

---

## 8. Inventarios (Gestión de Inventarios)

**Propósito**: Control de materiales, stock y movimientos de inventario.

### Modelos Principales

| Modelo | Descripción |
|--------|-------------|
| SolicitudMaterial | Solicitudes de material |
| CategoriaMaterial | Categorías de materiales |
| Material | Catálogo de materiales con precio estimado |
| CompatibilidadMaterial | Compatibilidades entre materiales |
| Lote | Control de lotes |
| StockRecord | Registro de stock por ubicación y proveedor |
| MovimientoInventario | Movimientos de entrada y salida |

---

## 9. Auditorías (Gestión de Auditorías)

**Propósito**: Registro y seguimiento de auditorías.

### Modelos Principales

| Modelo | Descripción |
|--------|-------------|
| Auditoria | Auditorías con fechas, tipo y estado |
| ResultadoAuditoria | Resultados de las auditorías |

---

## 10. Seguridad (Gestión de Seguridad Industrial)

**Propósito**: Sistema integral de seguridad industrial, permisos de trabajo y EPPs.

### Modelos Principales

| Modelo | Descripción |
|--------|-------------|
| TipoIncidente | Tipos de incidentes |
| Incidente | Registro de incidentes |
| TipoInspeccion | Tipos de inspección |
| ItemInspeccion | Ítems de inspección |
| Inspeccion | Inspecciones de seguridad |
| ResultadoInspeccion | Resultados de inspecciones |
| AsignacionEPP | Asignación de Equipo de Protección Personal |
| AnalisisRiesgo | Análisis de riesgos |
| Riesgo | Riesgos identificados |
| Control | Controles de mitigación |
| PasoTrabajo | Pasos de trabajo seguro |
| TipoPermiso | Tipos de permiso de trabajo |
| RequisitoPermiso | Requisitos por tipo de permiso |
| PermisoTrabajo | Permisos de trabajo (LOCKOUT/TAGOUT, Espacio Confinado, etc.) |
| VerificacionRequisito | Verificación de requisitos |

---

## 11. Callcenter (Centro de Llamadas / Tickets)

**Propósito**: Gestión de tickets y solicitudes con integración a sistemas externos (SIG).

### Modelos

- SolicitudTicket: Gestión de tickets de soporte

---

## 12. Servicios

**Propósito**: Módulo de servicios diversos.

---

## Aplicaciones de Terceros Integradas

| Paquete | Descripción |
|---------|-------------|
| jazzmin | Tema de admin personalizado para Django |
| import_export | Importación/exportación de datos (CSV, Excel) |
| django_celery_results | Resultados de tareas asíncronas (Celery) |
| colorfield | Campo de color para interfaces visuales |
| corsheaders | Configuración de CORS |
| django.contrib.humanize | Filtros de templates para números legibles |
| storages | Integración con almacenamiento S3/MinIO |

---

## Tecnologías y Patrones

- **Framework**: Django (Python)
- **Almacenamiento**: MinIO/S3 para documentos
- **Tareas asíncronas**: Celery
- **Integraciones**: Dynamics 365, Mayan EDMS, n8n (IA)
- **UI**: Admin de Django personalizado con Jazzmin, templates responsive
