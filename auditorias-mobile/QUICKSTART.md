# 🚀 Inicio Rápido - Auditorías Mobile

## ⚡ Configuración en 3 Pasos

### 1️⃣ Configurar URL del Servidor

Edita `services/api.ts` línea 8:

```typescript
const API_BASE_URL = 'http://192.168.1.XXX:8000'; // Tu IP local
```

### 2️⃣ Iniciar Django

```bash
cd d:\Apps\energia\energy
python manage.py runserver 0.0.0.0:8000
```

### 3️⃣ Iniciar Expo

```bash
cd d:\Apps\energia\energy\auditorias-mobile
npx expo start
```

Escanea el QR con **Expo Go** en tu teléfono.

## 📱 Cómo Usar

1. **Crear auditoría** en Django Admin
2. **Abrir app** → Seleccionar auditoría
3. **Inicializar** → Escanear activos
4. **Finalizar** cuando termines

## 🎨 Estados de Escaneo

- 🟢 **Encontrado** - Ubicación correcta
- 🟡 **Ubicación Errónea** - Activo en lugar incorrecto
- 🔴 **Extraviado** - No encontrado al finalizar
- 🔵 **No Pertenece** - Fuera del alcance

## 🔧 Solución Rápida de Problemas

### No conecta con Django
- ✅ Django corriendo con `0.0.0.0:8000`
- ✅ Misma red WiFi
- ✅ URL correcta en `api.ts`

### Cámara no funciona
- ✅ Permisos otorgados a Expo Go
- ✅ Usar "Ingreso Manual" como alternativa

## 📁 Ubicación

```
d:\Apps\energia\energy\auditorias-mobile\
```

## 📚 Documentación Completa

Ver [README.md](file:///d:/Apps/energia/energy/auditorias-mobile/README.md) para guía detallada.
