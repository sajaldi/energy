# 🎯 Resumen Rápido - Sistema de Firmas Electrónicas

## 🚀 URLs Principales

```
📝 Perfil de Firma (Configurar tu firma)
/firmas/perfil/

📋 Mis Documentos por Firmar
/firmas/por-firmar/

✍️ Firmar un Documento
/firmas/firmar/<documento_firmado_id>/

✅ Aplicar Firma (AJAX)
POST /firmas/aplicar/<documento_firmado_id>/

❌ Rechazar Firma (AJAX)
POST /firmas/rechazar/<documento_firmado_id>/

🔍 Verificar Firma Pública
/firmas/verificar/<token_uuid>/

⚙️ Solicitar Firmas (Admin)
/firmas/solicitar/<documento_id>/

📊 Lista de Documentos Firmados
/firmas/documentos/

🔧 Panel de Administración
/admin/documentos/
```

## ⚡ Funcionalidades Principales

### 1️⃣ Firma Manuscrita
- Canvas HTML5 interactivo
- Soporte mouse y touch
- Conversión automática a PNG transparente
- Reutilizable en múltiples documentos

### 2️⃣ Subida de PNG
- Drag & drop de archivos
- Validación de formato (PNG/JPG)
- Redimensionamiento automático
- Fondo transparente recomendado

### 3️⃣ Posicionamiento Flexible
- Arrastra firma con el mouse
- Posición en porcentaje (responsive)
- Múltiples páginas del documento
- Ajuste de tamaño dinámico

### 4️⃣ Seguridad SHA-256
- Hash del documento original
- Hash de cada firma
- Verificación de integridad
- Detección de modificaciones

### 5️⃣ Trazabilidad Completa
- Timestamp certificado
- IP address del firmante
- User agent del navegador
- Token UUID único

### 6️⃣ Workflow de Aprobación
- Múltiples firmantes
- Orden secuencial (opcional)
- Roles personalizados
- Firmas obligatorias/opcionales
- Rechazo con motivo

### 7️⃣ Auditoría
- Log inmutable de acciones
- Información forense
- Exportable en JSON
- Cumplimiento normativo

## 🎨 Capturas de Funcionalidades

### Perfil de Firma
```
┌─────────────────────────────────────┐
│  🖊️ Mi Firma Electrónica           │
├─────────────────────────────────────┤
│  📋 Info Personal:                  │
│  - Nombre: Juan Pérez               │
│  - Cargo: Ingeniero                 │
│  - Depto: Ingeniería                │
├─────────────────────────────────────┤
│  ✍️ Firma Manuscrita | 📤 Subir PNG │
├─────────────────────────────────────┤
│  [Canvas para dibujar firma]        │
│  🗑️ Limpiar  💾 Guardar             │
└─────────────────────────────────────┘
```

### Visor de Firma
```
┌──────────────────┬──────────────┐
│  📄 DOCUMENTO    │  ✍️ TU FIRMA │
│                  │              │
│  [PDF/Imagen]    │  [Preview]   │
│                  │              │
│  [Firma          │  Posición:   │
│   arrastrable]   │  X: 10%      │
│                  │  Y: 80%      │
│  [Firmas         │              │
│   existentes]    │  Comentarios │
│                  │  [textarea]  │
│                  │              │
│                  │  ✅ Firmar   │
│                  │  ❌ Rechazar │
└──────────────────┴──────────────┘
```

### Verificación de Firma
```
┌─────────────────────────────────────┐
│  ✅ Firma Válida y Auténtica        │
│  Esta firma es auténtica y el       │
│  documento no ha sido alterado      │
├─────────────────────────────────────┤
│  📋 Información:                    │
│  Firmante: Juan Pérez               │
│  Fecha: 26/12/2025 11:45:00         │
│  Documento: ENG-DOC-001             │
│  IP: 192.168.1.100                  │
├─────────────────────────────────────┤
│  🔒 Hash SHA-256:                   │
│  a3b4c5d6e7f8...                    │
├─────────────────────────────────────┤
│  📜 Certificado de Autenticidad     │
│  {                                  │
│    "token": "uuid...",              │
│    "documento": "ENG-DOC-001",      │
│    "firmante": "Juan Pérez",        │
│    ...                              │
│  }                                  │
└─────────────────────────────────────┘
```

## 🔐 Características de Seguridad

| Característica | Implementación |
|----------------|----------------|
| **Integridad del Documento** | Hash SHA-256 del archivo original |
| **Integridad de Firma** | Hash SHA-256 de la imagen de firma |
| **No Repudio** | Token UUID + Timestamp + Trazabilidad |
| **Autenticación** | Vinculado a usuario Django autenticado |
| **Auditoría** | Log completo de todas las acciones |
| **Verificación Pública** | Cualquiera puede verificar con el token |

## 📊 Estados del Documento

```
PENDIENTE    ⏳  Sin firmas aplicadas
PARCIAL      📝  Algunas firmas completadas
COMPLETO     ✅  Todas las firmas aplicadas
RECHAZADO    ❌  Al menos una firma rechazada
```

## 🎯 Casos de Uso

### Ejemplo 1: Documento de Ingeniería con 3 Firmantes

1. **Ingeniero** elabora documento → Firma como "Elaboró"
2. **Supervisor** revisa documento → Firma como "Revisó"
3. **Gerente** aprueba documento → Firma como "Aprobó"

### Ejemplo 2: Orden de Trabajo

1. **Técnico** completa trabajo → Firma como "Ejecutó"
2. **Cliente** recibe servicio → Firma como "Recibí Conforme"

### Ejemplo 3: Procedimiento Operativo

1. **Autor** crea procedimiento → Firma como "Elaboró"
2. **Calidad** verifica → Firma como "Verificó"
3. **Gerente** autoriza → Firma como "Autorizó"

## 🛠️ Personalización Rápida

### Cambiar Tamaño Por Defecto de Firma

`models_firmas.py` línea ~160:
```python
ancho = models.FloatField(default=20)  # Cambiar de 15 a 20%
alto = models.FloatField(default=10)   # Cambiar de 8 a 10%
```

### Agregar Campo Personalizado al Perfil

`models_firmas.py` modelo `PerfilFirma`:
```python
cedula = models.CharField(max_length=20, blank=True)
matricula_profesional = models.CharField(max_length=50, blank=True)
```

### Agregar Email de Notificación

`views_firmas.py` en función `solicitar_firmas`:
```python
from django.core.mail import send_mail

send_mail(
    subject='Firma Requerida',
    message=f'Tienes un documento pendiente: {doc.codigo}',
    from_email='sistema@energia.com',
    recipient_list=[firmante.email]
)
```

## 📱 Próximas Funcionalidades

- [ ] Generación automática de PDF con firmas visibles
- [ ] Códigos QR en certificados
- [ ] Notificaciones por email
- [ ] Firma con certificado digital PKI
- [ ] App móvil para firmar
- [ ] Integración con DocuSign/Adobe Sign
- [ ] Estadísticas y reportes
- [ ] Exportación masiva de certificados

## 🎓 Tips de Uso

1. **Para mejor calidad de firma manuscrita**: Dibuja despacio y con trazos firmes
2. **Para firma PNG**: Usa fondo transparente y alta resolución
3. **Posicionamiento**: Ajusta X/Y con precisión en los inputs numéricos
4. **Verificación**: Guarda el token UUID para futuras verificaciones
5. **Seguridad**: El hash SHA-256 detecta cualquier modificación del documento

## 📞 Acceso Rápido Admin

```
/admin/documentos/perfil firma/
/admin/documentos/documentofirmado/
/admin/documentos/firmarequerida/
/admin/documentos/firma/
/admin/documentos/auditoriafirmas/
```

---
**✅ Sistema listo para usar - ¡Empieza a firmar documentos ahora!**
