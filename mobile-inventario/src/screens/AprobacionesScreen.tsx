import React, { useState, useCallback } from 'react';
import { View, Text, FlatList, StyleSheet, TouchableOpacity, RefreshControl, Alert, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useFocusEffect } from '@react-navigation/native';
import { fetchPendientesAprobacion, aprobarSolicitud } from '../api/client';

export default function AprobacionesScreen({ navigation }: any) {
  const [solicitudes, setSolicitudes] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [procesando, setProcesando] = useState<number | null>(null);

  const cargar = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchPendientesAprobacion();
      setSolicitudes(data.solicitudes || []);
    } catch (e) {
      Alert.alert('Error', 'No se pudieron cargar las aprobaciones.');
    } finally {
      setLoading(false);
    }
  }, []);

  useFocusEffect(useCallback(() => { cargar(); }, [cargar]));

  const procesar = (id: number, accion: 'aprobar' | 'rechazar') => {
    Alert.alert(
      accion === 'aprobar' ? 'Autorizar solicitud' : 'Rechazar solicitud',
      `Solicitud #${id}`,
      [
        { text: 'Cancelar', style: 'cancel' },
        {
          text: accion === 'aprobar' ? 'Autorizar' : 'Rechazar',
          style: accion === 'aprobar' ? 'default' : 'destructive',
          onPress: async () => {
            setProcesando(id);
            try {
              const r = await aprobarSolicitud(id, accion);
              if (r.status === 'success') {
                setSolicitudes(prev => prev.filter(s => s.id !== id));
              } else {
                Alert.alert('Error', r.message || 'No se pudo procesar.');
              }
            } catch (e) {
              Alert.alert('Error', 'No se pudo procesar la solicitud.');
            } finally {
              setProcesando(null);
            }
          },
        },
      ]
    );
  };

  const renderItem = ({ item }: { item: any }) => (
    <View style={styles.card}>
      <TouchableOpacity onPress={() => navigation.navigate('SolicitudDetalle', { id: item.id })}>
        <View style={styles.cardHead}>
          <Text style={styles.cardId}>#{item.id}</Text>
          <Text style={styles.cardFecha}>{item.fecha}</Text>
        </View>
        <Text style={styles.cardSolicitante}>{item.solicitante}</Text>
        <Text style={styles.cardItems}>{item.num_items} materiales{item.orden_trabajo ? ` · ${item.orden_trabajo}` : ''}</Text>
        {!!item.comentarios && <Text style={styles.cardComent} numberOfLines={2}>{item.comentarios}</Text>}
      </TouchableOpacity>
      <View style={styles.actions}>
        <TouchableOpacity
          style={[styles.btn, styles.btnReject]}
          onPress={() => procesar(item.id, 'rechazar')}
          disabled={procesando === item.id}
        >
          <Ionicons name="close" size={18} color="#fff" />
          <Text style={styles.btnText}>Rechazar</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.btn, styles.btnApprove]}
          onPress={() => procesar(item.id, 'aprobar')}
          disabled={procesando === item.id}
        >
          {procesando === item.id
            ? <ActivityIndicator color="#fff" size="small" />
            : <><Ionicons name="checkmark" size={18} color="#fff" /><Text style={styles.btnText}>Autorizar</Text></>}
        </TouchableOpacity>
      </View>
    </View>
  );

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
            <Ionicons name="checkmark-done-circle-outline" size={48} color="#94a3b8" />
            <Text style={styles.emptyText}>No hay solicitudes pendientes de autorización.</Text>
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
  cardFecha: { color: '#6a6d70', fontSize: 12 },
  cardSolicitante: { fontWeight: '700', fontSize: 15, marginTop: 4 },
  cardItems: { color: '#6a6d70', fontSize: 13, marginTop: 2 },
  cardComent: { color: '#475569', fontSize: 13, marginTop: 6, fontStyle: 'italic' },
  actions: { flexDirection: 'row', gap: 10, marginTop: 12 },
  btn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 12 },
  btnApprove: { backgroundColor: '#107e3e' },
  btnReject: { backgroundColor: '#bb0000' },
  btnText: { color: '#fff', fontWeight: '700' },
  emptyWrap: { flexGrow: 1, justifyContent: 'center' },
  empty: { alignItems: 'center', padding: 40 },
  emptyText: { color: '#94a3b8', marginTop: 12, textAlign: 'center' },
});
