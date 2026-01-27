# Auditorías Mobile - Guía de Uso

## 📱 Aplicación Móvil para Auditorías de Activos

Esta es una aplicación móvil desarrollada con Expo Go que permite realizar auditorías de activos mediante escaneo de códigos de barras/QR usando `expo-camera`, integrada con el backend Django existente.

> **Nota**: La app usa `expo-camera` en lugar de `expo-barcode-scanner` para compatibilidad total con Expo Go sin necesidad de compilación nativa.

## 🚀 Inicio Rápido

### Prerrequisitos

1. **Node.js** instalado (v16 o superior)
2. **Expo Go** instalado en tu dispositivo móvil:
   - [Android](https://play.google.com/store/apps/details?id=host.exp.exponent)
   - [iOS](https://apps.apple.com/app/expo-go/id982107779)
3. **Servidor Django** ejecutándose y accesible en la red

### Configuración

1. **Configurar la URL del API:**
   
   Edita el archivo `services/api.ts` y actualiza la URL base:
   
   ```typescript
   const API_BASE_URL = 'http://TU_IP:8000';
   ```
   
   **Importante:** 
   - Para desarrollo local, usa la IP de tu computadora en la red local (ej: `http://192.168.1.100:8000`)
   - NO uses `localhost` o `127.0.0.1` ya que el móvil no podrá conectarse
   - Asegúrate de estar en la misma red WiFi que el servidor Django

2. **Verificar que Django esté ejecutándose:**
   
   ```bash
   cd d:\Apps\energia\energy
   python manage.py runserver 0.0.0.0:8000
   ```
   
   El `0.0.0.0` permite conexiones desde otros dispositivos en la red.

### Ejecutar la App

1. **Iniciar el servidor de desarrollo:**
   
   ```bash
   cd d:\Apps\energia\energy\auditorias-mobile
   npx expo start
   ```

2. **Abrir en tu dispositivo:**
   
   - Escanea el código QR que aparece en la terminal con la app Expo Go
   - O presiona `a` para Android / `i` para iOS si tienes emuladores

## 📖 Funcionalidades

### Lista de Auditorías

- Ver todas las auditorías disponibles
- Filtrar por estado (Borrador, En Curso, Finalizada)
- Pull-to-refresh para actualizar
- Ver progreso de cada auditoría

### Ejecución de Auditoría

1. **Inicializar Auditoría:**
   - Toca el botón "Inicializar Auditoría"
   - Esto crea los registros pendientes para todos los activos en el alcance

2. **Escanear Activos:**
   - Apunta la cámara al código de barras/QR del activo
   - O usa el botón "Ingreso Manual" para escribir el código
   - La app mostrará el resultado con código de color:
     - 🟢 Verde: Encontrado (ubicación correcta)
     - 🟡 Amarillo: Ubicación errónea
     - 🔴 Rojo: Extraviado
     - 🔵 Azul: No pertenece a la auditoría

3. **Ver Progreso:**
   - Estadísticas en tiempo real (total, escaneados, pendientes)
   - Lista de escaneos recientes
   - Barra de progreso visual

4. **Finalizar Auditoría:**
   - Toca "Finalizar Auditoría" cuando termines
   - Los activos no encontrados se marcarán como extraviados

## 🎨 Características

- ✅ Escaneo de códigos de barras/QR en tiempo real
- ✅ Entrada manual de códigos como alternativa
- ✅ Estadísticas de progreso en vivo
- ✅ Códigos de color para estados de activos
- ✅ Interfaz moderna y fácil de usar
- ✅ Sincronización automática con Django
- ✅ Manejo de errores robusto

## 🔧 Solución de Problemas

### Error de conexión

Si ves "No se pudo conectar con el servidor":

1. Verifica que Django esté ejecutándose con `python manage.py runserver 0.0.0.0:8000`
2. Confirma que la URL en `services/api.ts` sea correcta
3. Asegúrate de estar en la misma red WiFi
4. Verifica que el firewall no esté bloqueando el puerto 8000

### La cámara no funciona

1. Asegúrate de haber dado permisos de cámara a Expo Go
2. Usa el botón "Ingreso Manual" como alternativa
3. Reinicia la app

### Los escaneos no se registran

1. Verifica que la auditoría esté inicializada
2. Confirma que el código escaneado corresponda a un activo en el sistema
3. Revisa la consola de Django para ver los logs del servidor

## 📁 Estructura del Proyecto

```
auditorias-mobile/
├── components/          # Componentes reutilizables
│   ├── AuditCard.tsx   # Tarjeta de auditoría
│   ├── ScannerView.tsx # Vista de escáner
│   ├── ResultCard.tsx  # Tarjeta de resultado
│   └── StatsBar.tsx    # Barra de estadísticas
├── screens/            # Pantallas principales
│   ├── AuditListScreen.tsx      # Lista de auditorías
│   └── AuditExecutionScreen.tsx # Ejecución de auditoría
├── services/           # Servicios API
│   └── api.ts         # Cliente API Django
├── types/             # Definiciones TypeScript
│   └── index.ts
├── constants/         # Constantes de diseño
│   └── Colors.ts
└── App.tsx           # Componente raíz
```

## 🔄 Flujo de Trabajo

1. Crear auditoría en Django Admin
2. Abrir app móvil y seleccionar auditoría
3. Inicializar auditoría
4. Escanear activos en campo
5. Revisar progreso en tiempo real
6. Finalizar auditoría
7. Revisar resultados en Django Admin

## 📝 Notas

- La app requiere conexión de red para funcionar
- Los datos se sincronizan en tiempo real con Django
- Se recomienda usar en dispositivos con buena cámara para mejor escaneo
- Los permisos de cámara son necesarios para el escaneo de códigos

## 🆘 Soporte

Si encuentras problemas:

1. Revisa los logs en la consola de Expo
2. Verifica los logs del servidor Django
3. Asegúrate de que todas las dependencias estén instaladas
4. Confirma que las versiones de Node.js y Expo sean compatibles
