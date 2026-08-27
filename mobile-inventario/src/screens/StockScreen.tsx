import React, { useState, useEffect } from 'react';
import { View, Text, TextInput, FlatList, StyleSheet, TouchableOpacity, Modal, Alert } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { CameraView, useCameraPermissions } from 'expo-camera';
import { searchMaterials, getStockByMaterial } from '../db/database';
import { useSync } from '../context/SyncContext';

export default function StockScreen() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<any[]>([]);
  const [selected, setSelected] = useState<any>(null);
  const [stockDetail, setStockDetail] = useState<any[]>([]);
  const { syncAll, lastSync } = useSync();

  // Scanner
  const [scannerOpen, setScannerOpen] = useState(false);
  const [scanned, setScanned] = useState(false);
  const [permission, requestPermission] = useCameraPermissions();

  useEffect(() => {
    if (query.length >= 2) {
      searchMaterials(query).then(setResults);
    } else {
      setResults([]);
    }
  }, [query]);

  const selectMaterial = async (item: any) => {
    setSelected(item);
    const stock = await getStockByMaterial(item.id);
    setStockDetail(stock);
  };

  const abrirScanner = async () => {
    if (!permission?.granted) {
      const res = await requestPermission();
      if (!res.granted) { Alert.alert('Permiso denegado', 'Se necesita acceso a la cámara para escanear.'); return; }
    }
    setScanned(false);
    setScannerOpen(true);
  };

  const onBarcodeScanned = async ({ data }: { data: string }) => {
    if (scanned) return;
    setScanned(true);
    setScannerOpen(false);
    const mats = await searchMaterials(data);
    if (mats.length === 1) {
      selectMaterial(mats[0]);
    } else if (mats.length > 1) {
      setQuery(data);
      setResults(mats);
    } else {
      Alert.alert('No encontrado', `Código "${data}" no coincide con ningún material del catálogo local.`);
    }
  };

  return (
    <View style={styles.container}>
      {/* Search */}
      <View style={styles.searchRow}>
        <Ionicons name="search-outline" size={20} color="#6a6d70" />
        <TextInput style={styles.searchInput} placeholder="Buscar material o escanear..." value={query} onChangeText={setQuery} />
        <TouchableOpacity onPress={abrirScanner}>
          <Ionicons name="barcode-outline" size={24} color="#0070f2" />
        </TouchableOpacity>
      </View>

      {/* Sync button */}
      <TouchableOpacity style={styles.syncBtn} onPress={syncAll}>
        <Ionicons name="cloud-download-outline" size={16} color="#0070f2" />
        <Text style={styles.syncText}>Sincronizar catálogo</Text>
      </TouchableOpacity>

      {/* Results or Detail */}
      {selected ? (
        <View style={styles.detailCard}>
          <TouchableOpacity onPress={() => setSelected(null)}>
            <Text style={styles.backLink}>← Volver</Text>
          </TouchableOpacity>
          <Text style={styles.detailName}>{selected.nombre}</Text>
          <Text style={styles.detailSku}>{selected.sku} · {selected.unidad}</Text>
          <Text style={styles.detailTotal}>Stock Total: {selected.stock_total}</Text>
          <Text style={styles.sectionTitle}>Por Ubicación:</Text>
          {stockDetail.map((s, i) => (
            <View key={i} style={styles.stockRow}>
              <Text style={styles.stockLocation}>{s.location_name}</Text>
              <Text style={styles.stockQty}>{s.cantidad}</Text>
            </View>
          ))}
          {stockDetail.length === 0 && <Text style={styles.empty}>Sin detalle por ubicación</Text>}
        </View>
      ) : (
        <FlatList
          data={results}
          keyExtractor={(item) => String(item.id)}
          renderItem={({ item }) => (
            <TouchableOpacity style={styles.item} onPress={() => selectMaterial(item)}>
              <View style={{ flex: 1 }}>
                <Text style={styles.itemName}>{item.nombre}</Text>
                <Text style={styles.itemSku}>{item.sku} · {item.unidad}</Text>
              </View>
              <Text style={styles.itemStock}>{item.stock_total}</Text>
            </TouchableOpacity>
          )}
          ListEmptyComponent={query.length >= 2 ? <Text style={styles.empty}>Sin resultados</Text> : null}
        />
      )}

      {/* Modal del Scanner */}
      <Modal visible={scannerOpen} animationType="slide" onRequestClose={() => setScannerOpen(false)}>
        <View style={{ flex: 1, backgroundColor: '#000' }}>
          {permission?.granted ? (
            <CameraView
              style={{ flex: 1 }}
              barcodeScannerSettings={{ barcodeTypes: ['qr', 'ean13', 'ean8', 'code128', 'code39', 'upc_a', 'upc_e'] }}
              onBarcodeScanned={scanned ? undefined : onBarcodeScanned}
            />
          ) : (
            <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
              <Text style={{ color: '#fff' }}>Sin permiso de cámara</Text>
            </View>
          )}
          <View style={{ position: 'absolute', bottom: 60, left: 0, right: 0, alignItems: 'center' }}>
            <Text style={{ color: '#fff', fontSize: 16, fontWeight: '600', backgroundColor: 'rgba(0,0,0,0.6)', padding: 12 }}>
              Apunta al código de barras
            </Text>
          </View>
          <TouchableOpacity
            style={{ position: 'absolute', top: 50, right: 20, backgroundColor: 'rgba(0,0,0,0.6)', padding: 10, borderRadius: 20 }}
            onPress={() => setScannerOpen(false)}
          >
            <Ionicons name="close" size={24} color="#fff" />
          </TouchableOpacity>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f7f7f7', padding: 16 },
  searchRow: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#fff', borderWidth: 1, borderColor: '#d9d9d9', padding: 12, marginBottom: 12, gap: 8 },
  searchInput: { flex: 1, fontSize: 16 },
  syncBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 12 },
  syncText: { color: '#0070f2', fontWeight: '600', fontSize: 13 },
  item: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#fff', padding: 14, borderBottomWidth: 1, borderBottomColor: '#f0f0f0' },
  itemName: { fontWeight: '700', fontSize: 15 },
  itemSku: { color: '#6a6d70', fontSize: 12, marginTop: 2 },
  itemStock: { fontSize: 24, fontWeight: '800', color: '#0070f2' },
  detailCard: { backgroundColor: '#fff', padding: 20, borderWidth: 1, borderColor: '#d9d9d9' },
  backLink: { color: '#0070f2', fontWeight: '600', marginBottom: 12 },
  detailName: { fontSize: 20, fontWeight: '800' },
  detailSku: { color: '#6a6d70', marginBottom: 8 },
  detailTotal: { fontSize: 28, fontWeight: '800', color: '#107e3e', marginVertical: 12 },
  sectionTitle: { fontSize: 13, fontWeight: '700', color: '#6a6d70', textTransform: 'uppercase', marginTop: 16, marginBottom: 8 },
  stockRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: '#f0f0f0' },
  stockLocation: { fontSize: 14 },
  stockQty: { fontSize: 16, fontWeight: '700' },
  empty: { textAlign: 'center', color: '#94a3b8', marginTop: 40, fontSize: 14 },
});
