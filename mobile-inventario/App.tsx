import React, { useEffect, useState } from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { Ionicons } from '@expo/vector-icons';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { initDatabase } from './src/db/database';
import { SyncProvider } from './src/context/SyncContext';
import { AuthProvider, useAuth } from './src/context/AuthContext';

import StockScreen from './src/screens/StockScreen';
import ScannerScreen from './src/screens/ScannerScreen';
import DispatchScreen from './src/screens/DispatchScreen';
import InventoryScreen from './src/screens/InventoryScreen';
import TransferScreen from './src/screens/TransferScreen';
import LoginScreen from './src/screens/LoginScreen';
import SyncBar from './src/components/SyncBar';

// Nuevas pantallas por rol
import MisSolicitudesScreen from './src/screens/MisSolicitudesScreen';
import NuevaSolicitudScreen from './src/screens/NuevaSolicitudScreen';
import AprobacionesScreen from './src/screens/AprobacionesScreen';
import DespachosScreen from './src/screens/DespachosScreen';
import SolicitudDetalleScreen from './src/screens/SolicitudDetalleScreen';

const Tab = createBottomTabNavigator();
const Stack = createNativeStackNavigator();

const commonScreenOptions = {
  headerStyle: { backgroundColor: '#354a5f' },
  headerTintColor: '#fff',
  headerTitleStyle: { fontWeight: '600' as const },
  tabBarActiveTintColor: '#0070f2',
  tabBarInactiveTintColor: '#6a6d70',
};

function icon(name: keyof typeof Ionicons.glyphMap) {
  return ({ color, size }: { color: string; size: number }) => <Ionicons name={name} size={size} color={color} />;
}

// ---- Stack: Mis Solicitudes -> Detalle ----
function MisSolicitudesStack() {
  return (
    <Stack.Navigator screenOptions={{ headerStyle: { backgroundColor: '#354a5f' }, headerTintColor: '#fff' }}>
      <Stack.Screen name="MisSolicitudesList" component={MisSolicitudesScreen} options={{ title: 'Mis Solicitudes' }} />
      <Stack.Screen name="SolicitudDetalle" component={SolicitudDetalleScreen} options={{ title: 'Detalle' }} />
    </Stack.Navigator>
  );
}

function AprobacionesStack() {
  return (
    <Stack.Navigator screenOptions={{ headerStyle: { backgroundColor: '#354a5f' }, headerTintColor: '#fff' }}>
      <Stack.Screen name="AprobacionesList" component={AprobacionesScreen} options={{ title: 'Aprobaciones' }} />
      <Stack.Screen name="SolicitudDetalle" component={SolicitudDetalleScreen} options={{ title: 'Detalle' }} />
    </Stack.Navigator>
  );
}

function DespachosStack() {
  return (
    <Stack.Navigator screenOptions={{ headerStyle: { backgroundColor: '#354a5f' }, headerTintColor: '#fff' }}>
      <Stack.Screen name="DespachosList" component={DespachosScreen} options={{ title: 'Por Despachar' }} />
      <Stack.Screen name="SolicitudDetalle" component={SolicitudDetalleScreen} options={{ title: 'Detalle' }} />
    </Stack.Navigator>
  );
}

// ---- Tabs por rol ----
function UsuarioTabs() {
  return (
    <Tab.Navigator screenOptions={commonScreenOptions}>
      <Tab.Screen name="Solicitudes" component={MisSolicitudesStack} options={{ headerShown: false, tabBarIcon: icon('document-text-outline') }} />
      <Tab.Screen name="Nueva" component={NuevaSolicitudScreen} options={{ title: 'Nueva Solicitud', tabBarIcon: icon('add-circle-outline') }} />
      <Tab.Screen name="Consulta" component={StockScreen} options={{ tabBarIcon: icon('cube-outline') }} />
    </Tab.Navigator>
  );
}

function AprobadorTabs() {
  return (
    <Tab.Navigator screenOptions={commonScreenOptions}>
      <Tab.Screen name="Aprobaciones" component={AprobacionesStack} options={{ headerShown: false, tabBarIcon: icon('checkmark-done-outline') }} />
      <Tab.Screen name="Solicitudes" component={MisSolicitudesStack} options={{ headerShown: false, title: 'Mis Solicitudes', tabBarIcon: icon('document-text-outline') }} />
      <Tab.Screen name="Nueva" component={NuevaSolicitudScreen} options={{ title: 'Nueva Solicitud', tabBarIcon: icon('add-circle-outline') }} />
    </Tab.Navigator>
  );
}

function AlmacenTabs() {
  return (
    <Tab.Navigator screenOptions={commonScreenOptions}>
      <Tab.Screen name="Despachar" component={DespachosStack} options={{ headerShown: false, tabBarIcon: icon('arrow-down-circle-outline') }} />
      <Tab.Screen name="Consulta" component={StockScreen} options={{ tabBarIcon: icon('cube-outline') }} />
      <Tab.Screen name="Scanner" component={ScannerScreen} options={{ title: 'Escanear', tabBarIcon: icon('barcode-outline') }} />
      <Tab.Screen name="Inventario" component={InventoryScreen} options={{ title: 'Conteo', tabBarIcon: icon('clipboard-outline') }} />
    </Tab.Navigator>
  );
}

function AppContent() {
  const { isLoggedIn, user } = useAuth();
  if (!isLoggedIn) return <LoginScreen />;

  const rol = user?.rol || 'usuario';
  let Tabs = UsuarioTabs;
  if (rol === 'almacen') Tabs = AlmacenTabs;
  else if (rol === 'aprobador') Tabs = AprobadorTabs;

  return (
    <>
      <Tabs />
      <SyncBar />
    </>
  );
}

export default function App() {
  const [dbReady, setDbReady] = useState(false);

  useEffect(() => {
    initDatabase().then(() => setDbReady(true));
  }, []);

  if (!dbReady) return null;

  return (
    <SafeAreaProvider>
      <AuthProvider>
        <SyncProvider>
          <NavigationContainer>
            <StatusBar style="light" />
            <AppContent />
          </NavigationContainer>
        </SyncProvider>
      </AuthProvider>
    </SafeAreaProvider>
  );
}
