import React, { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet, Alert, ScrollView } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { searchMaterials, addPendingOperation } from '../db/database';
import { useSync } from '../context/SyncContext';

export default function DispatchScreen() {
  const [mode, setMode] = useState<'dispatch' | 'receive'>('dispatch');
  const [query, setQuery] = useState('');
  const [material, setMaterial] = useState<any>(null);
  const [cantidad, setCantidad] = useState('');
  const [results, setResults] = useState<any[]>([]);
  const { refreshPendingCount } = useSync();

  const buscar = async () => {
    if (query.length < 2) return;
    const r = await searchMaterials(query);
    setResults(r);
  };

  const registrar = async () => {
    if (!material) { Alert.alert('Error', 'Seleccione un material'); return; }
    if (!cantidad || parseFloat(cantidad) <= 0) { Alert.alert('Error', 'Ingrese cantidad válida'); return; }

    await addPendingOperation(mode === 'dispatch' ? 'SALIDA' : 'ENTRADA', {
      material_id: material.id,
      material_nombre: material.nombre,
      cantidad: parseFloat(cantidad),
      timestamp: new Date().toISOString(),
    });

    await refreshPendingCount();
    Alert.alert('Registrado', `${mode === 'dispatch' ? 'Salida' : 'Entrada'} de ${cantidad} ${material.unidad} de ${material.nombre} guardada. Se sincronizará cuando haya conexión.`);
    setMaterial(null);
    setCantidad('');
    setQuery('');
    setResults([]);
  };

  return (
    <ScrollView style={styles.container}>
      {/* Toggle */}
      <View style={styles.toggle}>
        <TouchableOpacity style={[styles.toggleBtn, mode === 'dispatch' && styles.toggleActive]} onPress={() => setMode('dispatch')}>
          <Ionicons name="arrow-up-circle-outline" size={18} color={mode === 'dispatch' ? '#fff' : '#0070f2'} />
          <Text style={[styles.toggleText, mode === 'dispatch' && styles.toggleTextActive]}>Despacho</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[styles.toggleBtn, mode === 'receive' && styles.toggleActive]} onPress={() => setMode('receive')}>
          <Ionicons name="arrow-down-circle-outline" size={18} color={mode === 'receive' ? '#fff' : '#107e3e'} />
          <Text style={[styles.toggleText, mode === 'receive' && styles.toggleTextActive]}>Recepción</Text>
        </TouchableOpacity>
      </View>

      {/* Search */}
      <View style={styles.searchRow}>
        <TextInput style={styles.searchInput} placeholder="Buscar material..." value={query} onChangeText={setQuery} onSubmitEditing={buscar} />
        <TouchableOpacity onPress={buscar} style={styles.searchBtn}><Ionicons name="search" size={20} color="#fff" /></TouchableOpacity>
      </View>

      {/* Results */}
      {!material && results.map(item => (
        <TouchableOpacity key={item.id} style={styles.item} onPress={() => { setMaterial(item); setResults([]); }}>
          <Text style={styles.itemName}>{item.nombre}</Text>
          <Text style={styles.itemSku}>{item.sku} · Stock: {item.stock_total}</Text>
        </TouchableOpacity>
      ))}

      {/* Selected + Qty */}
      {material && (
        <View style={styles.selectedCard}>
          <Text style={styles.selectedName}>{material.nombre}</Text>
          <Text style={styles.selectedSku}>{material.sku} · {material.unidad}</Text>
          <TextInput style={styles.qtyInput} placeholder="Cantidad" keyboardType="decimal-pad" value={cantidad} onChangeText={setCantidad} />
          <TouchableOpacity style={[styles.actionBtn, mode === 'receive' && { backgroundColor: '#107e3e' }]} onPress={registrar}>
            <Ionicons name={mode === 'dispatch' ? 'arrow-up-circle' : 'arrow-down-circle'} size={20} color="#fff" />
            <Text style={styles.actionText}>{mode === 'dispatch' ? 'Registrar Salida' : 'Registrar Entrada'}</Text>
          </TouchableOpacity>
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f7f7f7', padding: 16 },
  toggle: { flexDirection: 'row', marginBottom: 16, gap: 8 },
  toggleBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, padding: 12, borderWidth: 2, borderColor: '#0070f2' },
  toggleActive: { backgroundColor: '#0070f2' },
  toggleText: { fontWeight: '700', color: '#0070f2' },
  toggleTextActive: { color: '#fff' },
  searchRow: { flexDirection: 'row', gap: 8, marginBottom: 12 },
  searchInput: { flex: 1, backgroundColor: '#fff', borderWidth: 1, borderColor: '#d9d9d9', padding: 12, fontSize: 16 },
  searchBtn: { backgroundColor: '#0070f2', padding: 12, justifyContent: 'center' },
  item: { backgroundColor: '#fff', padding: 14, borderBottomWidth: 1, borderBottomColor: '#f0f0f0' },
  itemName: { fontWeight: '700', fontSize: 15 },
  itemSku: { color: '#6a6d70', fontSize: 12, marginTop: 2 },
  selectedCard: { backgroundColor: '#fff', padding: 20, borderWidth: 1, borderColor: '#d9d9d9', marginTop: 8 },
  selectedName: { fontSize: 18, fontWeight: '800' },
  selectedSku: { color: '#6a6d70', marginBottom: 16 },
  qtyInput: { borderWidth: 2, borderColor: '#0070f2', padding: 14, fontSize: 24, fontWeight: '800', textAlign: 'center', marginBottom: 16 },
  actionBtn: { backgroundColor: '#0070f2', padding: 16, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8 },
  actionText: { color: '#fff', fontWeight: '700', fontSize: 16 },
});
