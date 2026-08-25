import React, { useState, useEffect } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet, Alert, ScrollView } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { searchMaterials, getLocations, addPendingOperation } from '../db/database';
import { useSync } from '../context/SyncContext';

export default function TransferScreen() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<any[]>([]);
  const [material, setMaterial] = useState<any>(null);
  const [locations, setLocations] = useState<any[]>([]);
  const [origen, setOrigen] = useState<any>(null);
  const [destino, setDestino] = useState<any>(null);
  const [cantidad, setCantidad] = useState('');
  const [showLocPicker, setShowLocPicker] = useState<'origen' | 'destino' | null>(null);
  const { refreshPendingCount } = useSync();

  useEffect(() => {
    getLocations().then(setLocations);
  }, []);

  const buscar = async () => {
    if (query.length < 2) return;
    const r = await searchMaterials(query);
    setResults(r);
  };

  const registrarTransferencia = async () => {
    if (!material) { Alert.alert('Error', 'Seleccione un material'); return; }
    if (!origen || !destino) { Alert.alert('Error', 'Seleccione origen y destino'); return; }
    if (origen.id === destino.id) { Alert.alert('Error', 'Origen y destino no pueden ser iguales'); return; }
    if (!cantidad || parseFloat(cantidad) <= 0) { Alert.alert('Error', 'Ingrese cantidad válida'); return; }

    await addPendingOperation('TRANSFERENCIA', {
      material_id: material.id,
      material_nombre: material.nombre,
      cantidad: parseFloat(cantidad),
      origen_id: origen.id,
      origen_nombre: origen.nombre,
      destino_id: destino.id,
      destino_nombre: destino.nombre,
      timestamp: new Date().toISOString(),
    });

    await refreshPendingCount();
    Alert.alert('Registrado', `Transferencia de ${cantidad} ${material.unidad} de "${origen.nombre}" → "${destino.nombre}" guardada. Se sincronizará con conexión.`);
    setMaterial(null);
    setOrigen(null);
    setDestino(null);
    setCantidad('');
    setQuery('');
  };

  return (
    <ScrollView style={styles.container}>
      <Text style={styles.title}>Transferencia de Material</Text>

      {/* Material search */}
      <View style={styles.searchRow}>
        <TextInput style={styles.searchInput} placeholder="Buscar material..." value={query} onChangeText={setQuery} onSubmitEditing={buscar} />
        <TouchableOpacity onPress={buscar} style={styles.searchBtn}><Ionicons name="search" size={20} color="#fff" /></TouchableOpacity>
      </View>

      {!material && results.map(item => (
        <TouchableOpacity key={item.id} style={styles.item} onPress={() => { setMaterial(item); setResults([]); }}>
          <Text style={styles.itemName}>{item.nombre}</Text>
          <Text style={styles.itemSku}>{item.sku} · Stock: {item.stock_total}</Text>
        </TouchableOpacity>
      ))}

      {material && (
        <View style={styles.form}>
          <View style={styles.materialBadge}>
            <Text style={styles.materialName}>{material.nombre}</Text>
            <TouchableOpacity onPress={() => setMaterial(null)}><Ionicons name="close-circle" size={22} color="#bb0000" /></TouchableOpacity>
          </View>

          {/* Origen */}
          <Text style={styles.label}>Origen:</Text>
          <TouchableOpacity style={styles.locBtn} onPress={() => setShowLocPicker('origen')}>
            <Text style={origen ? styles.locSelected : styles.locPlaceholder}>{origen ? origen.nombre : 'Seleccionar origen...'}</Text>
          </TouchableOpacity>

          {/* Destino */}
          <Text style={styles.label}>Destino:</Text>
          <TouchableOpacity style={styles.locBtn} onPress={() => setShowLocPicker('destino')}>
            <Text style={destino ? styles.locSelected : styles.locPlaceholder}>{destino ? destino.nombre : 'Seleccionar destino...'}</Text>
          </TouchableOpacity>

          {/* Cantidad */}
          <Text style={styles.label}>Cantidad:</Text>
          <TextInput style={styles.qtyInput} placeholder="0" keyboardType="decimal-pad" value={cantidad} onChangeText={setCantidad} />

          <TouchableOpacity style={styles.submitBtn} onPress={registrarTransferencia}>
            <Ionicons name="swap-horizontal" size={20} color="#fff" />
            <Text style={styles.submitText}>Registrar Transferencia</Text>
          </TouchableOpacity>
        </View>
      )}

      {/* Location picker */}
      {showLocPicker && (
        <View style={styles.pickerOverlay}>
          <View style={styles.picker}>
            <Text style={styles.pickerTitle}>Seleccionar {showLocPicker === 'origen' ? 'Origen' : 'Destino'}</Text>
            <ScrollView style={{ maxHeight: 300 }}>
              {locations.map(loc => (
                <TouchableOpacity key={loc.id} style={styles.pickerItem} onPress={() => {
                  if (showLocPicker === 'origen') setOrigen(loc);
                  else setDestino(loc);
                  setShowLocPicker(null);
                }}>
                  <Text>{loc.nombre}</Text>
                </TouchableOpacity>
              ))}
            </ScrollView>
            <TouchableOpacity onPress={() => setShowLocPicker(null)}><Text style={styles.cancelText}>Cancelar</Text></TouchableOpacity>
          </View>
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f7f7f7', padding: 16 },
  title: { fontSize: 18, fontWeight: '800', marginBottom: 16 },
  searchRow: { flexDirection: 'row', gap: 8, marginBottom: 12 },
  searchInput: { flex: 1, backgroundColor: '#fff', borderWidth: 1, borderColor: '#d9d9d9', padding: 12, fontSize: 16 },
  searchBtn: { backgroundColor: '#0070f2', padding: 12, justifyContent: 'center' },
  item: { backgroundColor: '#fff', padding: 14, borderBottomWidth: 1, borderBottomColor: '#f0f0f0' },
  itemName: { fontWeight: '700', fontSize: 15 },
  itemSku: { color: '#6a6d70', fontSize: 12, marginTop: 2 },
  form: { backgroundColor: '#fff', padding: 20, borderWidth: 1, borderColor: '#d9d9d9', marginTop: 8 },
  materialBadge: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, paddingBottom: 12, borderBottomWidth: 1, borderBottomColor: '#f0f0f0' },
  materialName: { fontSize: 16, fontWeight: '800' },
  label: { fontSize: 12, fontWeight: '700', color: '#6a6d70', textTransform: 'uppercase', marginBottom: 4, marginTop: 12 },
  locBtn: { borderWidth: 1, borderColor: '#d9d9d9', padding: 14 },
  locSelected: { fontSize: 15, fontWeight: '600' },
  locPlaceholder: { fontSize: 15, color: '#94a3b8' },
  qtyInput: { borderWidth: 2, borderColor: '#0070f2', padding: 14, fontSize: 24, fontWeight: '800', textAlign: 'center', marginTop: 4 },
  submitBtn: { backgroundColor: '#0070f2', padding: 16, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, marginTop: 20 },
  submitText: { color: '#fff', fontWeight: '700', fontSize: 16 },
  pickerOverlay: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'center', padding: 24 },
  picker: { backgroundColor: '#fff', padding: 20, borderRadius: 8 },
  pickerTitle: { fontSize: 16, fontWeight: '800', marginBottom: 12 },
  pickerItem: { padding: 14, borderBottomWidth: 1, borderBottomColor: '#f0f0f0' },
  cancelText: { color: '#bb0000', textAlign: 'center', marginTop: 12, fontWeight: '600' },
});
