import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, Alert } from 'react-native';
import { CameraView, useCameraPermissions } from 'expo-camera';
import { getMaterialById, searchMaterials } from '../db/database';

export default function ScannerScreen() {
  const [permission, requestPermission] = useCameraPermissions();
  const [scanned, setScanned] = useState(false);
  const [result, setResult] = useState<any>(null);

  useEffect(() => {
    if (!permission?.granted) requestPermission();
  }, []);

  const handleBarCodeScanned = async ({ type, data }: { type: string; data: string }) => {
    if (scanned) return;
    setScanned(true);

    // Buscar por SKU o ID
    let material = null;
    const byId = await getMaterialById(parseInt(data));
    if (byId) {
      material = byId;
    } else {
      const bySearch = await searchMaterials(data);
      if (bySearch.length > 0) material = bySearch[0];
    }

    if (material) {
      setResult(material);
    } else {
      Alert.alert('No encontrado', `Código: ${data}\nNo se encontró en el catálogo local.`, [
        { text: 'Escanear otro', onPress: () => setScanned(false) }
      ]);
    }
  };

  if (!permission?.granted) {
    return <View style={styles.center}><Text>Se necesita permiso de cámara</Text></View>;
  }

  return (
    <View style={styles.container}>
      {!result ? (
        <>
          <CameraView
            style={styles.camera}
            barcodeScannerSettings={{ barcodeTypes: ['qr', 'ean13', 'ean8', 'code128', 'code39'] }}
            onBarcodeScanned={scanned ? undefined : handleBarCodeScanned}
          />
          <View style={styles.overlay}>
            <Text style={styles.hint}>Apunta al código QR o de barras</Text>
          </View>
        </>
      ) : (
        <View style={styles.resultCard}>
          <Text style={styles.resultName}>{result.nombre}</Text>
          <Text style={styles.resultSku}>{result.sku}</Text>
          <Text style={styles.resultStock}>Stock: {result.stock_total} {result.unidad}</Text>
          {result.descripcion ? <Text style={styles.resultDesc}>{result.descripcion}</Text> : null}
          <Text style={styles.scanAgain} onPress={() => { setResult(null); setScanned(false); }}>
            ← Escanear otro
          </Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#000' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  camera: { flex: 1 },
  overlay: { position: 'absolute', bottom: 80, left: 0, right: 0, alignItems: 'center' },
  hint: { color: '#fff', fontSize: 16, fontWeight: '600', backgroundColor: 'rgba(0,0,0,0.6)', padding: 12, borderRadius: 8 },
  resultCard: { flex: 1, backgroundColor: '#fff', padding: 24, justifyContent: 'center' },
  resultName: { fontSize: 24, fontWeight: '800', marginBottom: 4 },
  resultSku: { fontSize: 14, color: '#6a6d70', marginBottom: 16 },
  resultStock: { fontSize: 36, fontWeight: '800', color: '#0070f2', marginBottom: 16 },
  resultDesc: { fontSize: 14, color: '#475569', marginBottom: 24 },
  scanAgain: { color: '#0070f2', fontWeight: '700', fontSize: 16 },
});
