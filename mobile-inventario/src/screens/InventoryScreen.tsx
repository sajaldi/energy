import React, { useState, useEffect } from 'react';
import { View, Text, TextInput, TouchableOpacity, FlatList, StyleSheet, Alert } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { searchMaterials, addInventoryCount, getCountsBySession } from '../db/database';
import { useSync } from '../context/SyncContext';

export default function InventoryScreen() {
  const [sessionId] = useState(() => `INV-${Date.now()}`);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<any[]>([]);
  const [counts, setCounts] = useState<any[]>([]);
  const [selectedMaterial, setSelectedMaterial] = useState<any>(null);
  const [cantidadContada, setCantidadContada] = useState('');
  const { refreshPendingCount } = useSync();

  useEffect(() => {
    loadCounts();
  }, []);

  const loadCounts = async () => {
    const c = await getCountsBySession(sessionId);
    setCounts(c);
  };

  const buscar = async () => {
    if (query.length < 2) return;
    const r = await searchMaterials(query);
    setResults(r);
  };

  const registrarConteo = async () => {
    if (!selectedMaterial) return;
    const contada = parseFloat(cantidadContada);
    if (isNaN(contada) || contada < 0) { Alert.alert('Error', 'Cantidad inválida'); return; }

    await addInventoryCount(
      sessionId,
      selectedMaterial.id,
      1, // TODO: seleccionar ubicación
      selectedMaterial.stock_total,
      contada
    );

    await loadCounts();
    await refreshPendingCount();
    setSelectedMaterial(null);
    setCantidadContada('');
    setQuery('');
    setResults([]);
  };

  const diferencia = selectedMaterial ? (parseFloat(cantidadContada || '0') - selectedMaterial.stock_total) : 0;

  return (
    <View style={styles.container}>
      <Text style={styles.sessionLabel}>Sesión: {sessionId}</Text>

      {/* Search */}
      <View style={styles.searchRow}>
        <TextInput style={styles.searchInput} placeholder="Buscar material para contar..." value={query} onChangeText={setQuery} onSubmitEditing={buscar} />
        <TouchableOpacity onPress={buscar} style={styles.searchBtn}><Ionicons name="search" size={20} color="#fff" /></TouchableOpacity>
      </View>

      {/* Search Results */}
      {!selectedMaterial && results.map(item => (
        <TouchableOpacity key={item.id} style={styles.item} onPress={() => { setSelectedMaterial(item); setResults([]); }}>
          <Text style={styles.itemName}>{item.nombre}</Text>
          <Text style={styles.itemSku}>{item.sku} · Sistema: {item.stock_total}</Text>
        </TouchableOpacity>
      ))}

      {/* Counting Form */}
      {selectedMaterial && (
        <View style={styles.countCard}>
          <Text style={styles.countName}>{selectedMaterial.nombre}</Text>
          <Text style={styles.countSku}>{selectedMaterial.sku}</Text>
          <Text style={styles.countSystem}>Stock Sistema: <Text style={{ fontWeight: '800' }}>{selectedMaterial.stock_total}</Text></Text>
          <TextInput style={styles.countInput} placeholder="Cantidad contada" keyboardType="decimal-pad" value={cantidadContada} onChangeText={setCantidadContada} autoFocus />
          {cantidadContada !== '' && (
            <Text style={[styles.diff, diferencia > 0 ? styles.diffPositive : diferencia < 0 ? styles.diffNegative : styles.diffZero]}>
              Diferencia: {diferencia > 0 ? '+' : ''}{diferencia}
            </Text>
          )}
          <TouchableOpacity style={styles.countBtn} onPress={registrarConteo}>
            <Ionicons name="checkmark-circle" size={20} color="#fff" />
            <Text style={styles.countBtnText}>Registrar Conteo</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={() => { setSelectedMaterial(null); setCantidadContada(''); }}>
            <Text style={styles.cancelText}>Cancelar</Text>
          </TouchableOpacity>
        </View>
      )}

      {/* History */}
      {counts.length > 0 && !selectedMaterial && (
        <>
          <Text style={styles.historyTitle}>Conteos registrados ({counts.length})</Text>
          <FlatList
            data={counts}
            keyExtractor={(_, i) => String(i)}
            renderItem={({ item }) => (
              <View style={styles.historyItem}>
                <View style={{ flex: 1 }}>
                  <Text style={{ fontWeight: '700' }}>{item.material_nombre}</Text>
                  <Text style={{ fontSize: 12, color: '#6a6d70' }}>{item.sku}</Text>
                </View>
                <View style={{ alignItems: 'flex-end' }}>
                  <Text style={{ fontSize: 12, color: '#6a6d70' }}>Sistema: {item.cantidad_sistema}</Text>
                  <Text style={{ fontSize: 14, fontWeight: '700' }}>Contado: {item.cantidad_contada}</Text>
                  <Text style={[{ fontSize: 12, fontWeight: '800' }, item.diferencia > 0 ? { color: '#107e3e' } : item.diferencia < 0 ? { color: '#bb0000' } : { color: '#6a6d70' }]}>
                    Δ {item.diferencia > 0 ? '+' : ''}{item.diferencia}
                  </Text>
                </View>
              </View>
            )}
          />
        </>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f7f7f7', padding: 16 },
  sessionLabel: { fontSize: 11, color: '#94a3b8', marginBottom: 8 },
  searchRow: { flexDirection: 'row', gap: 8, marginBottom: 12 },
  searchInput: { flex: 1, backgroundColor: '#fff', borderWidth: 1, borderColor: '#d9d9d9', padding: 12, fontSize: 16 },
  searchBtn: { backgroundColor: '#0070f2', padding: 12, justifyContent: 'center' },
  item: { backgroundColor: '#fff', padding: 14, borderBottomWidth: 1, borderBottomColor: '#f0f0f0' },
  itemName: { fontWeight: '700', fontSize: 15 },
  itemSku: { color: '#6a6d70', fontSize: 12, marginTop: 2 },
  countCard: { backgroundColor: '#fff', padding: 20, borderWidth: 2, borderColor: '#0070f2' },
  countName: { fontSize: 18, fontWeight: '800' },
  countSku: { color: '#6a6d70', marginBottom: 12 },
  countSystem: { fontSize: 16, marginBottom: 16 },
  countInput: { borderWidth: 2, borderColor: '#0070f2', padding: 16, fontSize: 28, fontWeight: '800', textAlign: 'center', marginBottom: 12 },
  diff: { textAlign: 'center', fontSize: 18, fontWeight: '800', marginBottom: 16 },
  diffPositive: { color: '#107e3e' },
  diffNegative: { color: '#bb0000' },
  diffZero: { color: '#6a6d70' },
  countBtn: { backgroundColor: '#0070f2', padding: 16, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8 },
  countBtnText: { color: '#fff', fontWeight: '700', fontSize: 16 },
  cancelText: { color: '#bb0000', textAlign: 'center', marginTop: 12, fontWeight: '600' },
  historyTitle: { fontSize: 14, fontWeight: '700', color: '#32363a', marginTop: 20, marginBottom: 8 },
  historyItem: { flexDirection: 'row', backgroundColor: '#fff', padding: 12, borderBottomWidth: 1, borderBottomColor: '#f0f0f0' },
});
