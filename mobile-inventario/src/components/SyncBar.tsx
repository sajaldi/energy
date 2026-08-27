import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useSync } from '../context/SyncContext';

// Altura aproximada del tab bar de bottom-tabs (sin contar el safe area inferior)
const TAB_BAR_HEIGHT = 49;

export default function SyncBar() {
  const { isSyncing, pendingCount, syncAll } = useSync();
  const insets = useSafeAreaInsets();

  if (pendingCount === 0 && !isSyncing) return null;

  // Se ancla justo encima del tab bar, respetando el safe area inferior del dispositivo
  const bottomOffset = TAB_BAR_HEIGHT + insets.bottom;

  return (
    <View style={[styles.bar, { bottom: bottomOffset }]}>
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
  bar: {
    position: 'absolute',
    left: 0,
    right: 0,
    backgroundColor: '#e9730c',
    paddingVertical: 10,
    paddingHorizontal: 16,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    elevation: 8,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: -2 },
    shadowOpacity: 0.15,
    shadowRadius: 4,
    zIndex: 1000,
  },
  info: { flexDirection: 'row', alignItems: 'center', gap: 8, flex: 1 },
  text: { color: '#fff', fontSize: 13, fontWeight: '600' },
  btn: { backgroundColor: 'rgba(255,255,255,0.25)', paddingHorizontal: 14, paddingVertical: 6 },
  btnText: { color: '#fff', fontWeight: '700', fontSize: 12 },
});
