import React, { useState, useCallback, useRef } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, Alert, ActivityIndicator, Modal, Image, TextInput } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useFocusEffect } from '@react-navigation/native';
import { CameraView, useCameraPermissions } from 'expo-camera';
import { fetchSolicitudDetalle, confirmarEntrega } from '../api/client';
import { useAuth } from '../context/AuthContext';

const ESTADO_LABEL: Record<string, string> = {
  BORRADOR: 'Borrador',
  PENDIENTE_AUTORIZACION: 'Pendiente de autorización',
  PENDIENTE: 'Por despachar',
  LISTO_RECOLECCION: 'Lista para recolección',
  ENTREGADO: 'Entregado',
  RECHAZADO: 'Rechazado',
};

export default function SolicitudDetalleScreen({ route, navigation }: any) {
  const { id, confirmar } = route.params || {};
  const { user } = useAuth();
  const esAlmacen = user?.rol === 'almacen';

  const [sol, setSol] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [guardando, setGuardando] = useState(false);

  // Confirmación de entrega
  const [recibeNombre, setRecibeNombre] = useState('');
  const [fotoBase64, setFotoBase64] = useState<string | null>(null);
  const [camOpen, setCamOpen] = useState(false);
  const [permission, requestPermission] = useCameraPermissions();
  const cameraRef = useRef<CameraView>(null);

  const cargar = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchSolicitudDetalle(id);
      setSol(data.solicitud);
    } catch (e) {
      Alert.alert('Error', 'No se pudo cargar la solicitud.');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useFocusEffect(useCallback(() => { cargar(); }, [cargar]));

  const abrirCamara = async () => {
    if (!permission?.granted) {
      const res = await requestPermission();
      if (!res.granted) { Alert.alert('Permiso denegado', 'Se necesita la cámara para la foto de entrega.'); return; }
    }
    setCamOpen(true);
  };

  const tomarFoto = async () => {
    if (!cameraRef.current) return;
    try {
      const foto = await cameraRef.current.takePictureAsync({ quality: 0.5, base64: true });
      setFotoBase64(foto?.base64 || null);
      setCamOpen(false);
    } catch (e) {
      Alert.alert('Error', 'No se pudo tomar la foto.');
    }
  };

  const enviarConfirmacion = async () => {
    if (!fotoBase64) { Alert.alert('Foto requerida', 'Toma una foto de quién recibe el material.'); return; }
    if (!recibeNombre.trim()) { Alert.alert('Falta el nombre', 'Indica quién recibe el material.'); return; }
    setGuardando(true);
    try {
      const r = await confirmarEntrega(id, { recibe_nombre: recibeNombre.trim(), foto_base64: fotoBase64 });
      if (r.status === 'success') {
        Alert.alert('Entrega confirmada', r.message || 'La solicitud fue entregada.', [
          { text: 'OK', onPress: () => navigation.goBack() },
        ]);
      } else {
        Alert.alert('Error', r.message || 'No se pudo confirmar la entrega.');
      }
    } catch (e) {
      Alert.alert('Error', 'No se pudo confirmar la entrega.');
    } finally {
      setGuardando(false);
    }
  };

  if (loading || !sol) {
    return <View style={styles.center}><ActivityIndicator size="large" color="#0070f2" /></View>;
  }

  const mostrarConfirmacion = esAlmacen && confirmar && sol.estado === 'LISTO_RECOLECCION';

  return (
    <ScrollView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.hId}>Solicitud #{sol.id}</Text>
        <Text style={styles.hEstado}>{ESTADO_LABEL[sol.estado] || sol.estado}</Text>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Información</Text>
        <Row label="Solicitante" value={sol.solicitante} />
        <Row label="Fecha" value={sol.fecha} />
        <Row label="Bodega origen" value={sol.ubicacion_origen || '—'} />
        <Row label="Orden de trabajo" value={sol.orden_trabajo || '—'} />
        {!!sol.autorizado_por && <Row label="Autorizado por" value={sol.autorizado_por} />}
        {!!sol.comentarios && <Row label="Comentarios" value={sol.comentarios} />}
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Materiales ({sol.items?.length || 0})</Text>
        {(sol.items || []).map((it: any, i: number) => (
          <View key={i} style={styles.itemRow}>
            <View style={{ flex: 1 }}>
              <Text style={styles.itemName}>{it.material_nombre}</Text>
              <Text style={styles.itemSku}>{it.sku}</Text>
            </View>
            <Text style={styles.itemQty}>{it.cantidad} {it.unidad}</Text>
          </View>
        ))}
      </View>

      {mostrarConfirmacion && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Confirmar entrega</Text>
          <Text style={styles.label}>¿Quién recibe el material?</Text>
          <TextInput
            style={styles.input}
            placeholder="Nombre de quien recibe"
            value={recibeNombre}
            onChangeText={setRecibeNombre}
          />

          {fotoBase64 ? (
            <View style={styles.fotoWrap}>
              <Image source={{ uri: `data:image/jpeg;base64,${fotoBase64}` }} style={styles.foto} />
              <TouchableOpacity style={styles.retomar} onPress={abrirCamara}>
                <Ionicons name="camera-reverse-outline" size={16} color="#0070f2" />
                <Text style={styles.retomarText}>Volver a tomar</Text>
              </TouchableOpacity>
            </View>
          ) : (
            <TouchableOpacity style={styles.fotoBtn} onPress={abrirCamara}>
              <Ionicons name="camera-outline" size={22} color="#0070f2" />
              <Text style={styles.fotoBtnText}>Tomar foto de quién recibe</Text>
            </TouchableOpacity>
          )}

          <TouchableOpacity style={[styles.confirmBtn, guardando && { opacity: 0.6 }]} onPress={enviarConfirmacion} disabled={guardando}>
            {guardando ? <ActivityIndicator color="#fff" /> : <><Ionicons name="checkmark-done-outline" size={20} color="#fff" /><Text style={styles.confirmBtnText}>Confirmar Entrega</Text></>}
          </TouchableOpacity>
        </View>
      )}

      {/* Cámara */}
      <Modal visible={camOpen} animationType="slide" onRequestClose={() => setCamOpen(false)}>
        <View style={{ flex: 1, backgroundColor: '#000' }}>
          {permission?.granted ? (
            <CameraView ref={cameraRef} style={{ flex: 1 }} facing="back" />
          ) : (
            <View style={styles.center}><Text style={{ color: '#fff' }}>Sin permiso de cámara</Text></View>
          )}
          <View style={styles.camControls}>
            <TouchableOpacity style={styles.shutter} onPress={tomarFoto}>
              <Ionicons name="camera" size={30} color="#000" />
            </TouchableOpacity>
          </View>
          <TouchableOpacity style={styles.camClose} onPress={() => setCamOpen(false)}>
            <Ionicons name="close" size={26} color="#fff" />
          </TouchableOpacity>
        </View>
      </Modal>
    </ScrollView>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.row}>
      <Text style={styles.rowLabel}>{label}</Text>
      <Text style={styles.rowValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f7f7f7' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#f7f7f7' },
  header: { backgroundColor: '#354a5f', padding: 20 },
  hId: { color: '#fff', fontSize: 20, fontWeight: '800' },
  hEstado: { color: '#c9d4df', fontSize: 13, marginTop: 4 },
  section: { backgroundColor: '#fff', borderWidth: 1, borderColor: '#e2e8f0', margin: 12, marginBottom: 0, padding: 14 },
  sectionTitle: { fontWeight: '800', fontSize: 14, marginBottom: 10, color: '#32363a' },
  row: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 6, borderBottomWidth: 1, borderBottomColor: '#f0f0f0' },
  rowLabel: { color: '#6a6d70', fontSize: 13 },
  rowValue: { fontWeight: '600', fontSize: 13, flexShrink: 1, textAlign: 'right', marginLeft: 12 },
  itemRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: '#f0f0f0' },
  itemName: { fontWeight: '600', fontSize: 14 },
  itemSku: { color: '#6a6d70', fontSize: 12 },
  itemQty: { fontWeight: '700', fontSize: 14, color: '#0070f2' },
  label: { fontSize: 13, color: '#6a6d70', marginBottom: 6 },
  input: { borderWidth: 1, borderColor: '#d9d9d9', padding: 12, fontSize: 15, marginBottom: 12 },
  fotoBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, borderWidth: 2, borderColor: '#0070f2', borderStyle: 'dashed', padding: 16, marginBottom: 12 },
  fotoBtnText: { color: '#0070f2', fontWeight: '700' },
  fotoWrap: { marginBottom: 12, alignItems: 'center' },
  foto: { width: '100%', height: 220, borderRadius: 4 },
  retomar: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 8 },
  retomarText: { color: '#0070f2', fontWeight: '600' },
  confirmBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#107e3e', padding: 16, marginTop: 4, marginBottom: 20 },
  confirmBtnText: { color: '#fff', fontWeight: '700', fontSize: 16 },
  camControls: { position: 'absolute', bottom: 40, left: 0, right: 0, alignItems: 'center' },
  shutter: { width: 70, height: 70, borderRadius: 35, backgroundColor: '#fff', justifyContent: 'center', alignItems: 'center' },
  camClose: { position: 'absolute', top: 50, right: 20, backgroundColor: 'rgba(0,0,0,0.6)', padding: 10, borderRadius: 20 },
});
