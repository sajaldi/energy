# Plan de Implementación: Sistema de Gestión Documental (EDMS)

Este plan describe la arquitectura para implementar un sistema de gestión documental robusto inspirado en Aconex/Dynamics 365, dentro del entorno Django existente.

## Objetivo
Centralizar la información técnica (planos, manuales, fichas) con un control estricto de versiones, trazabilidad y metadatos estructurados.

## User Review Required
> [!IMPORTANT]
> **Modelo de Versionado:** Se propone usar un modelo de "Documento Maestro" + "Revisiones Históricas". El registro principal (`Documento`) siempre apuntará a la información más reciente, mientras que `Revision` almacenará el historial inmutable.
> ¿Está de acuerdo con este enfoque o prefiere que cada revisión sea un registro independiente desde el inicio?

## Proposed Changes

### App: `documentos` [NEW]

Se creará una nueva aplicación Django para aislar esta lógica compleja.

#### [NEW] [models.py](file:///d:/Apps/energia/energy/documentos/models.py)

1.  **`Carpeta` (Opcional/Futuro)**: Estructura de árbol para organizar documentos (simular sistema de archivos).
2.  **`Documento` (Maestro)**:
    *   `codigo`: CharField, Unique (Ej: 'CCG-I-T1-IAA-07-02').
    *   `titulo`: CharField.
    *   `tipo`: ForeignKey (Plano, Manual, Procedimiento, etc.).
    *   `disciplina`: ForeignKey.
    *   `estado_actual`: (Borrador, Revisión, Aprobado).
    *   `ultima_revision`: Enlace a la revisión vigente.
    *   `activos`: ManyToMany con `Activo`.
    *   `ubicaciones`: ManyToMany con `Ubicacion`.
3.  **`Revision` (Histórico)**:
    *   `documento`: FK a `Documento`.
    *   `archivo`: FileField (con ruta dinámica `/docs/Y/M/`).
    *   `revision`: CharField (0, 1, A, B...).
    *   `fecha_revision`: Date.
    *   `creado_por`: User.
    *   `comentarios`: TextField.
    *   `hash`: CharField (MD5 para integridad).

### Admin: Interfaz de Usuario

Se personalizará fuertemente el admin para `Documento`:
*   **List Display:** Código, Título, Revisión Actual, Estado, Acciones Rápidas (Ver PDF).
*   **Filtros (Faceted):** Por Disciplina, Tipo, Estado.
*   **Inline:** Lista de Revisiones anteriores en modo solo lectura.
*   **Acciones:** "Crear Nueva Revisión" (transición de estado y archivo).

### Core: Integración

*   **Visor de PDF:** Reutilizar el visor existente para previsualizar documentos directamente desde la lista o detalle.

## Verification Plan

### Automated Tests
*   **Test Modelos:** Verificar que al crear una nueva revisión, se actualice el puntero `ultima_revision` del documento maestro.
*   **Test Unicidad:** Intentar crear dos documentos con el mismo código (debe fallar).
*   **Test Integridad:** Verificar cálculo de hash al subir archivo.

### App: `comunicaciones` [NEW]

Módulo para correspondencia oficial (tipo Aconex Mail).

#### [NEW] [models.py](file:///d:/Apps/energia/energy/comunicaciones/models.py)

1.  **`TipoComunicado`**:
    *   `nombre`: (RFI, Transmittal, Instrucción, Memo).
    *   `codigo`: Prefijo para el consecutivo (ej: RFI, TRN).
2.  **`Comunicado`**:
    *   `consecutivo`: CharField único generado auto (ej: RFI-001-2025).
    *   `asunto`: CharField.
    *   `cuerpo`: TextField (HTML).
    *   `remitente`: User (Creador).
    *   `fecha_envio`: DateTime.
    *   `estado`: (Borrador, Enviado). Una vez enviado, es inmutable.
    *   `parent`: FK a `self` (para hilos de respuesta).
3.  **`Destinatario`**:
    *   `comunicado`: FK.
    *   `usuario`: FK User.
    *   `tipo`: (PARA, CC, CCO).
    *   `leido`: Boolean / FechaLeido (Tracking).
4.  **`AdjuntoComunicado`**:
    *   `comunicado`: FK.
    *   `documento_revision`: FK a `documentos.Revision` (Transmittals).
    *   `archivo`: FileField (Adjuntos ad-hoc).

### Módulo de Notificaciones [NEW]

Sistema para alertar a los usuarios sobre nueva correspondencia.

#### Lógica de Notificación
1. **Interna (DB):** Se creará un modelo `Notificacion` para mostrar en la interfaz.
2. **Email:** Se enviará un correo automático a cada `Destinatario` (PARA y CC) cuando el `Comunicado` cambie a `ENVIADO`.

#### [NEW] [models.py](file:///d:/Apps/energia\energy\comunicaciones\models.py) (Extensión)
* **`Notificacion`**:
    * `usuario`: FK User.
    * `comunicado`: FK Comunicado.
    * `leida`: Boolean.
    * `fecha_creacion`: DateTime.

#### Automatización (Signals)
* Se implementará un `post_save` signal en `Comunicado`.
* Si `estado == 'ENVIADO'`, generar registros en `Notificacion` para todos los destinatarios vinculados.
* Ejecutar tarea de Celery (opcional) para el envío de mails si la carga es alta.

### Manual Verification
1.  Crear un Documento "Plano Eléctrico" Rev A.
2.  Subir nueva versión (Rev 0).
3.  Verificar que el listado muestra Rev 0 pero el historial conserva Rev A.
4.  Comprobar que se puede vincular a un Activo existente.
5.  Crear y enviar un comunicado tipo RFI. Verificar inmutabilidad tras envío.
6.  Validar que los destinatarios reciban una notificación (interna/email).

