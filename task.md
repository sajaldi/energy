# Tareas: Sistema de Gestión Documental (EDMS - Tipo Aconex)

## Fase 1: Fundamentos y Modelado de Datos
- [x] **Diseño del Esquema de Datos**
    - [x] `Documento`: Entidad principal con metadatos fijos (Código, Título, Autor).
    - [x] `Revision`: Versiones del documento (Archivo, Versión, Estado, Fecha).
    - [x] `Metadatos`: Tablas auxiliares (TipoDocumento, Disciplina, Status).
- [x] **Configuración de la App**
    - [x] Crear app `documentos`.
    - [x] Definir modelos y relaciones.
    - [x] Configurar Admin de Django (usando la nueva toolbar).

## Fase 2: Lógica de Negocio y Control
- [x] **Control de Versiones y Numeración**
    - [x] Lógica para autoincremento de revisiones (A -> B -> 0 -> 1).
    - [x] Validación de unicidad de Códigos de Documento.
- [x] **Almacenamiento y Seguridad**
    - [x] Configurar ruta de subida organizada (`/media/docs/{proyecto}/{disciplina}`).
    - [x] Hash de archivos (MD5/SHA) para integridad.
- [x] **Integración**
    - [x] Relación con `Ubicacion` y `Activo` (Many-to-Many).

## Fase 3: Interfaz de Usuario (Admin & Visor)
- [x] **Vistas del Admin**
    - [x] Listado con filtros avanzados (Faceted Search similar a Aconex).
    - [x] Acciones masivas (Descargar zip, Transmitir).
- [x] **Visualización**
    - [x] Integración con el visor de PDF existente.

# Sistema de Comunicaciones (mail/Transmittals)
## Fase 4: Correspondencia Formal (Tipo Aconex)
- [x] **Arquitectura y Modelos**
    - [x] Crear app `comunicaciones`.
    - [x] Modelo `TipoComunicado` (RFI, Transmittal, Memo).
    - [x] Modelo `Comunicado` (Asunto, Cuerpo, Consecutivo Auto-generado, Inmutabilidad).
    - [x] Modelo `Destinatario` (Para, CC, CCO, Acuse de Recibo).
- [x] **Funcionalidad de Transmittals**
    - [x] Integración con `documentos`: Adjuntar Revisiones específicas a un Comunicado.
- [x] **Interfaz de Inbox (Admin)**
    - [x] Vistas personalizadas: "Bandeja de Entrada" (recibidos) y "Enviados".
    - [x] Filtros por tipo (RFI pendintes, etc).
    - [x] Acción de "Enviar" (hacer inmutable y generar consecutivo).

## Fase 5: Notificaciones e Inbox
- [x] **Lógica de Envío**
    - [x] Configurar signals para disparar notificaciones al enviar comunicado.
    - [x] Modelo `Notificacion` para bandeja de entrada interna.
- [x] **Integración Email**
    - [x] Configurar envío de correos electrónicos básicos (Consola).
- [x] **Lógica de Respuestas**
    - [x] Botón "Responder" con pre-llenado de asunto y parent.

# Módulo de Mantenimiento Proactivo
## Fase 6: Planificación Mensual
- [x] **Modelado de Planificación**
    - [x] Crear modelo `PlanificacionMensual` (Mes, Año, Estado).
    - [x] Relacionar con `OrdenTrabajo`.
- [x] **Lógica de Generación de Plan**
    - [x] Acción para "Poblar Plan" basado en programaciones vigentes.
- [x] **Refinamiento de Generación de OTs**
    - [x] Implementar expansión automática de áreas (descendientes/niveles).
    - [x] Agregar campo `orden` a Ubicaciones para secuencia personalizada.
    - [x] Asegurar secuencialidad back-to-back basada en `tiempo_estimado`.
    - [x] Validar que el total de tareas quepa en el plazo de la frecuencia.
- [x] **Optimización de Importación, Eliminación y Exportación**
    - [x] Desactivar actualizaciones de MPTT durante carga masiva y reconstruir al final.
    - [x] Optimizar eliminación masiva en el admin (borrado en bloque + reconstrucción única).
    - [x] Eliminar problema N+1 en exportación mediante caché de rutas en memoria.
    - [x] Habilitar operaciones en bloque (bulk) para carga de datos.
- [x] **Optimización de Rendimiento Global**
    - [x] Agregar índices a `Activo`, `OrdenTrabajo` y `Aviso`.
    - [x] Optimizar admin con `select_related` y `autocomplete_fields` generales.
    - [x] Configurar `CONN_MAX_AGE` para mitigar latencia de BD remota.
    - [x] Eliminar consultas N+1 en conteos de activos y órdenes de trabajo.

# Infraestructura y Rendimiento
## Fase 8: Eliminación de MPTT y Simplificación
- [x] **Limpieza de Modelos**
    - [x] Remover `MPTTModel` de `Ubicacion`.
    - [x] Remover `MPTTModel` de `Categoria`.
- [x] **Actualización de Admin**
    - [x] Cambiar `DraggableMPTTAdmin` por `admin.ModelAdmin` estándar.
    - [x] Simplificar `UbicacionResource` y `CategoriaResource`.
    - [x] Implementar caching en `before_import` para evitar N+1 queries.
- [x] **Configuración Global**
    - [x] Eliminar `mptt` de `settings.py`.
- [x] **Migración de Datos**
    - [x] Generar y aplicar migraciones para remover campos `lft`, `rght`, `tree_id`, `level`.
- [x] **Optimización Extra de Importación**
    - [x] Habilitar `use_bulk=True` en todos los recursos (Activo, Consumo, Rutina, etc).
    - [x] Implementar `ActivoResource` con precarga de FKs.
- [x] Corregir `AttributeError` en Calendario de Mantenimiento (reemplazar `get_root`).

# Experiencia de Usuario (UX)
## Fase 7: Onboarding y Tutorial de Bienvenida
- [x] **Modelo de Perfil**
    - [x] Crear modelo `PerfilUsuario` con flag `visto_tutorial`.
- [x] **Tutorial Interactivo (JS)**
    - [x] Integrar librería de tour (Intro.js).
    - [x] Crear guión del tutorial (Dashboard, Documentos, Comunicaciones).
- [x] **Lógica de Activación**
    - [x] Inyectar JS condicionalmente si el usuario es nuevo.

> [!TIP]
> Consulta [walkthrough_optimizacion.md](file:///C:/Users/Saul/.gemini/antigravity/brain/9b90c12b-d0ed-40f8-8d1b-9daaeba5c1cf/walkthrough_optimizacion.md) para ver los detalles de las mejoras de rendimiento.
