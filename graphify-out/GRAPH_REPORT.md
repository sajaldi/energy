# Graph Report - .  (2026-05-28)

## Corpus Check
- Large corpus: 1485 files · ~9,276,278 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder.

## Summary
- 185 nodes · 178 edges · 60 communities (13 shown, 47 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 10 edges (avg confidence: 0.74)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Django Models|Django Models]]
- [[_COMMUNITY_Budget & Finance|Budget & Finance]]
- [[_COMMUNITY_API Service (api.ts)|API Service (api.ts)]]
- [[_COMMUNITY_Maintenance CMMS|Maintenance CMMS]]
- [[_COMMUNITY_UIUX Design System|UI/UX Design System]]
- [[_COMMUNITY_Document Management|Document Management]]
- [[_COMMUNITY_Asset Management|Asset Management]]
- [[_COMMUNITY_Inventory Control|Inventory Control]]
- [[_COMMUNITY_Communications|Communications]]
- [[_COMMUNITY_Document Management|Document Management]]
- [[_COMMUNITY_Contract (PPP)|Contract (PPP)]]
- [[_COMMUNITY_Communications|Communications]]
- [[_COMMUNITY_Asset Management|Asset Management]]
- [[_COMMUNITY_admin_firmas.py|admin_firmas.py]]
- [[_COMMUNITY_Maintenance CMMS|Maintenance CMMS]]
- [[_COMMUNITY_initCommand|initCommand]]
- [[_COMMUNITY_updateCommand|updateCommand]]
- [[_COMMUNITY_versionsCommand|versionsCommand]]
- [[_COMMUNITY_AIType|AIType]]
- [[_COMMUNITY_InstallType|InstallType]]
- [[_COMMUNITY_Release|Release]]
- [[_COMMUNITY_Asset|Asset]]
- [[_COMMUNITY_InstallConfig|InstallConfig]]
- [[_COMMUNITY_PlatformConfig|PlatformConfig]]
- [[_COMMUNITY_detectAIType|detectAIType]]
- [[_COMMUNITY_getAITypeDescription|getAITypeDescription]]
- [[_COMMUNITY_extractZip|extractZip]]
- [[_COMMUNITY_copyFolders|copyFolders]]
- [[_COMMUNITY_cleanup|cleanup]]
- [[_COMMUNITY_createTempDir|createTempDir]]
- [[_COMMUNITY_installFromZip|installFromZip]]
- [[_COMMUNITY_GitHubRateLimitError|GitHubRateLimitError]]
- [[_COMMUNITY_GitHubDownloadError|GitHubDownloadError]]
- [[_COMMUNITY_fetchReleases|fetchReleases]]
- [[_COMMUNITY_getLatestRelease|getLatestRelease]]
- [[_COMMUNITY_downloadRelease|downloadRelease]]
- [[_COMMUNITY_getAssetUrl|getAssetUrl]]
- [[_COMMUNITY_PlatformConfig|PlatformConfig]]
- [[_COMMUNITY_loadPlatformConfig|loadPlatformConfig]]
- [[_COMMUNITY_loadAllPlatformConfigs|loadAllPlatformConfigs]]
- [[_COMMUNITY_renderSkillFile|renderSkillFile]]
- [[_COMMUNITY_generatePlatformFiles|generatePlatformFiles]]
- [[_COMMUNITY_generateAllPlatformFiles|generateAllPlatformFiles]]
- [[_COMMUNITY_getSupportedAITypes|getSupportedAITypes]]
- [[_COMMUNITY_RootStackParamList|RootStackParamList]]
- [[_COMMUNITY_Services & KPI|Services & KPI]]
- [[_COMMUNITY_Asset Management|Asset Management]]
- [[_COMMUNITY_Services & KPI|Services & KPI]]
- [[_COMMUNITY_ScanResult|ScanResult]]
- [[_COMMUNITY_Services & KPI|Services & KPI]]
- [[_COMMUNITY_InitializeResponse|InitializeResponse]]
- [[_COMMUNITY_Document Management|Document Management]]
- [[_COMMUNITY_urls_firmas.py|urls_firmas.py]]
- [[_COMMUNITY_perfil_firma.html|perfil_firma.html]]
- [[_COMMUNITY_visor_firmar.html|visor_firmar.html]]
- [[_COMMUNITY_verificar_firma.html|verificar_firma.html]]
- [[_COMMUNITY_lista_por_firmar.html|lista_por_firmar.html]]
- [[_COMMUNITY_solicitar_firmas.html|solicitar_firmas.html]]
- [[_COMMUNITY_lista_documentos_firmados.html|lista_documentos_firmados.html]]
- [[_COMMUNITY_User Onboarding Tutorial (Intro.js)|User Onboarding Tutorial (Intro.js)]]

## God Nodes (most connected - your core abstractions)
1. `Energy CMMS` - 22 edges
2. `Mantenimiento App (Maintenance CMMS)` - 13 edges
3. `Activos App (Asset Management)` - 11 edges
4. `Antigravity Kit (UI UX Pro Max)` - 11 edges
5. `Sistema de Firmas Electr�nicas` - 10 edges
6. `Documentos App (EDMS)` - 9 edges
7. `Inventarios App (Inventory)` - 8 edges
8. `Auditor�as Mobile App` - 7 edges
9. `Presupuestos App (Budget/Finance)` - 6 edges
10. `Coolify Deployment Platform` - 6 edges

## Surprising Connections (you probably didn't know these)
- `Energy CMMS` --references--> `Call Center App (MAO/Tickets)`  [EXTRACTED]
  SYSTEM_DOCUMENTATION.md → MODULOS.md
- `Sistema de Firmas Electr�nicas` --conceptually_related_to--> `Sistema de Gesti�n Documental (EDMS)`  [INFERRED]
  documentos/INDICE.md → walkthrough_documentos.md
- `SAP Fiori Horizon Mobile Redesign` --references--> `Auditor�as Mobile App`  [INFERRED]
  task.md → auditorias-mobile/README.md
- `Energy CMMS` --references--> `Activos App (Asset Management)`  [EXTRACTED]
  SYSTEM_DOCUMENTATION.md → MODULOS.md
- `Energy CMMS` --references--> `Auditorias App (Audits)`  [EXTRACTED]
  SYSTEM_DOCUMENTATION.md → MODULOS.md

## Hyperedges (group relationships)
- **Mermaid Architecture Graph** — app_mantenimiento, app_activos, app_seguridad, app_inventarios, app_presupuestos, app_proyectos, app_documentos, app_auditorias, app_callcenter, app_servicios [EXTRACTED 1.00]
- **Coolify Deployment Stack** — coolify, django_framework, postgresql, redis, celery [EXTRACTED 1.00]
- **n8n PDF Extraction Workflow** — n8n, app_documentos, concepto_callback_url, concepto_extraccion_pdf [EXTRACTED 1.00]
- **Lot/FEFO Inventory Subsystem** — modelo_lote, modelo_stockrecord, modelo_movimientoinventario, concepto_fefo, app_inventarios [EXTRACTED 1.00]
- **Import/Export Subsystem** — concepto_import_background, concepto_progreso_tiempo_real, celery, app_inventarios, app_mantenimiento, app_activos [EXTRACTED 1.00]
- **Modelos de Datos del Sistema de Firmas** — diagramas_perfilfirma, diagramas_documentofirmado, diagramas_firmarequerida, diagramas_firma, diagramas_auditoriafirmas, diagramas_user [EXTRACTED 1.00]
- **M�dulos Backend del Sistema de Firmas** — implementacion_completa_models_firmas_py, implementacion_completa_views_firmas_py, implementacion_completa_urls_firmas_py, implementacion_completa_admin_firmas_py [EXTRACTED 1.00]
- **Templates Frontend del Sistema de Firmas** — implementacion_completa_perfil_firma_html, implementacion_completa_visor_firmar_html, implementacion_completa_verificar_firma_html, implementacion_completa_lista_por_firmar_html, implementacion_completa_solicitar_firmas_html, implementacion_completa_lista_documentos_firmados_html [EXTRACTED 1.00]
- **Caracter�sticas de Seguridad** — readme_firmas_hash_sha256, readme_firmas_token_uuid [EXTRACTED 1.00]
- **Tipos de Comunicado** — walkthrough_comunicaciones_rfi, walkthrough_comunicaciones_trn, walkthrough_comunicaciones_inst [EXTRACTED 1.00]
- **Arquitectura en Capas del Sistema de Firmas** — diagramas_capa_vistas, diagramas_capa_logica, diagramas_capa_datos [EXTRACTED 1.00]
- **Infraestructura de Procesamiento As�ncrono** — importacion_asincrona_celery, importacion_asincrona_redis [EXTRACTED 1.00]
- **Auditor�as Mobile Component Suite** — auditcard_component, scannerview_component, resultcard_component, statsbar_component, auditlistscreen, auditexecutionscreen [EXTRACTED 1.00]
- **Contrato APP Parties and Entities** — contrato_ppp_ccg, secretaria_finanzas, banco_lafise, centro_civico_gubernamental [EXTRACTED 1.00]
- **UI UX Pro Max Design Intelligence Suite** — uipm_design_generator, uipm_search_engine, uipm_67_styles, uipm_96_palettes, uipm_57_typography, uipm_99_ux_guidelines, uipm_100_reasoning_rules, uipm_13_stacks [EXTRACTED 1.00]
- **Django Apps in energy/ Project** — edms_documentos_app, comunicaciones_app, planificacion_mensual, ordentrabajo_model, activo_model, ubicacion_model [INFERRED 0.75]

## Communities (60 total, 47 thin omitted)

### Community 0 - "Django Models"
Cohesion: 0.12
Nodes (19): Django, PostgreSQL, Capa de Datos, Capa de L�gica de Negocio, Capa de Vistas, Capas de Seguridad, Accesos R�pidos del Sistema, models_firmas.py (+11 more)

### Community 1 - "Budget & Finance"
Cohesion: 0.18
Nodes (16): Almacen App (Warehouse), Core App (System Core), Presupuestos App (Budget/Finance), Celery Async Task Queue, Cost Sheet Budget Monitor, Coolify Deployment Platform, Django Framework, Dynamics 365 ERP (+8 more)

### Community 2 - "API Service (api.ts)"
Cohesion: 0.13
Nodes (15): API Service (api.ts), AuditCard Component, AuditExecutionScreen, AuditListScreen, Auditor�as Mobile App, Comunicaciones App, Django Backend, EDMS Documentos App (+7 more)

### Community 3 - "Maintenance CMMS"
Cohesion: 0.17
Nodes (13): Call Center App (MAO/Tickets), Mantenimiento App (Maintenance CMMS), Seguridad App (Safety/Security), Servicios App (KPIs/Reporting), Visual Annual/Monthly Schedule, Material Settlement Process, Categoria Model (Routine Categories), Frecuencia Model (+5 more)

### Community 4 - "UI/UX Design System"
Cohesion: 0.21
Nodes (12): Antigravity Kit (UI UX Pro Max), 100 Reasoning Rules, 13 Tech Stacks Support, 57 Font Pairings Collection, 67 UI Styles Collection, 96 Color Palettes Collection, 99 UX Guidelines Collection, CSV Data Databases (+4 more)

### Community 5 - "Document Management"
Cohesion: 0.27
Nodes (11): Documentos App (EDMS), Proyectos App (Projects/CAPEX), Callback URL Pattern (n8n to Django), AI Chatbot (Gemini/n8n), PDF Text Extraction via n8n, Electronic Signatures, Mayan EDMS, Activo Model (Asset) (+3 more)

### Community 6 - "Asset Management"
Cohesion: 0.25
Nodes (9): Activos App (Asset Management), Auditorias App (Audits), Unique Composite Key (pipe-separated), Hierarchical Asset Explorer, MPTT Hierarchical Tree Structure, QR/RFID Scanner, Interactive Plan Viewer, Plano Model (Technical Drawings) (+1 more)

### Community 7 - "Inventory Control"
Cohesion: 0.36
Nodes (9): Inventarios App (Inventory), Technician Cart (Mobile), FEFO Algorithm (First Expired First Out), Background Import System, Real-Time Import Progress Bar, Lote Model (Proposed), Material Model (Catalog), MovimientoInventario Model (+1 more)

### Community 8 - "Communications"
Cohesion: 0.22
Nodes (9): Comunicados, INST (Instrucci�n de Campo), Notificaciones, RFI (Request for Information), Sistema de Comunicaciones, TRN (Transmittal), Disciplinas, Sistema de Gesti�n Documental (EDMS) (+1 more)

### Community 9 - "Document Management"
Cohesion: 0.39
Nodes (8): DocumentoFirmado, Firma, FirmaRequerida, PerfilFirma, User (Django), Fase 3: Generaci�n de PDFs, Documento, Revisi�n

### Community 10 - "Contract (PPP)"
Cohesion: 0.29
Nodes (7): Banco LAFISE (Honduras), Carol Sierra, Centro C�vico Gubernamental (CCG), Contrato APP Centro C�vico Gubernamental, KPI Indicators (IE-01 to IE-46), Mesa de Atenci�n Operativa (MAO), Secretar�a de Finanzas Honduras

### Community 11 - "Communications"
Cohesion: 0.70
Nodes (5): Comunicaciones App (Transmittals), AdjuntoComunicado Model, Comunicado Model, Destinatario Model, Notificacion Model

### Community 12 - "Asset Management"
Cohesion: 0.67
Nodes (3): Activo Model, MPTT Removal Optimization, Ubicacion Model

## Knowledge Gaps
- **107 isolated node(s):** `initCommand`, `updateCommand`, `versionsCommand`, `AIType`, `InstallType` (+102 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **47 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Energy CMMS` connect `Budget & Finance` to `Maintenance CMMS`, `Document Management`, `Asset Management`, `Inventory Control`, `Communications`?**
  _High betweenness centrality (0.074) - this node is a cross-community bridge._
- **Why does `Sistema de Firmas Electr�nicas` connect `Django Models` to `Communications`?**
  _High betweenness centrality (0.028) - this node is a cross-community bridge._
- **Why does `Mantenimiento App (Maintenance CMMS)` connect `Maintenance CMMS` to `Budget & Finance`, `Asset Management`, `Inventory Control`?**
  _High betweenness centrality (0.027) - this node is a cross-community bridge._
- **What connects `initCommand`, `updateCommand`, `versionsCommand` to the rest of the system?**
  _107 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Django Models` be split into smaller, more focused modules?**
  _Cohesion score 0.11695906432748537 - nodes in this community are weakly interconnected._
- **Should `API Service (api.ts)` be split into smaller, more focused modules?**
  _Cohesion score 0.13333333333333333 - nodes in this community are weakly interconnected._