# 🖊️ Sistema de Firmas Electrónicas

## Descripción General

Sistema completo de firmas electrónicas para documentos con las siguientes características:

### ✅ Características Principales

1. **Múltiples Métodos de Firma**
   - ✍️ Firma manuscrita (dibujo con canvas HTML5)
   - 📤 Subida de imagen PNG (con transparencia)
   - Reutilización de firma guardada en perfil

2. **Posicionamiento Flexible**
   - Arrastra y suelta tu firma en cualquier parte del documento
   - Ajuste de tamaño (ancho y alto en porcentaje)
   - Soporte multi-página
   - Posicionamiento preciso con coordenadas X, Y

3. **Seguridad Completa**
   - Hash SHA-256 del documento para verificar integridad
   - Hash SHA-256 de cada firma
   - Token único de verificación (UUID)
   - Timestamp certificado (fecha/hora exacta de firma)
   - Trazabilidad completa (IP, user agent, usuario)

4. **Workflow de Aprobación**
   - Múltiples firmantes por documento
   - Orden secuencial de firmas (opcional)
   - Roles personalizados (Elaboró, Revisó, Aprobó, etc.)
   - Firmas obligatorias y opcionales
   - Rechazo de documentos con motivo

5. **Auditoría Completa**
   - Log de todas las acciones
   - Historial inmutable
   - Certificado de autenticidad exportable
   - Verificación pública de firmas

## 📁 Estructura de Archivos

```
documentos/
├── models_firmas.py          # Modelos de datos para firmas
├── views_firmas.py           # Vistas y lógica de negocio
├── urls_firmas.py            # URLs del sistema
├── admin_firmas.py           # Configuración del admin
├── templates/
│   └── documentos/
│       └── firmas/
│           ├── perfil_firma.html              # Configurar firma personal
│           ├── lista_por_firmar.html          # Documentos pendientes
│           ├── visor_firmar.html              # Interfaz de firma
│           ├── verificar_firma.html           # Verificación pública
│           ├── solicitar_firmas.html          # Configurar firmantes
│           └── lista_documentos_firmados.html # Gestión de firmados
└── migrations/
    └── 0002_documentofirmado_firma_auditoriafirmas_and_more.py
```

## 🚀 Instalación y Configuración

### 1. Dependencias

El sistema ya está integrado. Asegúrate de tener:

```bash
pip install Pillow  # Para procesamiento de imágenes
```

### 2. Aplicar Migraciones

Ya se aplicaron automáticamente:

```bash
python manage.py migrate documentos
```

### 3. URLs Configuradas

Las URLs ya están incluidas en `energia/urls.py`:

```python
path('firmas/', include('documentos.urls_firmas', namespace='firmas')),
```

## 📖 Uso del Sistema

### Para Usuarios (Firmantes)

#### 1. Configurar Tu Firma

1. Ve a `/firmas/perfil/`
2. Elige uno de los dos métodos:
   - **Firma manuscrita**: Dibuja tu firma con el mouse o pantalla táctil
   - **Subir PNG**: Sube una imagen de tu firma (PNG con fondo transparente recomendado)
3. Completa tu cargo y departamento
4. Guarda tu firma

#### 2. Firmar un Documento

1. Ve a `/firmas/por-firmar/` para ver documentos pendientes
2. Haz clic en "Firmar Ahora"
3. En el visor:
   - Arrastra tu firma a la posición deseada
   - Ajusta con los controles de posición si es necesario
   - Agrega comentarios (opcional)
   - Haz clic en "Firmar Documento"
4. Recibirás un token de verificación único

#### 3. Rechazar un Documento

Si un documento requiere cambios:
1. Abre el visor de firma
2. Haz clic en "Rechazar Documento"
3. Proporciona un motivo
4. El documento se marcará como rechazado

### Para Administradores

#### 1. Solicitar Firmas para un Documento

1. Ve a `/firmas/solicitar/<documento_id>/`
2. Agrega firmantes:
   - Selecciona el usuario
   - Asigna un rol (Elaboró, Revisó, Aprobó, etc.)
   - Define la posición en el documento
3. Guarda la solicitud
4. Los firmantes serán notificados (si configuras notificaciones)

#### 2. Ver Estado de Documentos Firmados

1. Ve a `/firmas/documentos/`
2. Ver el progreso de cada documento:
   - ⏳ Pendiente
   - 📝 Parcial (algunas firmas completadas)
   - ✅ Completo (todas las firmas)
   - ❌ Rechazado

#### 3. Verificar Autenticidad de una Firma

1. Ve a `/firmas/verificar/<token>/`
2. Verás:
   - Información del firmante
   - Fecha y hora exacta de firma
   - Hash del documento y firma
   - Estado de integridad (si el documento fue modificado)
   - Certificado de autenticidad

## 🔒 Seguridad

### Hash SHA-256

Cada firma y documento genera un hash SHA-256 que permite:
- Verificar que el documento no ha sido modificado
- Garantizar la integridad de la firma
- Prevenir falsificaciones

### Token de Verificación

Cada firma recibe un UUID único que permite:
- Verificación pública sin autenticación
- Compartir certificados de autenticidad
- Generar códigos QR (futura implementación)

### Auditoría

Todas las acciones se registran en `AuditoriaFirmas`:
- Quién realizó la acción
- Cuándo (timestamp)
- Desde dónde (IP address)
- Qué hizo (detalle JSON)

## 🎨 Personalización

### Ajustar Tamaño de Firma por Defecto

En `models_firmas.py`, modelo `FirmaRequerida`:

```python
ancho = models.FloatField(default=15, help_text="Ancho (%)")
alto = models.FloatField(default=8, help_text="Alto (%)")
```

### Cambiar Posición Por Defecto

```python
posicion_x = models.FloatField(default=10, help_text="Posición X (%)")
posicion_y = models.FloatField(default=80, help_text="Posición Y (%)")
```

### Agregar Notificaciones por Email

En `views_firmas.py`, después de crear una `FirmaRequerida`:

```python
from django.core.mail import send_mail

send_mail(
    subject=f'Firma requerida: {doc_firmado.documento.codigo}',
    message=f'Tienes un documento pendiente de firma...',
    from_email='notificaciones@energia.com',
    recipient_list=[firmante.email],
)
```

## 📊 Modelos de Base de Datos

### PerfilFirma
- Almacena la firma de cada usuario
- Metadatos (cargo, departamento)
- Una firma por usuario

### DocumentoFirmado
- Documento que requiere firmas
- Hash SHA-256 del documento original
- Estado (Pendiente, Parcial, Completo, Rechazado)

### FirmaRequerida
- Define quién debe firmar
- Posición y tamaño de la firma
- Orden y obligatoriedad

### Firma
- Registro de firma aplicada
- Token de verificación
- Trazabilidad completa
- Hash de la firma

### AuditoriaFirmas
- Log inmutable de todas las acciones
- Información forense completa

## 🔄 Flujo de Trabajo Típico

1. **Administrador** crea un documento en el sistema
2. **Administrador** solicita firmas (`solicitar_firmas`)
3. **Sistema** crea `DocumentoFirmado` con `FirmaRequerida` para cada firmante
4. **Firmante 1** recibe notificación
5. **Firmante 1** configura su firma en `/firmas/perfil/` (si no la tiene)
6. **Firmante 1** firma el documento en `/firmas/firmar/<id>/`
7. **Sistema** crea registro `Firma` con hash y token
8. **Sistema** actualiza estado del `DocumentoFirmado`
9. **Firmante 2, 3, etc.** repiten pasos 5-7
10. Cuando todas las firmas están completas, estado = "COMPLETO"
11. **Cualquier persona** puede verificar la firma en `/firmas/verificar/<token>/`

## 🛠️ Mejoras Futuras

- [ ] Generación de PDF con firmas estampadas visualmente
- [ ] Códigos QR para verificación rápida
- [ ] Notificaciones por email automáticas
- [ ] Firma con certificado digital PKI
- [ ] Firma biométrica
- [ ] Integración con sistemas de archivo digital
- [ ] API REST para integración externa
- [ ] Dashboard de métricas y reportes

## 📞 Soporte

Para dudas sobre el sistema de firmas:
1. Consulta esta documentación
2. Revisa el código en `documentos/models_firmas.py` y `documentos/views_firmas.py`
3. Verifica los logs de auditoría en el admin de Django

## 📝 Licencia

Este sistema fue desarrollado como parte del proyecto Energía.

---

**Desarrollado con ❤️ para cumplir con los más altos estándares de seguridad**
