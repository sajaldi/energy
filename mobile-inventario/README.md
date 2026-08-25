# SoftCoM Inventario — App de Campo

App React Native (Expo) offline-first para gestión de inventario en campo.

## Funcionalidades

- **Consulta de Stock** — Busca materiales en catálogo local (SQLite)
- **Escaneo QR / Código de Barras** — Identifica materiales con la cámara
- **Despacho / Recepción** — Registra entradas y salidas (offline queue)
- **Toma de Inventario Físico** — Conteo vs sistema con diferencias
- **Transferencias** — Mueve material entre ubicaciones

## Offline-First

- Catálogo completo en **SQLite** local
- Operaciones se guardan en **cola offline**
- Al recuperar conexión: **sync automático** con el backend Django

## Setup

```bash
cd mobile-inventario
npm install
npx expo start
```

## Build APK

```bash
npx eas build --platform android --profile preview
```

## Arquitectura

```
src/
├── api/client.ts          # HTTP client + auth
├── db/database.ts         # SQLite offline storage
├── context/
│   ├── AuthContext.tsx     # Login state
│   └── SyncContext.tsx     # Sync engine
├── components/
│   └── SyncBar.tsx        # Pending ops indicator
└── screens/
    ├── LoginScreen.tsx
    ├── StockScreen.tsx     # Consulta de stock
    ├── ScannerScreen.tsx   # QR + barcode
    ├── DispatchScreen.tsx  # Entradas/Salidas
    ├── InventoryScreen.tsx # Conteo físico
    └── TransferScreen.tsx  # Transferencias
```

## Backend APIs requeridas

El backend Django necesita exponer:
- `POST /api/auth/login/` — Retorna token
- `GET /inventarios/api/mobile-sync/master/` — Catálogo + stock + ubicaciones
- `POST /inventarios/api/mobile-sync/push/` — Recibe operaciones pendientes
- `POST /inventarios/api/mobile-sync/inventory-counts/` — Recibe conteos

## Configuración

Editar `src/api/client.ts`:
```typescript
const API_BASE = 'https://softcom.ccg.hn';
```
