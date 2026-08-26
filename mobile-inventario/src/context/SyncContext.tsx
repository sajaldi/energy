import React, { createContext, useContext, useState, useCallback } from 'react';
import { isOnline, fetchMasterData, pushOperations, pushInventoryCounts } from '../api/client';
import { upsertMaterials, upsertLocations, upsertStockRecords, getPendingOperations, markOperationSynced, setLastSync, getUnsyncedCounts, markCountsSynced } from '../db/database';

interface SyncState {
  isSyncing: boolean;
  lastSync: string | null;
  pendingCount: number;
  syncAll: () => Promise<void>;
  refreshPendingCount: () => Promise<void>;
}

const SyncContext = createContext<SyncState>({
  isSyncing: false,
  lastSync: null,
  pendingCount: 0,
  syncAll: async () => {},
  refreshPendingCount: async () => {},
});

export function SyncProvider({ children }: { children: React.ReactNode }) {
  const [isSyncing, setIsSyncing] = useState(false);
  const [lastSync, setLastSyncState] = useState<string | null>(null);
  const [pendingCount, setPendingCount] = useState(0);

  const refreshPendingCount = useCallback(async () => {
    const ops = await getPendingOperations();
    const counts = await getUnsyncedCounts();
    setPendingCount(ops.length + counts.length);
  }, []);

  const syncAll = useCallback(async () => {
    const online = await isOnline();
    if (!online) return;

    setIsSyncing(true);
    try {
      // 1. Push pending operations
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
      }

      // 1.5. Push pending inventory counts
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

      // 2. Pull master data
      const data = await fetchMasterData();
      if (data.materials) await upsertMaterials(data.materials);
      if (data.locations) await upsertLocations(data.locations);
      if (data.stock) await upsertStockRecords(data.stock);

      // 3. Update sync timestamp
      const now = new Date().toISOString();
      await setLastSync(now);
      setLastSyncState(now);
      await refreshPendingCount();
    } catch (error) {
      console.error('Sync error:', error);
    } finally {
      setIsSyncing(false);
    }
  }, [refreshPendingCount]);

  return (
    <SyncContext.Provider value={{ isSyncing, lastSync, pendingCount, syncAll, refreshPendingCount }}>
      {children}
    </SyncContext.Provider>
  );
}

export const useSync = () => useContext(SyncContext);
