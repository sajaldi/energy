# 🔄 Diagramas y Flujos - Sistema de Firmas Electrónicas

## 📊 Diagrama de Arquitectura

```
┌─────────────────────────────────────────────────────────────────┐
│                    SISTEMA DE FIRMAS ELECTRÓNICAS                │
└─────────────────────────────────────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
    ┌───▼────┐           ┌─────▼──────┐         ┌─────▼──────┐
    │ USUARIO │           │   ADMIN    │         │  PÚBLICO   │
    │ FIRMANTE│           │ SOLICITANTE│         │ VERIFICADOR│
    └───┬────┘           └─────┬──────┘         └─────┬──────┘
        │                      │                       │
        │ /firmas/perfil/      │ /firmas/solicitar/   │ /firmas/verificar/
        │ /firmas/por-firmar/  │ /firmas/documentos/  │
        │ /firmas/firmar/      │                      │
        │                      │                       │
        └──────────────┬───────┴───────────────────────┘
                       │
        ┌──────────────▼──────────────┐
        │      CAPA DE VISTAS         │
        │   (views_firmas.py)         │
        │                             │
        │  - perfil_firma()           │
        │  - lista_documentos_por...()│
        │  - visor_documento_firmar() │
        │  - aplicar_firma()          │
        │  - rechazar_firma()         │
        │  - verificar_firma()        │
        │  - solicitar_firmas()       │
        └──────────────┬──────────────┘
                       │
        ┌──────────────▼──────────────┐
        │   CAPA DE LÓGICA DE NEGOCIO │
        │   (models_firmas.py)        │
        │                             │
        │  - Validaciones             │
        │  - Generación de Hash       │
        │  - Tokens UUID              │
        │  - Verificación Integridad  │
        │  - Certificados             │
        └──────────────┬──────────────┘
                       │
        ┌──────────────▼──────────────┐
        │     CAPA DE DATOS           │
        │     (PostgreSQL)            │
        │                             │
        │  [PerfilFirma]              │
        │  [DocumentoFirmado]         │
        │  [FirmaRequerida]           │
        │  [Firma]                    │
        │  [AuditoriaFirmas]          │
        └─────────────────────────────┘
```

---

## 🔄 Flujo 1: Configurar Firma Personal

```
┌──────────┐
│ Usuario  │
│ Login    │
└────┬─────┘
     │
     ▼
┌─────────────────────────────────┐
│ GET /firmas/perfil/             │
│                                 │
│ ┌─────────────────────────────┐ │
│ │ ✍️ Firma Manuscrita         │ │
│ │ [Canvas Interactivo]        │ │
│ │ Dibujar con mouse/touch     │ │
│ └─────────────────────────────┘ │
│                  O              │
│ ┌─────────────────────────────┐ │
│ │ 📤 Subir PNG                │ │
│ │ [Drag & Drop Area]          │ │
│ │ Seleccionar archivo         │ │
│ └─────────────────────────────┘ │
│                                 │
│ [Cargo]      [____________]     │
│ [Departamento] [__________]     │
│                                 │
│ [💾 Guardar Firma]              │
└────┬────────────────────────────┘
     │
     ▼
┌─────────────────────────┐
│ POST /firmas/perfil/    │
│                         │
│ - Procesar imagen       │
│ - Convertir a PNG       │
│ - Generar hash SHA-256  │
│ - Guardar en BD         │
└────┬────────────────────┘
     │
     ▼
┌─────────────────┐
│ PerfilFirma     │
│ ├─ usuario      │
│ ├─ firma_imagen │
│ ├─ cargo        │
│ ├─ departamento │
│ └─ hash         │
└─────────────────┘
```

---

## 🔄 Flujo 2: Solicitar Firmas (Admin)

```
┌──────────┐
│  Admin   │
│  Login   │
└────┬─────┘
     │
     ▼
┌──────────────────────────────────┐
│ GET /firmas/solicitar/<doc_id>/  │
│                                  │
│ 📄 Documento: ENG-PLN-001        │
│                                  │
│ ➕ Agregar Firmante:             │
│ [Usuario: ▼]  [Juan Pérez]       │
│ [Rol: ______] Elaboró            │
│ [Orden: ___]  1                  │
│                                  │
│ [➕ Agregar]                     │
│                                  │
│ Firmantes agregados:             │
│ ┌────────────────────────────┐  │
│ │ 1. Juan Pérez - Elaboró    │  │
│ │ 2. Ana López - Revisó      │  │
│ │ 3. Carlos Ruiz - Aprobó    │  │
│ └────────────────────────────┘  │
│                                  │
│ [💾 Guardar y Solicitar]         │
└────┬─────────────────────────────┘
     │
     ▼
┌─────────────────────────────────┐
│ POST /firmas/solicitar/<id>/    │
│                                 │
│ FOR EACH firmante:              │
│   - Crear FirmaRequerida        │
│   - Asignar posición default    │
│   - Establecer orden            │
│   - (Opcional) Enviar email     │
└────┬────────────────────────────┘
     │
     ▼
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│DocumentoFirmado  │    │FirmaRequerida #1 │    │FirmaRequerida #2 │
│├─ documento      │───▶│├─ firmante: Juan │    │├─ firmante: Ana  │
│├─ estado:PENDING │    ││  orden: 1        │    ││  orden: 2        │
│└─ hash_original  │    │└─ rol: Elaboró   │    │└─ rol: Revisó    │
└──────────────────┘    └──────────────────┘    └──────────────────┘
```

---

## 🔄 Flujo 3: Firmar Documento

```
┌──────────┐
│ Firmante │
│  Login   │
└────┬─────┘
     │
     ▼
┌──────────────────────────────┐
│ GET /firmas/por-firmar/      │
│                              │
│ 📋 Mis Documentos Pendientes │
│ ┌──────────────────────────┐ │
│ │ 📄 ENG-PLN-001           │ │
│ │ Plano de Instalación     │ │
│ │ Rol: Elaboró             │ │
│ │ [✍️ Firmar Ahora]        │ │
│ └──────────────────────────┘ │
└────┬─────────────────────────┘
     │
     ▼
┌───────────────────────────────────────────┐
│ GET /firmas/firmar/<doc_firmado_id>/      │
│                                           │
│ ┌─────────────────┬─────────────────────┐ │
│ │   DOCUMENTO     │    TU FIRMA         │ │
│ │ ┌────────────┐  │  ┌───────────────┐ │ │
│ │ │            │  │  │ [Preview]      │ │ │
│ │ │ [PDF/Img]  │  │  │               │ │ │
│ │ │            │  │  │ Juan Pérez    │ │ │
│ │ │  ┌────┐    │  │  │ Ingeniero     │ │ │
│ │ │  │📝  │←──────────┤ Elaboró       │ │ │
│ │ │  └────┘    │  │  │               │ │ │
│ │ │  Arrastrar │  │  │ Posición:     │ │ │
│ │ │  firma aquí│  │  │ X: [10]%      │ │ │
│ │ │            │  │  │ Y: [85]%      │ │ │
│ │ └────────────┘  │  │               │ │ │
│ │                 │  │ Comentarios:  │ │ │
│ │                 │  │ [_________]   │ │ │
│ │                 │  │               │ │ │
│ │                 │  │ [✅ Firmar]   │ │ │
│ │                 │  │ [❌ Rechazar] │ │ │
│ └─────────────────┴──┴───────────────┘ │
└───────┬───────────────────────────────┘
        │ Usuario hace clic en "Firmar"
        ▼
┌─────────────────────────────────────────┐
│ POST /firmas/aplicar/<doc_firmado_id>/  │
│                                         │
│ {                                       │
│   posicion_x: 10.5,                     │
│   posicion_y: 85.2,                     │
│   pagina: 1,                            │
│   comentarios: "OK"                     │
│ }                                       │
└───────┬─────────────────────────────────┘
        │
        ▼
┌─────────────────────────────┐
│ Validaciones:               │
│ ✓ Usuario autorizado?       │
│ ✓ Tiene perfil de firma?    │
│ ✓ No ha firmado antes?      │
│ ✓ Documento existe?         │
└───────┬─────────────────────┘
        │ Todas OK
        ▼
┌──────────────────────────────┐
│ Crear registro Firma:        │
│ ├─ documento_firmado         │
│ ├─ firma_requerida           │
│ ├─ firmante                  │
│ ├─ imagen_firma ← del perfil │
│ ├─ posicion_x, posicion_y    │
│ ├─ hash_firma ← calcular     │
│ ├─ token ← generar UUID      │
│ ├─ timestamp ← now()         │
│ ├─ ip_firmante               │
│ └─ user_agent                │
└───────┬──────────────────────┘
        │
        ▼
┌──────────────────────────────┐
│ Actualizar DocumentoFirmado: │
│                              │
│ firmas_aplicadas: 1          │
│ firmas_totales: 3            │
│ estado: PARCIAL              │
└───────┬──────────────────────┘
        │
        ▼
┌──────────────────────────────┐
│ Crear AuditoriaFirmas:       │
│ ├─ usuario: Juan Pérez       │
│ ├─ accion: FIRMAR            │
│ ├─ fecha: 2025-12-26 11:45   │
│ ├─ ip: 192.168.1.100         │
│ └─ detalles: {...}           │
└───────┬──────────────────────┘
        │
        ▼
┌─────────────────────────────────┐
│ Respuesta JSON:                 │
│ {                               │
│   success: true,                │
│   token_verificacion: "uuid...",│
│   certificado: {...}            │
│ }                               │
└───────┬─────────────────────────┘
        │
        ▼
┌──────────────────┐
│ ✅ FIRMAD EXITOSAMENTE │
│                  │
│ Token: abc123... │
└──────────────────┘
```

---

## 🔄 Flujo 4: Verificar Firma (Público)

```
┌──────────────┐
│ Cualquier    │
│ Persona      │
└────┬─────────┘
     │
     │ Tiene token: abc123-def456-...
     │
     ▼
┌────────────────────────────────────┐
│ GET /firmas/verificar/<token>/     │
└────┬───────────────────────────────┘
     │
     ▼
┌────────────────────────────────────┐
│ Buscar Firma por token UUID        │
└────┬───────────────────────────────┘
     │
     ├─ Encontrada ─────────────────┐
     │                              │
     ▼                              │
┌──────────────────────────────────┐ │
│ Verificar Integridad:            │ │
│                                  │ │
│ hash_almacenado = Firma.hash     │ │
│ hash_documento = calcular_hash() │ │
│                                  │ │
│ hash_almacenado == hash_actual?  │ │
│      ├─ SÍ: ✅ Íntegro           │ │
│      └─ NO: ⚠️ Modificado        │ │
└──────┬───────────────────────────┘ │
       │                             │
       ▼                             │
┌─────────────────────────────────┐  │
│ MOSTRAR CERTIFICADO:            │  │
│                                 │  │
│ ✅ Firma Válida y Auténtica     │  │
│                                 │  │
│ 📋 Información:                 │  │
│ Firmante: Juan Pérez            │  │
│ Fecha: 26/12/2025 11:45:30      │  │
│ Documento: ENG-PLN-001          │  │
│ IP: 192.168.1.100               │  │
│                                 │  │
│ 🔒 Hashes SHA-256:              │  │
│ Firma: a3b4c5d6e7f8...          │  │
│ Documento: 9f8e7d6c5b4a...      │  │
│                                  │ │
│ 💾 Estado:                       │ │
│ ✅ Documento íntegro            │  │
│ No ha sido modificado           │  │
│                                 │  │
│ 📜 Certificado JSON:            │  │
│ {                               │  │
│   token: "...",                 │  │
│   documento: "ENG-PLN-001",     │  │
│   firmante: "Juan Pérez",       │  │
│   fecha: "2025-12-26...",       │  │
│   hash_firma: "...",            │  │
│   hash_documento: "..."         │  │
│ }                               │  │
└─────────────────────────────────┘  │
                                     │
┌────────── NO Encontrada ───────────┘
│
▼
┌──────────────────────────┐
│ ❌ Firma No Encontrada   │
│                          │
│ El token proporcionado   │
│ no es válido o la firma  │
│ no existe en el sistema  │
└──────────────────────────┘
```

---

## 🔄 Flujo 5: Estado del Documento (Completo)

```
DocumentoFirmado
├─ estado: PENDIENTE
│
│ Firmante #1 firma ──────────┐
│                             │
├─ estado: PARCIAL            ▼
│  (1/3 firmas)          ┌──────────────┐
│                        │ Firma #1     │
│ Firmante #2 firma ────┼─ firmado=True │
│                        │ Juan Pérez   │
├─ estado: PARCIAL       └──────────────┘
│  (2/3 firmas)               │
│                             │
│ Firmante #3 firma ──────────┤
│                             │
├─ estado: COMPLETO           ▼
│  (3/3 firmas)          ┌──────────────┐
│                        │ Firma #2     │
│ ✅ Documento completo  ├─ firmado=True │
│                        │ Ana López    │
└─────────────────────── └──────────────┘
                              │
                              ▼
                         ┌──────────────┐
                         │ Firma #3     │
                         ├─ firmado=True │
                         │ Carlos Ruiz  │
                         └──────────────┘
```

---

## 🔄 Flujo 6: Rechazo de Documento

```
Firmante en /firmas/firmar/<id>/
│
│ Ve algo incorrecto
│
▼
Hace clic en [❌ Rechazar]
│
▼
Ingresa motivo:
"El documento tiene errores en
 la sección 3.2, revisar cálculos"
│
▼
POST /firmas/rechazar/<id>/
│
▼
┌──────────────────────────────┐
│ Crear Firma de Rechazo:      │
│ ├─ firmado: False            │
│ ├─ rechazado: True           │
│ ├─ motivo_rechazo: "..."     │
│ └─ timestamp, IP, etc.       │
└───────┬──────────────────────┘
        │
        ▼
┌──────────────────────────────┐
│ Actualizar DocumentoFirmado: │
│ estado: RECHAZADO            │
└───────┬──────────────────────┘
        │
        ▼
┌──────────────────────────────┐
│ Notificar a solicitante:     │
│ "Documento rechazado por     │
│  Ana López. Motivo: ..."     │
└──────────────────────────────┘
```

---

## 📊 Modelo de Datos Relacional

```
┌─────────────────────────┐
│      User (Django)      │
│ ────────────────────────│
│ PK: id                  │
│     username            │
│     first_name          │
│     last_name           │
│     email               │
└──┬────────────┬─────────┘
   │            │
   │            │
   │1          1│
   │            │
┌──▼─────────────────────┐   ┌──▼─────────────────────┐
│   PerfilFirma          │   │   FirmaRequerida       │
│ ──────────────────────│   │ ──────────────────────│
│ PK: id                 │   │ PK: id                 │
│ FK: usuario            │   │ FK: firmante           │
│     firma_imagen       │   │ FK: documento_firmado  │
│     cargo              │   │     rol                │
│     departamento       │   │     orden              │
│     activa             │   │     posicion_x/y       │
└────────────────────────┘   │     pagina             │
                             │     ancho/alto         │
                             └──┬─────────────────────┘
                                │1
                                │
                               1│
┌──────────────────────────────▼┐
│        Firma                  │
│ ─────────────────────────────│
│ PK: id                        │
│ FK: documento_firmado         │
│ FK: firma_requerida (1-to-1)  │
│ FK: firmante                  │
│     imagen_firma              │
│     posicion_x/y, pagina      │
│     hash_firma                │
│     token_verificacion (UUID) │
│     fecha_firma               │
│     ip_firmante               │
│     firmado                   │
│     rechazado                 │
│     motivo_rechazo            │
└───────────────────────────────┘
        ▲
        │*
        │
        │1
┌───────┴──────────────────────┐
│   DocumentoFirmado           │
│ ─────────────────────────────│
│ PK: id                       │
│ FK: documento                │
│ FK: revision                 │
│     hash_documento_original  │
│     estado                   │
│     pdf_firmado              │
└──┬───────────────────────────┘
   │1
   │
   │*
┌──▼──────────────────────────┐
│   Documento (existente)      │
│ ─────────────────────────────│
│ PK: id                       │
│     codigo                   │
│     titulo                   │
│     tipo_documento           │
└──────────────────────────────┘
```

---

## 🔐 Flujo de Seguridad

```
┌──────────────────────────────────────────────┐
│          CAPAS DE SEGURIDAD                  │
└──────────────────────────────────────────────┘

Nivel 1: AUTENTICACIÓN
├─ Django @login_required
├─ Usuario debe estar autenticado
└─ Sesión válida

Nivel 2: AUTORIZACIÓN
├─ Verificar FirmaRequerida existe
├─ Verificar usuario == firmante
└─ Verificar no firmado previamente

Nivel 3: INTEGRIDAD DE DATOS
├─ Hash SHA-256 del documento
│  ├─ Calculado al crear DocumentoFirmado
│  └─ Verificado posteriormente
│
├─ Hash SHA-256 de imagen de firma
│  ├─ Calculado al guardar firma
│  └─ Stored para verificación
│
└─ Token UUID único
   ├─ No predecible
   └─ Verificación pública segura

Nivel 4: TRAZABILIDAD
├─ Timestamp (fecha/hora exacta)
├─ IP address del firmante
├─ User Agent (navegador/dispositivo)
└─ Usuario Django autenticado

Nivel 5: AUDITORÍA
├─ AuditoriaFirmas (log inmutable)
├─ Todas las acciones registradas
├─ Información forense completa
└─ Exportable para análisis

Nivel 6: NO REPUDIO
├─ Firma vinculada a usuario
├─ No modificable después de crear
├─ Certificado de autenticidad
└─ Verificación pública disponible
```

---

Este archivo proporciona diagramas visuales ASCII del sistema completo.
Para más información, consulta INDICE.md
