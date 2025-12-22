# Sistema de Gestión Documental (EDMS) - Guía de Uso

Esta guía describe cómo utilizar el nuevo sistema de documentación técnica inspirado en Aconex.

## 1. Configuración Inicial (Metadatos)
Antes de subir documentos, debes definir los catálogos base en el Admin > Documentos:

1.  **Disciplinas**:
    *   Ej: `Arquitectura (ARQ)`, `Eléctrico (ELE)`, `Mecánico (MEC)`.
2.  **Tipos de Documento**:
    *   Ej: `Plano (PLN)`, `Manual (MNL)`, `Procedimiento (PRO)`.

## 2. Crear un Documento (Flujo Maestro)
El "Documento" es el contenedor principal.

1.  Ve a **Documentos > Documentos**.
2.  Clic en **+ Agregar Documento**.
3.  **Identificación**:
    *   Código: `CCG-I-T1-ARQ-01` (Debe ser único).
    *   Título: `Plano Arquitectónico Nivel 1`.
    *   Tipo/Disciplina: Selecciona los creados anteriormente.
4.  **Estado**:
    *   Estado Actual: `Borrador`.
5.  **Relaciones**:
    *   Vincula Activos o Ubicaciones si corresponde.
6.  Clic en **Guardar y continuar editando**.

## 3. Subir una Revisión (Flujo de Archivos)
Una vez creado el contenedor, subimos el archivo real (la revisión).

1.  En la misma pantalla de edición del Documento, baja a la sección **Revisiones**.
2.  Clic en **Agregar otro Revisión**.
3.  Completa:
    *   **Revisión**: `A` (o `0`, `B`, etc).
    *   **Archivo**: Selecciona tu PDF.
    *   **Comentarios**: "Emisión inicial para revisión interna".
    *   **Creado por**: Tu usuario.
4.  Clic en **Guardar**.

## 4. Resultado
*   El sistema actualizará automáticamente el campo **"Última Revisión"** en el documento maestro.
*   En el listado principal, verás el documento mostrando "Rev A" y su fecha.
*   El archivo físico se guarda en `/media/docs/{año}/{mes}/{codigo}/`.

## Próximos Pasos (Fase 2)
*   Implementaremos lógica para que la revisión se calcule automáticamente (A -> B).
*   Validaciones de unicidad y hashes para evitar duplicados.
