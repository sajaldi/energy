# Guía de Configuración: n8n + Django - Extracción de Texto de PDFs

## 🚨 Problema Actual

El workflow de n8n está intentando hacer callback a:
```
❌ http://localhost:5000/documentos/api/update-texto/22/
```

Pero Django está corriendo en:
```
✅ http://localhost:8000
```

## ✅ Solución

### Paso 1: Abrir el Workflow en n8n

1. Abre n8n en tu navegador: `http://181.115.47.107:5678` (o donde esté corriendo)
2. Abre el workflow que se llama algo como "Extract Text from PDF" o similar

### Paso 2: Configurar el Nodo "Callback to Django"

Busca el nodo HTTP Request que hace el callback a Django (el que está fallando con el error rojo).

**Configuración correcta:**

```
┌─────────────────────────────────────────────────┐
│ HTTP Request - Callback to Django              │
├─────────────────────────────────────────────────┤
│                                                 │
│ Method: POST                                    │
│                                                 │
│ URL: {{$json["callback_url"]}}                  │
│      ↑ IMPORTANTE: Usar la variable dinámica   │
│                                                 │
│ Authentication: None                            │
│                                                 │
│ Send Headers: ✓                                 │
│   - Content-Type: application/json              │
│                                                 │
│ Send Body: ✓                                    │
│   Body Content Type: JSON                       │
│   Specify Body: Using JSON                      │
│                                                 │
│   JSON:                                         │
│   {                                             │
│     "texto": "{{$json.texto}}"                  │
│   }                                             │
│                                                 │
│   (Ajusta "texto" según el nombre del campo    │
│    donde guardas el texto extraído del PDF)    │
│                                                 │
└─────────────────────────────────────────────────┘
```

### Paso 3: Verificar el Payload que Recibe n8n

Cuando Django dispara el webhook de extracción, envía este payload:

```json
{
  "documento_id": 22,
  "codigo": "DOC-2024-001",
  "filepath": "documentos/archivo.pdf",
  "callback_url": "http://localhost:8000/documentos/api/update-texto/22/"
}
```

**El campo `callback_url` ya contiene la URL completa con el puerto correcto.**

### Paso 4: Flujo Completo

```
┌─────────────┐      ┌──────────────┐      ┌─────────────────┐
│   Django    │─────▶│     n8n      │─────▶│  Extrae Texto   │
│  (puerto    │ POST │  Webhook     │      │   del PDF       │
│   8000)     │      │  /extract-   │      │                 │
└─────────────┘      │   text       │      └─────────────────┘
                     └──────────────┘              │
                            ▲                      │
                            │                      ▼
                     ┌──────────────┐      ┌─────────────────┐
                     │   Django     │◀─────│  Callback to    │
                     │  Actualiza   │ POST │    Django       │
                     │  contenido_  │      │  (usa callback_ │
                     │   texto      │      │   url variable) │
                     └──────────────┘      └─────────────────┘
```

## 🔍 Debugging

### Si n8n sigue fallando:

1. **Verifica que Django esté corriendo:**
   ```bash
   # Debe mostrar algo en http://localhost:8000
   curl http://localhost:8000/admin/
   ```

2. **Verifica el endpoint del callback:**
   ```bash
   # Debe responder (aunque sea con error de CSRF)
   curl -X POST http://localhost:8000/documentos/api/update-texto/22/
   ```

3. **Revisa los logs de Django:**
   - En la terminal donde corre `python manage.py runserver`
   - Busca líneas que digan `POST /documentos/api/update-texto/...`

4. **Revisa los logs de n8n:**
   - En el workflow, haz clic en "Executions"
   - Revisa el payload que recibió y el que está enviando

## 📝 Variables de Entorno (Opcional)

Si quieres hacer esto más flexible, puedes agregar a tu `.env`:

```env
# URL base de Django (para callbacks de n8n)
SITE_URL=http://localhost:8000

# URL del webhook de n8n para extracción de texto
N8N_EXTRACT_TEXTO_WEBHOOK_URL=http://181.115.47.107:5678/webhook-test/extract-text
```

## ✅ Checklist de Verificación

- [ ] Django corriendo en puerto 8000
- [ ] n8n corriendo en puerto 5678
- [ ] Nodo "Callback to Django" usa `{{$json["callback_url"]}}`
- [ ] El método del callback es POST
- [ ] El body del callback incluye el campo "texto"
- [ ] El endpoint `/documentos/api/update-texto/<id>/` está registrado en Django
- [ ] El endpoint tiene `@csrf_exempt` (ya está configurado)

## 🎯 Resultado Esperado

Cuando todo funcione correctamente:

1. Haces clic en "⚡ Extraer Texto con n8n" en el admin de Django
2. Django envía el payload a n8n
3. n8n descarga el PDF, extrae el texto
4. n8n hace POST al callback_url con el texto extraído
5. Django actualiza el campo `contenido_texto` del documento
6. Puedes ver el texto en el panel de trazabilidad del documento
