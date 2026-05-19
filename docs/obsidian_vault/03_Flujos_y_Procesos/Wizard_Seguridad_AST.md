# 🛡️ Wizard de Permisos de Trabajo & AST

El Análisis de Seguridad en el Trabajo (AST) es obligatorio para realizar mantenimientos críticos en la planta. Para simplificar esta tarea, se diseñó un **Wizard Multiaso dinámico** integrado en el módulo de seguridad.

## 🗺️ Diagrama del Flujo del Permiso de Trabajo

```mermaid
graph TD
    classDef step fill:#1e1e2e,stroke:#f5c2e7,stroke-width:1px,color:#cdd6f4;
    classDef approved fill:#a6e3a1,stroke:#a6e3a1,stroke-width:1px,color:#11111b;

    S1[Paso 1: Información General y Activo] --> S2[Paso 2: Identificar Riesgos]
    S2 --> S3[Paso 3: Definir Controles de Mitigación]
    S3 --> S4[Paso 4: Asignar Requisitos de Permiso]
    S4 --> S5[Paso 5: Firmas y Envío]
    
    S5 --> APROV{Flujo de Aprobación}
    
    APROV -->|Firma Supervisor| A[Habilitado / Permiso Activo]
    APROV -->|Rechazado| R[Borrador / Requiere Edición]
    
    class S1,S2,S3,S4,S5 step;
    class A approved;
```

## ⚙️ Características Técnicas

1. **Persistencia del Borrador**: Los pasos del formulario se envían y persisten asíncronamente en el modelo `PermisoTrabajo` con el estado `BORRADOR`. Si el técnico en campo pierde la conexión, la información no se pierde.
2. **Catálogos Dinámicos**: Los riesgos y sus controles correspondientes se cargan automáticamente desde los catálogos estandarizados (`Riesgo` y `Control`) en base al tipo de actividad, evitando la digitación manual y errores ortográficos.
3. **Firmas Digitales Cruzadas**: El sistema requiere la firma digital electrónica del técnico ejecutor y la del supervisor responsable. Las firmas se validan mediante perfiles encriptados y se plasman en el documento PDF final guardado en MinIO.
4. **Validación Bypass en Cliente**: Para garantizar la resiliencia en dispositivos móviles, se implementó validación personalizada por paso en JavaScript, evitando conflictos con validaciones nativas de HTML5 en navegadores móviles integrados.

---
🔙 Volver a [[00_Inicio|Inicio]]
