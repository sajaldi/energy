/**
 * SQLite local database for offline-first inventory management.
 * Stores materials catalog, pending operations, and sync state.
 */
import * as SQLite from 'expo-sqlite';

let db: SQLite.SQLiteDatabase;

export async function getDb(): Promise<SQLite.SQLiteDatabase> {
  if (!db) {
    db = await SQLite.openDatabaseAsync('inventario.db');
  }
  return db;
}

export async function initDatabase(): Promise<void> {
  const database = await getDb();

  await database.execAsync(`
    -- Catálogo de materiales (sync desde servidor)
    CREATE TABLE IF NOT EXISTS materials (
      id INTEGER PRIMARY KEY,
      nombre TEXT NOT NULL,
      sku TEXT,
      codigo_barras TEXT,
      descripcion TEXT,
      unidad TEXT,
      categoria TEXT,
      imagen_url TEXT,
      stock_total REAL DEFAULT 0,
      updated_at TEXT
    );

    -- Ubicaciones/Bodegas
    CREATE TABLE IF NOT EXISTS locations (
      id INTEGER PRIMARY KEY,
      nombre TEXT NOT NULL,
      tipo TEXT,
      padre_id INTEGER
    );

    -- Stock por ubicación
    CREATE TABLE IF NOT EXISTS stock_records (
      id INTEGER PRIMARY KEY,
      material_id INTEGER NOT NULL,
      location_id INTEGER NOT NULL,
      cantidad REAL DEFAULT 0,
      FOREIGN KEY (material_id) REFERENCES materials(id),
      FOREIGN KEY (location_id) REFERENCES locations(id)
    );

    -- Cola de operaciones pendientes (offline queue)
    CREATE TABLE IF NOT EXISTS pending_operations (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tipo TEXT NOT NULL,
      payload TEXT NOT NULL,
      created_at TEXT DEFAULT (datetime('now')),
      synced INTEGER DEFAULT 0
    );

    -- Conteos de inventario físico
    CREATE TABLE IF NOT EXISTS inventory_counts (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      session_id TEXT NOT NULL,
      material_id INTEGER NOT NULL,
      location_id INTEGER NOT NULL,
      cantidad_sistema REAL,
      cantidad_contada REAL,
      diferencia REAL,
      created_at TEXT DEFAULT (datetime('now')),
      synced INTEGER DEFAULT 0
    );

    -- Última sincronización
    CREATE TABLE IF NOT EXISTS sync_meta (
      key TEXT PRIMARY KEY,
      value TEXT
    );
  `);

  // Migración: agregar columna codigo_barras si no existe (bases previas)
  try {
    const cols: any[] = await database.getAllAsync(`PRAGMA table_info(materials)`);
    const hasCodigoBarras = cols.some((c: any) => c.name === 'codigo_barras');
    if (!hasCodigoBarras) {
      await database.execAsync(`ALTER TABLE materials ADD COLUMN codigo_barras TEXT`);
    }
  } catch (e) {
    // silencioso
  }
}

// ===== MATERIALS =====
export async function upsertMaterials(materials: any[]): Promise<void> {
  const database = await getDb();
  for (const m of materials) {
    await database.runAsync(
      `INSERT OR REPLACE INTO materials (id, nombre, sku, codigo_barras, descripcion, unidad, categoria, imagen_url, stock_total, updated_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [m.id, m.nombre, m.sku, m.codigo_barras || null, m.descripcion, m.unidad, m.categoria, m.imagen_url, m.stock_total, m.updated_at]
    );
  }
}

export async function searchMaterials(query: string): Promise<any[]> {
  const database = await getDb();
  return database.getAllAsync(
    `SELECT * FROM materials WHERE nombre LIKE ? OR sku LIKE ? OR codigo_barras LIKE ? ORDER BY nombre LIMIT 50`,
    [`%${query}%`, `%${query}%`, `%${query}%`]
  );
}

export async function getMaterialById(id: number): Promise<any> {
  const database = await getDb();
  return database.getFirstAsync(`SELECT * FROM materials WHERE id = ?`, [id]);
}

export async function getMaterialByBarcode(codigo: string): Promise<any> {
  const database = await getDb();
  return database.getFirstAsync(`SELECT * FROM materials WHERE codigo_barras = ? OR sku = ?`, [codigo, codigo]);
}

// Crear material localmente con ID temporal negativo (se reemplaza al sincronizar)
export async function createMaterialLocal(data: { nombre: string; sku?: string; codigo_barras?: string; unidad?: string; descripcion?: string; }): Promise<any> {
  const database = await getDb();
  const tempId = -Date.now(); // ID temporal negativo único
  const sku = data.sku || `TMP-${Math.abs(tempId)}`;
  await database.runAsync(
    `INSERT INTO materials (id, nombre, sku, codigo_barras, descripcion, unidad, categoria, imagen_url, stock_total, updated_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    [tempId, data.nombre, sku, data.codigo_barras || null, data.descripcion || '', data.unidad || 'Unidad', '', '', 0, new Date().toISOString()]
  );
  // Encolar operación de creación
  await addPendingOperation('CREAR_MATERIAL', {
    temp_id: tempId,
    nombre: data.nombre,
    sku: sku,
    codigo_barras: data.codigo_barras || '',
    unidad: data.unidad || 'Unidad',
    descripcion: data.descripcion || '',
  });
  return { id: tempId, nombre: data.nombre, sku, codigo_barras: data.codigo_barras || '', unidad: data.unidad || 'Unidad' };
}

// Editar material localmente y encolar la edición
export async function updateMaterialLocal(id: number, data: { nombre?: string; codigo_barras?: string; descripcion?: string; }): Promise<void> {
  const database = await getDb();
  const fields: string[] = [];
  const values: any[] = [];
  if (data.nombre !== undefined) { fields.push('nombre = ?'); values.push(data.nombre); }
  if (data.codigo_barras !== undefined) { fields.push('codigo_barras = ?'); values.push(data.codigo_barras || null); }
  if (data.descripcion !== undefined) { fields.push('descripcion = ?'); values.push(data.descripcion); }
  if (fields.length === 0) return;
  values.push(id);
  await database.runAsync(`UPDATE materials SET ${fields.join(', ')} WHERE id = ?`, values);
  // Encolar edición solo si el material ya existe en servidor (id positivo)
  if (id > 0) {
    await addPendingOperation('EDITAR_MATERIAL', {
      material_id: id,
      nombre: data.nombre,
      codigo_barras: data.codigo_barras || '',
      descripcion: data.descripcion || '',
    });
  }
}

// Reemplazar ID temporal por ID real tras sincronización
export async function remapMaterialId(tempId: number, realId: number): Promise<void> {
  const database = await getDb();
  await database.runAsync(`UPDATE materials SET id = ? WHERE id = ?`, [realId, tempId]);
  await database.runAsync(`UPDATE stock_records SET material_id = ? WHERE material_id = ?`, [realId, tempId]);
  await database.runAsync(`UPDATE inventory_counts SET material_id = ? WHERE material_id = ?`, [realId, tempId]);
}

// ===== LOCATIONS =====
export async function upsertLocations(locations: any[]): Promise<void> {
  const database = await getDb();
  for (const l of locations) {
    await database.runAsync(
      `INSERT OR REPLACE INTO locations (id, nombre, tipo, padre_id) VALUES (?, ?, ?, ?)`,
      [l.id, l.nombre, l.tipo, l.padre_id]
    );
  }
}

export async function getLocations(): Promise<any[]> {
  const database = await getDb();
  return database.getAllAsync(`SELECT * FROM locations ORDER BY nombre`);
}

// ===== STOCK =====
export async function upsertStockRecords(records: any[]): Promise<void> {
  const database = await getDb();
  for (const r of records) {
    await database.runAsync(
      `INSERT OR REPLACE INTO stock_records (id, material_id, location_id, cantidad) VALUES (?, ?, ?, ?)`,
      [r.id, r.material_id, r.location_id, r.cantidad]
    );
  }
}

export async function getStockByMaterial(materialId: number): Promise<any[]> {
  const database = await getDb();
  return database.getAllAsync(
    `SELECT sr.*, l.nombre as location_name FROM stock_records sr JOIN locations l ON sr.location_id = l.id WHERE sr.material_id = ?`,
    [materialId]
  );
}

// Materiales con existencia en una ubicación específica (vista inicial de conteo)
export async function getMaterialsByLocation(locationId: number, query: string = ''): Promise<any[]> {
  const database = await getDb();
  const like = `%${query}%`;
  return database.getAllAsync(
    `SELECT m.id, m.nombre, m.sku, m.codigo_barras, m.unidad, sr.cantidad AS stock_ubicacion, sr.location_id
     FROM stock_records sr
     JOIN materials m ON sr.material_id = m.id
     WHERE sr.location_id = ?
       AND (m.nombre LIKE ? OR m.sku LIKE ? OR m.codigo_barras LIKE ?)
     ORDER BY m.nombre`,
    [locationId, like, like, like]
  );
}

// Busca en TODO el catálogo, mostrando el stock que tiene en la ubicación (0 si no tiene).
// Permite agregar materiales que aún no existen en esa ubicación.
export async function searchCatalogForLocation(locationId: number, query: string = ''): Promise<any[]> {
  const database = await getDb();
  const like = `%${query}%`;
  return database.getAllAsync(
    `SELECT m.id, m.nombre, m.sku, m.codigo_barras, m.unidad,
            COALESCE(sr.cantidad, 0) AS stock_ubicacion,
            ? AS location_id
     FROM materials m
     LEFT JOIN stock_records sr ON sr.material_id = m.id AND sr.location_id = ?
     WHERE m.nombre LIKE ? OR m.sku LIKE ? OR m.codigo_barras LIKE ?
     ORDER BY (sr.cantidad IS NULL), m.nombre
     LIMIT 50`,
    [locationId, locationId, like, like, like]
  );
}

// Solo ubicaciones tipo bodega/almacén
export async function getWarehouseLocations(): Promise<any[]> {
  const database = await getDb();
  return database.getAllAsync(
    `SELECT * FROM locations ORDER BY nombre`
  );
}

// ===== PENDING OPERATIONS (Offline Queue) =====
export async function addPendingOperation(tipo: string, payload: object): Promise<void> {
  const database = await getDb();
  await database.runAsync(
    `INSERT INTO pending_operations (tipo, payload) VALUES (?, ?)`,
    [tipo, JSON.stringify(payload)]
  );
}

export async function getPendingOperations(): Promise<any[]> {
  const database = await getDb();
  return database.getAllAsync(`SELECT * FROM pending_operations WHERE synced = 0 ORDER BY created_at`);
}

export async function markOperationSynced(id: number): Promise<void> {
  const database = await getDb();
  await database.runAsync(`UPDATE pending_operations SET synced = 1 WHERE id = ?`, [id]);
}

// ===== INVENTORY COUNTS =====
export async function addInventoryCount(sessionId: string, materialId: number, locationId: number, cantidadSistema: number, cantidadContada: number): Promise<void> {
  const database = await getDb();
  await database.runAsync(
    `INSERT INTO inventory_counts (session_id, material_id, location_id, cantidad_sistema, cantidad_contada, diferencia) VALUES (?, ?, ?, ?, ?, ?)`,
    [sessionId, materialId, locationId, cantidadSistema, cantidadContada, cantidadContada - cantidadSistema]
  );
}

export async function getCountsBySession(sessionId: string): Promise<any[]> {
  const database = await getDb();
  return database.getAllAsync(
    `SELECT ic.*, m.nombre as material_nombre, m.sku FROM inventory_counts ic JOIN materials m ON ic.material_id = m.id WHERE ic.session_id = ? ORDER BY ic.created_at`,
    [sessionId]
  );
}

// ===== SYNC META =====
export async function getLastSync(): Promise<string | null> {
  const database = await getDb();
  const row: any = await database.getFirstAsync(`SELECT value FROM sync_meta WHERE key = 'last_sync'`);
  return row ? row.value : null;
}

export async function setLastSync(timestamp: string): Promise<void> {
  const database = await getDb();
  await database.runAsync(
    `INSERT OR REPLACE INTO sync_meta (key, value) VALUES ('last_sync', ?)`,
    [timestamp]
  );
}

// ===== INVENTORY COUNTS SYNC =====
export async function getUnsyncedCounts(): Promise<any[]> {
  const database = await getDb();
  return database.getAllAsync(
    `SELECT ic.*, m.nombre as material_nombre, m.sku FROM inventory_counts ic JOIN materials m ON ic.material_id = m.id WHERE ic.synced = 0 ORDER BY ic.created_at`
  );
}

export async function markCountsSynced(ids: number[]): Promise<void> {
  if (ids.length === 0) return;
  const database = await getDb();
  const placeholders = ids.map(() => '?').join(',');
  await database.runAsync(`UPDATE inventory_counts SET synced = 1 WHERE id IN (${placeholders})`, ids);
}
