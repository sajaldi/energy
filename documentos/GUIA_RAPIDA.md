# 📖 Guía Rápida: Cómo Usar el Sistema de Firmas

## 🎯 Pasos para Empezar a Firmar Documentos

### **Paso 1: Crear un Documento** 📄

1. **Ir al Admin de Django:**
   ```
   http://localhost:8000/admin/
   ```

2. **Buscar sección "DOCUMENTOS"** en el menú lateral izquierdo

3. **Clic en "Documentos"**

4. **Clic en el botón verde "AGREGAR DOCUMENTO"** (arriba a la derecha)

5. **Llenar el formulario:**

   ```
   ┌─────────────────────────────────────────┐
   │ Código:  [ENG-DOC-001____________]      │
   │                                         │
   │ Título:  [Plan de Mantenimiento_____]  │
   │                                         │
   │ Tipo:    [Seleccionar tipo ▼]          │
   │                                         │
   │ Estado:  [BORRADOR ▼]                  │
   └─────────────────────────────────────────┘
   ```

6. **En la sección "Revisiones"** (parte inferior):
   
   ```
   ┌─────────────── REVISIONES ─────────────┐
   │ Revisión:  [A]  o  [1]  o  [00]        │
   │ Archivo:   [Elegir archivo...]         │
   │ Fecha:     [26/12/2025]                │
   │ Comentarios: [Primera versión___]     │
   └─────────────────────────────────────────┘
   ```

7. **Guardar** (botón azul abajo)

---

### **Paso 2: Solicitar Firmas** 🖊️

**OPCIÓN A: Desde la lista de documentos (FÁCIL)**

1. **Ir a:** `http://localhost:8000/admin/documentos/documento/`

2. **Verás una tabla de documentos con una columna "Firmas"**

3. **Clic en el botón morado "🖊️ Solicitar Firmas"** en el documento que creaste

4. **Se abrirá la interfaz para agregar firmantes:**

   ```
   ┌────────────────────────────────────────────┐
   │  📄 Documento: ENG-DOC-001                 │
   │                                            │
   │  ➕ Agregar Firmante:                      │
   │  ┌──────────────────────────────────────┐  │
   │  │ Usuario: [Seleccionar usuario ▼]     │  │
   │  │ Rol:     [Elaboró____________]       │  │
   │  │ [➕ Agregar Firmante]                │  │
   │  └──────────────────────────────────────┘  │
   │                                            │
   │  Firmantes agregados:                      │
   │  ┌──────────────────────────────────────┐  │
   │  │ 1. Juan Pérez - Elaboró              │  │
   │  │ 2. Ana López - Revisó                │  │
   │  └──────────────────────────────────────┘  │
   │                                            │
   │  [💾 Guardar y Solicitar]                  │
   └────────────────────────────────────────────┘
   ```

5. **Selecciona un usuario de la lista**
6. **Escribe un rol** (ejemplo: "Elaboró", "Revisó", "Aprobó")
7. **Clic en "Agregar Firmante"**
8. **Repite para agregar más firmantes**
9. **Clic en "Guardar y Solicitar Firmas"**

**OPCIÓN B: Desde URL directa**

1. **Ir a:** `http://localhost:8000/firmas/solicitar/1/`
   
   (Donde `1` es el ID de tu documento. Puedes verlo en la lista de documentos)

---

### **Paso 3: Configurar Tu Firma Personal** ✍️

**ANTES de poder firmar, cada usuario debe configurar su firma:**

1. **Ir a:** `http://localhost:8000/firmas/perfil/`

2. **Elegir método de firma:**

   **Opción A: Firma Manuscrita**
   ```
   ┌────────────────────────────────┐
   │ ✍️ Firma Manuscrita            │
   ├────────────────────────────────┤
   │                                │
   │   [Canvas para dibujar]        │
   │   Dibuja con mouse o dedo      │
   │                                │
   │ [🗑️ Limpiar] [💾 Guardar]     │
   └────────────────────────────────┘
   ```

   **Opción B: Subir PNG**
   ```
   ┌────────────────────────────────┐
   │ 📤 Subir Imagen PNG            │
   ├────────────────────────────────┤
   │                                │
   │   📁 Arrastra tu imagen aquí   │
   │   o haz clic para seleccionar  │
   │                                │
   │ [Seleccionar Archivo]          │
   │ [💾 Guardar]                   │
   └────────────────────────────────┘
   ```

3. **Completar datos:**
   - Cargo: `Ingeniero`, `Gerente`, etc.
   - Departamento: `Ingeniería`, `Operaciones`, etc.

4. **Guardar**

---

### **Paso 4: Ver Documentos Pendientes** 📋

1. **Ir a:** `http://localhost:8000/firmas/por-firmar/`

2. **Verás lista de documentos asignados a ti:**

   ```
   ┌─────────────────────────────────────────┐
   │ 📄 ENG-DOC-001                          │
   │ Plan de Mantenimiento Anual             │
   │ Rol: Elaboró                            │
   │ [✍️ Firmar Ahora]  [👁️ Ver Documento] │
   └─────────────────────────────────────────┘
   ```

---

### **Paso 5: Firmar el Documento** ✅

1. **Clic en "Firmar Ahora"**

2. **Se abrirá el visor:**

   ```
   ┌──────────────────┬──────────────┐
   │  📄 DOCUMENTO    │  ✍️ TU FIRMA │
   │                  │              │
   │  [Vista del PDF] │  [Preview    │
   │                  │   de firma]  │
   │                  │              │
   │  ┌────┐          │  Posición:   │
   │  │📝  │ ← Arrastra│  X: 10%     │
   │  └────┘  tu firma │  Y: 80%     │
   │     aquí         │              │
   │                  │  Comentarios:│
   │                  │  [_________] │
   │                  │              │
   │                  │  [✅ Firmar] │
   └──────────────────┴──────────────┘
   ```

3. **Arrastra tu firma** con el mouse a donde quieras que aparezca
4. **Ajusta la posición** si es necesario
5. **Agrega comentarios** (opcional)
6. **Clic en "✅ Firmar Documento"**
7. **¡Listo!** Recibirás un token de verificación

---

## 🔍 Verificar una Firma

**Cualquier persona puede verificar la autenticidad:**

1. **Ir a:** `http://localhost:8000/firmas/verificar/<TOKEN>/`

   (El token es el que recibiste al firmar)

2. **Verás el certificado de autenticidad** con:
   - Nombre del firmante
   - Fecha y hora exacta
   - Hash del documento
   - Hash de la firma
   - Estado de integridad

---

## 📊 Ver Estado de Documentos Firmados

**Para administradores:**

1. **Ir a:** `http://localhost:8000/firmas/documentos/`

2. **Verás todos los documentos con:**
   - Estado (Pendiente, Parcial, Completo, Rechazado)
   - Progreso de firmas (ej: 2/3 firmas)
   - Lista de firmantes y su estado

---

## ❓ Preguntas Frecuentes

### ¿Dónde creo tipos de documento?

```
Admin → DOCUMENTOS → Tipos de Documento → Agregar
```

### ¿Cómo subo un archivo al documento?

En la sección "Revisiones" cuando creas/editas un documento.

### ¿Puedo cambiar mi firma después?

Sí, ve a `/firmas/perfil/` y sube/dibuja una nueva.

### ¿Qué pasa si rechazo un documento?

El documento se marca como "Rechazado" y se notifica al solicitante con tu motivo.

### ¿Puedo firmar sin configurar mi perfil?

No, debes configurar tu firma primero en `/firmas/perfil/`.

### ¿Los documentos deben ser PDF?

No, pueden ser cualquier formato (PDF, Word, Excel, imágenes, etc.).

---

## 🚀 Accesos Rápidos

```
👤 Mi Perfil de Firma:
   http://localhost:8000/firmas/perfil/

📋 Mis Pendientes:
   http://localhost:8000/firmas/por-firmar/

⚙️ Admin de Documentos:
   http://localhost:8000/admin/documentos/documento/

📊 Todos los Firmados:
   http://localhost:8000/firmas/documentos/

🔧 Panel Admin:
   http://localhost:8000/admin/
```

---

## 💡 Tips Importantes

1. **Primero crea el documento** en el admin
2. **Luego solicita firmas** desde la lista de documentos
3. **Los usuarios configuran su firma** en `/firmas/perfil/`
4. **Luego pueden firmar** desde `/firmas/por-firmar/`

---

¿Necesitas ayuda? Consulta:
- `README_FIRMAS.md` - Documentación completa
- `DIAGRAMAS.md` - Flujos visuales
- `ejemplos_firmas.py` - Ejemplos de código
