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
}

// ===== MATERIALS =====
export async function upsertMaterials(materials: any[]): Promise<void> {
  const database = await getDb();
  for (const m of materials) {
    await database.runAsync(
      `INSERT OR REPLACE INTO materials (id, nombre, sku, descripcion, unidad, categoria, imagen_url, stock_total, updated_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [m.id, m.nombre, m.sku, m.descripcion, m.unidad, m.categoria, m.imagen_url, m.stock_total, m.updated_at]
    );
  }
}

export async function searchMaterials(query: string): Promise<any[]> {
  const database = await getDb();
  return database.getAllAsync(
    `SELECT * FROM materials WHERE nombre LIKE ? OR sku LIKE ? ORDER BY nombre LIMIT 50`,
    [`%${query}%`, `%${query}%`]
  );
}

export async function getMaterialById(id: number): Promise<any> {
  const database = await getDb();
  return database.getFirstAsync(`SELECT * FROM materials WHERE id = ?`, [id]);
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
