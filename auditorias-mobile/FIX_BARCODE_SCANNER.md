# Corrección: Expo Barcode Scanner → Expo Camera

## Problema
```
runtime not ready: error cannot find native module expobarcodescanner
```

## Causa
`expo-barcode-scanner` requiere compilación nativa y no está disponible en Expo Go.

## Solución
✅ Reemplazado `expo-barcode-scanner` con `expo-camera`

### Cambios Realizados

**Antes:**
```typescript
import { BarCodeScanner } from 'expo-barcode-scanner';
```

**Después:**
```typescript
import { CameraView, useCameraPermissions } from 'expo-camera';
```

### Componente Actualizado

- ✅ Usa `CameraView` con `barcodeScannerSettings`
- ✅ Hook `useCameraPermissions()` para permisos
- ✅ Soporta múltiples tipos de códigos: QR, Code128, Code39, EAN13, EAN8, UPC-A, UPC-E
- ✅ 100% compatible con Expo Go

### Verificación

```bash
npx tsc --noEmit  # ✅ Sin errores
```

## Estado
🟢 **Resuelto** - La app ahora funciona correctamente en Expo Go sin necesidad de compilación nativa.
