import React, { createContext, useContext, useState, useCallback } from 'react';
import { isOnline, fetchMasterData, pushOperations, pushInventoryCounts } from '../api/client';
import { upsertMaterials, upsertLocations, upsertStockRecords, getPendingOperations, markOperationSynced, setLastSync, getUnsyncedCounts, markCountsSynced, remapMaterialId } from '../db/database';

interface SyncState {
  isSyncing: boolean;
  lastSync: string | null;
  pendingCount: number;
  lastError: string | null;
  syncAll: () => Promise<void>;
  refreshPendingCount: () => Promise<void>;
}

const SyncContext = createContext<SyncState>({
  isSyncing: false,
  lastSync: null,
  pendingCount: 0,
  lastError: null,
  syncAll: async () => {},
  refreshPendingCount: async () => {},
});

export function SyncProvider({ children }: { children: React.ReactNode }) {
  const [isSyncing, setIsSyncing] = useState(false);
  const [lastSync, setLastSyncState] = useState<string | null>(null);
  const [pendingCount, setPendingCount] = useState(0);
  const [lastError, setLastError] = useState<string | null>(null);

  const refreshPendingCount = useCallback(async () => {
    const ops = await getPendingOperations();
    const counts = await getUnsyncedCounts();
    setPendingCount(ops.length + counts.length);
  }, []);

  const syncAll = useCallback(async () => {
    const online = await isOnline();
    if (!online) {
      setLastError('Sin conexión a internet.');
      return;
    }

    setIsSyncing(true);
    setLastError(null);
    let pullError: string | null = null;

    // ----- FASE 1: Push (no debe bloquear la descarga de datos maestros) -----
    try {
      const pending = await getPendingOperations();
      if (pending.length > 0) {
        const result = await pushOperations(pending.map(p => ({
          id: p.id,
          tipo: p.tipo,
          payload: JSON.parse(p.payload),
        })));
        if (result.synced) {
          for (const id of result.synced) {
            await markOperationSynced(id);
          }
        }
        if (result.material_id_map) {
          for (const [tempId, realId] of Object.entries(result.material_id_map)) {
            await remapMaterialId(Number(tempId), Number(realId));
          }
        }
      }

      const unsyncedCounts = await getUnsyncedCounts();
      if (unsyncedCounts.length > 0) {
        const countsPayload = unsyncedCounts.map(c => ({
          id: c.id,
          session_id: c.session_id,
          material_id: c.material_id,
          location_id: c.location_id,
          cantidad_sistema: c.cantidad_sistema,
          cantidad_contada: c.cantidad_contada,
          diferencia: c.diferencia,
        }));
        const countResult = await pushInventoryCounts(countsPayload);
        if (countResult.status === 'success' || countResult.success) {
          await markCountsSynced(unsyncedCounts.map((c: any) => c.id));
        }
      }
    } catch (error: any) {
      // Si falla el push, igual seguimos a descargar datos maestros (ubicaciones, etc.)
      console.error('Sync push error:', error);
      pullError = `No se pudieron enviar los pendientes: ${error?.message || error}`;
    }

    // ----- FASE 2: Pull de datos maestros (cada set independiente) -----
    try {
      const data = await fetchMasterData();
      // Ubicaciones primero (es lo más liviano y lo que necesita el conteo)
      if (data.locations) {
        try { await upsertLocations(data.locations); }
        catch (e: any) { console.error('upsertLocations error:', e); pullError = `Error guardando ubicaciones: ${e?.message || e}`; }
      }
      if (data.materials) {
        try { await upsertMaterials(data.materials); }
        catch (e: any) { console.error('upsertMaterials error:', e); }
      }
      if (data.stock) {
        try { await upsertStockRecords(data.stock); }
        catch (e: any) { console.error('upsertStockRecords error:', e); }
      }

      const now = new Date().toISOString();
      await setLastSync(now);
      setLastSyncState(now);
    } catch (error: any) {
      console.error('Sync pull error:', error);
      pullError = `No se pudieron descargar los datos: ${error?.message || error}`;
    }

    await refreshPendingCount();
    setLastError(pullError);
    setIsSyncing(false);
  }, [refreshPendingCount]);

  return (
    <SyncContext.Provider value={{ isSyncing, lastSync, pendingCount, lastError, syncAll, refreshPendingCount }}>
      {children}
    </SyncContext.Provider>
  );
}

export const useSync = () => useContext(SyncContext);
