# ☁️ Servicios y Sistemas Externos

El poder de **Energy** radica en su capacidad de orquestar servicios de terceros para ofrecer una experiencia industrial conectada.

## 🗂️ 1. MinIO / Almacenamiento S3
- **Propósito**: Repositorio seguro para archivos cargados en el módulo de documentos (planos, PDFs, manuales técnicos) e imágenes adjuntas a órdenes de trabajo y auditorías.
- **Funcionamiento**: Django se comunica mediante `django-storages` y la API compatible con Amazon S3. 
- **Ventaja**: Permite almacenar terabytes de datos técnicos sin ocupar espacio en el disco del servidor de base de datos.
- **Trazabilidad**: Las revisiones de documentos apuntan al almacenamiento remoto, manteniendo la versión exacta firmada digitalmente.

## 🤖 2. n8n (Inteligencia Artificial y Workflows)
- **Propósito**: Ejecución de flujos lógicos automáticos y asistente de IA.
- **Flujos**:
  - **Vectorización de Documentos**: Los PDFs técnicos se procesan a través de un flujo en n8n para extraer texto y generar embeddings vectoriales.
  - **Chat de IA**: Permite a los técnicos chatear con los manuales técnicos del activo en campo a través de un chat en la app móvil.
- **Configuración**: Comunicación vía Webhooks seguros entre Django y el servidor n8n.

## ⚙️ 3. Celery y Redis (Procesamiento Asíncrono)
- **Propósito**: Ejecución de tareas pesadas fuera de la solicitud HTTP (importaciones de catálogos de 80,000+ activos, generación de reportes anuales, envío masivo de correos).
- **Broker**: Redis actúa como broker de mensajería rápido.
- **Workers**: Workers distribuidos de Celery que procesan tareas fila por fila, enviando actualizaciones de progreso en tiempo real usando caché para polling en la UI.

## 💼 4. Microsoft Dynamics 365 (ERP)
- **Propósito**: Sincronización de transacciones financieras y estados de compras.
- **Flujo**: Sincronización asíncrona de Requisiciones, Presupuestos y Partidas, asegurando que la operación de mantenimiento no exceda el presupuesto disponible en el ERP corporativo.

---
🔙 Volver a [[00_Inicio|Inicio]]
