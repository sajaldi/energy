# Bases de Diseño — SoftCom CCG (Django Project)

## Tipografía

- **Fuente principal:** Artifakt Element (Autodesk Fusion)
- **Fallback:** Outfit, sans-serif
- **Carga vía CDN:**
  ```html
  <!-- Artifakt Element desde Autodesk GitHub -->
  <style>
    @font-face {
      font-family: 'Artifakt Element';
      src: url('https://raw.githubusercontent.com/Autodesk/standard-surface/master/style/fonts/Artifakt/Artifakt%20Element%20Medium.woff2') format('woff2');
      font-weight: 400;
      font-style: normal;
      font-display: swap;
    }
    @font-face {
      font-family: 'Artifakt Element';
      src: url('https://raw.githubusercontent.com/Autodesk/standard-surface/master/style/fonts/Artifakt/Artifakt%20Legend%20Bold.woff2') format('woff2');
      font-weight: 700;
      font-style: normal;
      font-display: swap;
    }
  </style>
  <!-- Fallback Outfit desde Google Fonts -->
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
  ```
- **Uso en CSS:**
  ```css
  font-family: 'Artifakt Element', 'Outfit', sans-serif;
  ```

## Paleta de Colores (Estilo SAP Fiori)

| Variable                 | Valor     | Uso                         |
|--------------------------|-----------|-----------------------------|
| `--fiori-primary`        | `#0070f2` | Acciones principales, links |
| `--fiori-bg`             | `#eff2f5` | Fondo de página             |
| `--fiori-card-bg`        | `#ffffff` | Fondo de tarjetas           |
| `--fiori-text`           | `#32363a` | Texto principal             |
| `--fiori-text-secondary` | `#6a6d70` | Texto secundario            |
| `--fiori-border`         | `#d9d9d9` | Bordes                      |
| `--fiori-success`        | `#107e3e` | Estados exitosos            |
| `--fiori-warning`        | `#e9730c` | Advertencias                |
| `--fiori-error`          | `#bb0000` | Errores                     |

## Componentes UI

### Botones
- Primario: fondo `--fiori-primary`, texto blanco, border-radius 4px
- Secundario: fondo blanco, borde `--fiori-border`, texto oscuro
- Danger: fondo `--fiori-error`, texto blanco

### Tablas (sap-table)
- Headers con fondo `#f0f4f8`, borde inferior
- Filas con hover sutil
- Edición inline tipo Excel con toggle de modo

### Tarjetas (sap-card)
- Fondo blanco, borde 1px solid `--fiori-border`
- Border-radius 0.5rem
- Box-shadow sutil: `0 0.125rem 0.25rem rgba(0, 0, 0, 0.08)`
- Hover: translateY(-4px) + border-color primary

### Badges de Estado
- Pendiente: bg `#f1f5f9`, color `#475569`
- En Progreso/Ejecución: bg `#fef3c7`, color `#92400e`
- Completada/Realizada: bg `#dcfce7`, color `#166534`
- Error/Cancelada: bg `#fee2e2`, color `#991b1b`
- Info/Programada: bg `#eff6ff`, color `#1d4ed8`

## Diagrama de Gantt

- Librería: Frappe Gantt v0.6.1
- Bar height: 26px, padding: 14px
- Colores por prioridad:
  - Baja: `#94a3b8` / `#64748b`
  - Media: `#4a90d9` / `#0070f2`
  - Alta: `#f59e0b` / `#d97706`
  - Crítica: `#ef4444` / `#dc2626`
  - Elementos: `#0e7c86` / `#14b8a6`
- Labels: Artifakt Element, 11px, blanco sobre barra

## Iconos

- Font Awesome 6.x (CDN)
- Estilo: solid (`fas`) por defecto

## Principios Generales

1. Todas las vistas nuevas deben usar Artifakt Element con fallback Outfit
2. Estilo SAP Fiori: limpio, profesional, sin bordes redondeados excesivos
3. Modales: usar Bootstrap 5 Modal con backdrop static
4. Alertas/Toasts: SweetAlert2
5. Tablas editables con modo vista/edición toggle
6. Persistencia de tab activa vía sessionStorage al recargar
7. Drag & drop nativo (HTML5) para reordenamiento
