import React, { useState, useCallback } from 'react';
import { View, Text, FlatList, StyleSheet, TouchableOpacity, RefreshControl, Alert, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useFocusEffect } from '@react-navigation/native';
import { fetchParaDespacho, despacharSolicitud } from '../api/client';

export default function DespachosScreen({ navigation }: any) {
  const [solicitudes, setSolicitudes] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [procesando, setProcesando] = useState<number | null>(null);

  const cargar = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchParaDespacho();
      setSolicitudes(data.solicitudes || []);
    } catch (e) {
      Alert.alert('Error', 'No se pudieron cargar las solicitudes.');
    } finally {
      setLoading(false);
    }
  }, []);

  useFocusEffect(useCallback(() => { cargar(); }, [cargar]));

  const despachar = (id: number) => {
    Alert.alert('Despachar', `¿Marcar la solicitud #${id} como lista para recolección? Se notificará al solicitante.`, [
      { text: 'Cancelar', style: 'cancel' },
      {
        text: 'Despachar',
        onPress: async () => {
          setProcesando(id);
          try {
            const r = await despacharSolicitud(id);
            if (r.status === 'success') {
              cargar();
            } else {
              Alert.alert('Error', r.message || 'No se pudo despachar.');
            }
          } catch (e) {
            Alert.alert('Error', 'No se pudo despachar.');
          } finally {
            setProcesando(null);
          }
        },
      },
    ]);
  };

  const renderItem = ({ item }: { item: any }) => {
    const listoParaEntrega = item.estado === 'LISTO_RECOLECCION';
    return (
      <View style={styles.card}>
        <TouchableOpacity onPress={() => navigation.navigate('SolicitudDetalle', { id: item.id })}>
          <View style={styles.cardHead}>
            <Text style={styles.cardId}>#{item.id}</Text>
            <View style={[styles.tag, listoParaEntrega ? styles.tagRecoleccion : styles.tagPendiente]}>
              <Text style={[styles.tagText, listoParaEntrega ? styles.tagTextRecoleccion : styles.tagTextPendiente]}>
                {listoParaEntrega ? 'Lista para recolección' : 'Por despachar'}
              </Text>
            </View>
          </View>
          <Text style={styles.cardSolicitante}>{item.solicitante}</Text>
          <Text style={styles.cardItems}>{item.num_items} materiales · {item.ubicacion_origen}</Text>
          {!!item.orden_trabajo && <Text style={styles.cardOt}>{item.orden_trabajo}</Text>}
        </TouchableOpacity>

        {listoParaEntrega ? (
          <TouchableOpacity
            style={[styles.btn, styles.btnConfirm]}
            onPress={() => navigation.navigate('SolicitudDetalle', { id: item.id, confirmar: true })}
          >
            <Ionicons name="checkmark-done-outline" size={18} color="#fff" />
            <Text style={styles.btnText}>Confirmar entrega (con foto)</Text>
          </TouchableOpacity>
        ) : (
          <TouchableOpacity
            style={[styles.btn, styles.btnDispatch]}
            onPress={() => despachar(item.id)}
            disabled={procesando === item.id}
          >
            {procesando === item.id
              ? <ActivityIndicator color="#fff" size="small" />
              : <><Ionicons name="cube-outline" size={18} color="#fff" /><Text style={styles.btnText}>Despachar</Text></>}
          </TouchableOpacity>
        )}
      </View>
    );
  };

  return (
    <View style={styles.container}>
      <FlatList
        data={solicitudes}
        keyExtractor={(item) => String(item.id)}
        renderItem={renderItem}
        contentContainerStyle={solicitudes.length === 0 ? styles.emptyWrap : { padding: 12 }}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={cargar} />}
        ListEmptyComponent={!loading ? (
          <View style={styles.empty}>
            <Ionicons name="file-tray-outline" size={48} color="#94a3b8" />
            <Text style={styles.emptyText}>No hay solicitudes por despachar.</Text>
          </View>
        ) : null}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f7f7f7' },
  card: { backgroundColor: '#fff', borderWidth: 1, borderColor: '#e2e8f0', padding: 14, marginBottom: 10 },
  cardHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  cardId: { fontWeight: '800', fontSize: 16, color: '#0070f2' },
  tag: { paddingHorizontal: 10, paddingVertical: 3 },
  tagPendiente: { backgroundColor: '#fef3c7' },
  tagRecoleccion: { backgroundColor: '#e5f0ff' },
  tagText: { fontSize: 11, fontWeight: '700' },
  tagTextPendiente: { color: '#92400e' },
  tagTextRecoleccion: { color: '#0064d1' },
  cardSolicitante: { fontWeight: '700', fontSize: 15, marginTop: 6 },
  cardItems: { color: '#6a6d70', fontSize: 13, marginTop: 2 },
  cardOt: { color: '#6a6d70', fontSize: 12, marginTop: 2 },
  btn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 12, marginTop: 12 },
  btnDispatch: { backgroundColor: '#0070f2' },
  btnConfirm: { backgroundColor: '#107e3e' },
  btnText: { color: '#fff', fontWeight: '700' },
  emptyWrap: { flexGrow: 1, justifyContent: 'center' },
  empty: { alignItems: 'center', padding: 40 },
  emptyText: { color: '#94a3b8', marginTop: 12, textAlign: 'center' },
});
