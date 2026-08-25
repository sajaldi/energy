import React, { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet, Alert } from 'react-native';
import { useAuth } from '../context/AuthContext';

export default function LoginScreen() {
  const { login } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLogin = async () => {
    if (!username || !password) { Alert.alert('Error', 'Ingrese usuario y contraseña'); return; }
    setLoading(true);
    try {
      await login(username, password);
    } catch (e: any) {
      Alert.alert('Error', 'Credenciales incorrectas o sin conexión');
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={styles.container}>
      <View style={styles.card}>
        <Text style={styles.title}>SoftCoM</Text>
        <Text style={styles.subtitle}>Inventario de Campo</Text>
        <TextInput style={styles.input} placeholder="Usuario" value={username} onChangeText={setUsername} autoCapitalize="none" />
        <TextInput style={styles.input} placeholder="Contraseña" value={password} onChangeText={setPassword} secureTextEntry />
        <TouchableOpacity style={[styles.btn, loading && styles.btnDisabled]} onPress={handleLogin} disabled={loading}>
          <Text style={styles.btnText}>{loading ? 'Ingresando...' : 'Ingresar'}</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#354a5f', padding: 24 },
  card: { backgroundColor: '#fff', borderRadius: 8, padding: 32, width: '100%', maxWidth: 360 },
  title: { fontSize: 28, fontWeight: '800', color: '#0070f2', textAlign: 'center' },
  subtitle: { fontSize: 14, color: '#6a6d70', textAlign: 'center', marginBottom: 24 },
  input: { borderWidth: 1, borderColor: '#d9d9d9', padding: 14, fontSize: 16, marginBottom: 12 },
  btn: { backgroundColor: '#0070f2', padding: 16, alignItems: 'center', marginTop: 8 },
  btnDisabled: { opacity: 0.6 },
  btnText: { color: '#fff', fontWeight: '700', fontSize: 16 },
});
