import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

export default function NuevaSolicitudScreen() {
  return (
    <View style={styles.container}>
      <Ionicons name="construct-outline" size={48} color="#94a3b8" />
      <Text style={styles.title}>Nueva Solicitud</Text>
      <Text style={styles.text}>El armado de solicitudes desde la app se habilitará en el siguiente paso.</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#f7f7f7', padding: 32 },
  title: { fontSize: 18, fontWeight: '800', marginTop: 16, color: '#32363a' },
  text: { color: '#6a6d70', textAlign: 'center', marginTop: 8 },
});
