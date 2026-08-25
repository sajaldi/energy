import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useSync } from '../context/SyncContext';

export default function SyncBar() {
  const { isSyncing, pendingCount, syncAll } = useSync();

  if (pendingCount === 0 && !isSyncing) return null;

  return (
    <View style={styles.bar}>
      <View style={styles.info}>
        <Ionicons name={isSyncing ? 'sync-outline' : 'cloud-offline-outline'} size={16} color="#fff" />
        <Text style={styles.text}>
          {isSyncing ? 'Sincronizando...' : `${pendingCount} operación(es) pendiente(s)`}
        </Text>
      </View>
      {!isSyncing && (
        <TouchableOpacity onPress={syncAll} style={styles.btn}>
          <Text style={styles.btnText}>Sincronizar</Text>
        </TouchableOpacity>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  bar: { backgroundColor: '#e9730c', paddingVertical: 8, paddingHorizontal: 16, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  info: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  text: { color: '#fff', fontSize: 13, fontWeight: '600' },
  btn: { backgroundColor: 'rgba(255,255,255,0.2)', paddingHorizontal: 12, paddingVertical: 4, borderRadius: 4 },
  btnText: { color: '#fff', fontWeight: '700', fontSize: 12 },
});
