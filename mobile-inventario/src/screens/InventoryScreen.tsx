import React, { useState, useEffect } from 'react';
import { View, Text, TextInput, TouchableOpacity, FlatList, StyleSheet, Alert, ScrollView } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { addInventoryCount, getCountsBySession, getWarehouseLocations, getMaterialsByLocation, searchCatalogForLocation } from '../db/database';
import { useSync } from '../context/SyncContext';

export default function InventoryScreen() {
  const [sessionId] = useState(() => `INV-${Date.now()}`);
  const [step, setStep] = useState<'location' | 'materials'>('location');

  // Ubicaciones
  const [locations, setLocations] = useState<any[]>([]);
  const [selectedLocation, setSelectedLocation] = useState<any>(null);

  // Materiales de la ubicación
  const [query, setQuery] = useState('');
  const [materials, setMaterials] = useState<any[]>([]);
  const [selectedMaterial, setSelectedMaterial] = useState<any>(null);
  const [cantidadContada, setCantidadContada] = useState('');

  // Conteos
  const [counts, setCounts] = useState<any[]>([]);
  const { refreshPendingCount } = useSync();

  useEffect(() => {
    loadLocations();
    loadCounts();
  }, []);

  const loadLocations = async () => {
    const locs = await getWarehouseLocations();
    setLocations(locs);
  };

  const loadCounts = async () => {
    const c = await getCountsBySession(sessionId);
    setCounts(c);
  };

  const selectLocation = async (loc: any) => {
    setSelectedLocation(loc);
    setStep('materials');
    const mats = await getMaterialsByLocation(loc.id);
    setMaterials(mats);
  };

  const buscarEnUbicacion = async (text: string) => {
    setQuery(text);
    if (!selectedLocation) return;
    if (text.trim().length === 0) {
      // Sin texto: mostrar solo los que tienen stock en la ubicación
      const mats = await getMaterialsByLocation(selectedLocation.id);
      setMaterials(mats);
    } else {
      // Con texto: buscar en TODO el catálogo (permite agregar nuevos a la ubicación)
      const mats = await searchCatalogForLocation(selectedLocation.id, text);
      setMaterials(mats);
    }
  };

  const registrarConteo = async () => {
    if (!selectedMaterial || !selectedLocation) return;
    const contada = parseFloat(cantidadContada);
    if (isNaN(contada) || contada < 0) { Alert.alert('Error', 'Cantidad inválida'); return; }

    await addInventoryCount(
      sessionId,
      selectedMaterial.id,
      selectedLocation.id,
      selectedMaterial.stock_ubicacion || 0,
      contada
    );

    await loadCounts();
    await refreshPendingCount();
    setSelectedMaterial(null);
    setCantidadContada('');
    setQuery('');
    // Refrescar materiales de la ubicación (los que tienen stock)
    const mats = await getMaterialsByLocation(selectedLocation.id);
    setMaterials(mats);
    Alert.alert('Registrado', 'Conteo guardado. Se sincronizará con conexión.');
  };

  const volverAUbicaciones = () => {
    setStep('location');
    setSelectedLocation(null);
    setSelectedMaterial(null);
    setQuery('');
    setMaterials([]);
  };

  const diferencia = selectedMaterial ? (parseFloat(cantidadContada || '0') - (selectedMaterial.stock_ubicacion || 0)) : 0;

  // ===== PASO 1: SELECCIONAR UBICACIÓN =====
  if (step === 'location') {
    return (
      <View style={styles.container}>
        <Text style={styles.sessionLabel}>Sesión: {sessionId}</Text>
        <Text style={styles.stepTitle}>1. Selecciona la Ubicación a Contar</Text>

        <FlatList
          data={locations}
          keyExtractor={(item) => String(item.id)}
          renderItem={({ item }) => (
            <TouchableOpacity style={styles.locItem} onPress={() => selectLocation(item)}>
              <Ionicons name="business-outline" size={22} color="#0070f2" style={{ marginRight: 12 }} />
              <View style={{ flex: 1 }}>
                <Text style={styles.itemName}>{item.nombre}</Text>
                {item.tipo ? <Text style={styles.itemSku}>{item.tipo}</Text> : null}
              </View>
              <Ionicons name="chevron-forward" size={20} color="#ccc" />
            </TouchableOpacity>
          )}
          ListEmptyComponent={
            <View style={styles.empty}>
              <Ionicons name="business-outline" size={40} color="#ccc" />
              <Text style={{ color: '#94a3b8', marginTop: 8 }}>No hay ubicaciones. Sincroniza primero.</Text>
            </View>
          }
        />

        {counts.length > 0 && (
          <View style={styles.countsBanner}>
            <Ionicons name="checkmark-done-circle" size={18} color="#107e3e" />
            <Text style={{ color: '#107e3e', fontWeight: '700', marginLeft: 6 }}>{counts.length} conteo(s) en esta sesión</Text>
          </View>
        )}
      </View>
    );
  }

  // ===== PASO 2: MATERIALES DE LA UBICACIÓN =====
  return (
    <View style={styles.container}>
      <TouchableOpacity style={styles.backRow} onPress={volverAUbicaciones}>
        <Ionicons name="arrow-back" size={20} color="#0070f2" />
        <Text style={styles.backText}>Cambiar ubicación</Text>
      </TouchableOpacity>

      <View style={styles.locHeader}>
        <Ionicons name="business" size={18} color="#0070f2" />
        <Text style={styles.locHeaderText}>{selectedLocation?.nombre}</Text>
      </View>

      {!selectedMaterial && (
        <>
          <View style={styles.searchRow}>
            <TextInput
              style={styles.searchInput}
              placeholder="Buscar cualquier material del catálogo..."
              value={query}
              onChangeText={buscarEnUbicacion}
            />
            <Ionicons name="search" size={20} color="#0070f2" style={{ alignSelf: 'center', marginLeft: 8 }} />
          </View>

          {query.trim().length === 0 && (
            <Text style={styles.hintText}>Mostrando materiales con existencia. Busca para agregar cualquier otro material a esta ubicación.</Text>
          )}

          <FlatList
            data={materials}
            keyExtractor={(item) => String(item.id)}
            renderItem={({ item }) => (
              <TouchableOpacity style={styles.item} onPress={() => { setSelectedMaterial(item); }}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.itemName}>{item.nombre}</Text>
                  <Text style={styles.itemSku}>{item.sku}</Text>
                </View>
                <View style={{ alignItems: 'flex-end' }}>
                  <Text style={[styles.stockBig, item.stock_ubicacion == 0 ? { color: '#94a3b8' } : null]}>{item.stock_ubicacion}</Text>
                  <Text style={styles.itemSku}>sistema</Text>
                </View>
              </TouchableOpacity>
            )}
            ListEmptyComponent={
              <View style={styles.empty}>
                <Ionicons name="cube-outline" size={40} color="#ccc" />
                <Text style={{ color: '#94a3b8', marginTop: 8 }}>
                  {query.trim().length > 0 ? 'No se encontraron materiales.' : 'Sin materiales con existencia. Busca para agregar.'}
                </Text>
              </View>
            }
          />
        </>
      )}

      {/* Formulario de conteo */}
      {selectedMaterial && (
        <ScrollView>
          <View style={styles.countCard}>
            <Text style={styles.countName}>{selectedMaterial.nombre}</Text>
            <Text style={styles.countSku}>{selectedMaterial.sku}</Text>
            <Text style={styles.countSystem}>Stock Sistema ({selectedLocation?.nombre}): <Text style={{ fontWeight: '800' }}>{selectedMaterial.stock_ubicacion}</Text></Text>
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
        </ScrollView>
      )}

      {/* Historial */}
      {counts.length > 0 && !selectedMaterial && (
        <>
          <Text style={styles.historyTitle}>Conteos registrados ({counts.length})</Text>
          <FlatList
            data={counts}
            keyExtractor={(_, i) => String(i)}
            style={{ maxHeight: 200 }}
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
  stepTitle: { fontSize: 15, fontWeight: '800', color: '#32363a', marginBottom: 12 },
  backRow: { flexDirection: 'row', alignItems: 'center', marginBottom: 8 },
  backText: { color: '#0070f2', fontWeight: '600', marginLeft: 4 },
  locHeader: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#eff6ff', padding: 12, marginBottom: 12, gap: 8 },
  locHeaderText: { fontSize: 16, fontWeight: '800', color: '#0070f2' },
  locItem: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#fff', padding: 16, borderBottomWidth: 1, borderBottomColor: '#f0f0f0' },
  searchRow: { flexDirection: 'row', backgroundColor: '#fff', borderWidth: 1, borderColor: '#d9d9d9', paddingHorizontal: 12, marginBottom: 12 },
  searchInput: { flex: 1, paddingVertical: 12, fontSize: 16 },
  item: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#fff', padding: 14, borderBottomWidth: 1, borderBottomColor: '#f0f0f0' },
  itemName: { fontWeight: '700', fontSize: 15 },
  itemSku: { color: '#6a6d70', fontSize: 12, marginTop: 2 },
  stockBig: { fontSize: 20, fontWeight: '800', color: '#0070f2' },
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
  empty: { alignItems: 'center', padding: 40 },
  countsBanner: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#f0fdf4', padding: 12, marginTop: 12 },
  hintText: { fontSize: 11, color: '#94a3b8', marginBottom: 8, fontStyle: 'italic' },
});
