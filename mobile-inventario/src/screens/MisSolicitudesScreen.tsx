import React, { useState, useCallback } from 'react';
import { View, Text, FlatList, StyleSheet, TouchableOpacity, RefreshControl, Alert } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useFocusEffect } from '@react-navigation/native';
import { fetchMisSolicitudes } from '../api/client';

const ESTADO_STYLE: Record<string, { bg: string; color: string; label: string }> = {
  BORRADOR: { bg: '#f1f5f9', color: '#475569', label: 'Borrador' },
  PENDIENTE_AUTORIZACION: { bg: '#eff6ff', color: '#1d4ed8', label: 'Pend. autorización' },
  PENDIENTE: { bg: '#fef3c7', color: '#92400e', label: 'Por despachar' },
  LISTO_RECOLECCION: { bg: '#e5f0ff', color: '#0064d1', label: 'Lista p/ recolección' },
  ENTREGADO: { bg: '#dcfce7', color: '#166534', label: 'Entregado' },
  RECHAZADO: { bg: '#fee2e2', color: '#991b1b', label: 'Rechazado' },
};

export default function MisSolicitudesScreen({ navigation }: any) {
  const [solicitudes, setSolicitudes] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const cargar = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchMisSolicitudes();
      setSolicitudes(data.solicitudes || []);
    } catch (e) {
      Alert.alert('Error', 'No se pudieron cargar tus solicitudes.');
    } finally {
      setLoading(false);
    }
  }, []);

  useFocusEffect(useCallback(() => { cargar(); }, [cargar]));

  const renderItem = ({ item }: { item: any }) => {
    const est = ESTADO_STYLE[item.estado] || { bg: '#f1f5f9', color: '#475569', label: item.estado };
    return (
      <TouchableOpacity style={styles.card} onPress={() => navigation.navigate('SolicitudDetalle', { id: item.id })}>
        <View style={styles.cardHead}>
          <Text style={styles.cardId}>#{item.id}</Text>
          <View style={[styles.tag, { backgroundColor: est.bg }]}>
            <Text style={[styles.tagText, { color: est.color }]}>{est.label}</Text>
          </View>
        </View>
        <Text style={styles.cardFecha}>{item.fecha}</Text>
        <Text style={styles.cardItems}>{item.num_items} materiales{item.orden_trabajo ? ` · ${item.orden_trabajo}` : ''}</Text>
        <Ionicons name="chevron-forward" size={18} color="#cbd5e1" style={styles.chev} />
      </TouchableOpacity>
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
            <Ionicons name="document-text-outline" size={48} color="#94a3b8" />
            <Text style={styles.emptyText}>Aún no tienes solicitudes.</Text>
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
  tagText: { fontSize: 11, fontWeight: '700' },
  cardFecha: { color: '#6a6d70', fontSize: 12, marginTop: 4 },
  cardItems: { color: '#475569', fontSize: 13, marginTop: 2 },
  chev: { position: 'absolute', right: 12, bottom: 14 },
  emptyWrap: { flexGrow: 1, justifyContent: 'center' },
  empty: { alignItems: 'center', padding: 40 },
  emptyText: { color: '#94a3b8', marginTop: 12, textAlign: 'center' },
});
