import React, { useEffect, useState } from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { Ionicons } from '@expo/vector-icons';
import { StatusBar } from 'expo-status-bar';
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

const Tab = createBottomTabNavigator();

function MainTabs() {
  return (
    <>
      <SyncBar />
      <Tab.Navigator
        screenOptions={({ route }) => ({
          tabBarIcon: ({ color, size }) => {
            let iconName: keyof typeof Ionicons.glyphMap = 'cube-outline';
            if (route.name === 'Stock') iconName = 'cube-outline';
            else if (route.name === 'Scanner') iconName = 'barcode-outline';
            else if (route.name === 'Despacho') iconName = 'arrow-down-circle-outline';
            else if (route.name === 'Inventario') iconName = 'clipboard-outline';
            else if (route.name === 'Transferir') iconName = 'swap-horizontal-outline';
            return <Ionicons name={iconName} size={size} color={color} />;
          },
          tabBarActiveTintColor: '#0070f2',
          tabBarInactiveTintColor: '#6a6d70',
          headerStyle: { backgroundColor: '#354a5f' },
          headerTintColor: '#fff',
          headerTitleStyle: { fontWeight: '600' },
        })}
      >
        <Tab.Screen name="Stock" component={StockScreen} options={{ title: 'Consulta' }} />
        <Tab.Screen name="Scanner" component={ScannerScreen} options={{ title: 'Escanear' }} />
        <Tab.Screen name="Despacho" component={DispatchScreen} options={{ title: 'Despacho' }} />
        <Tab.Screen name="Inventario" component={InventoryScreen} options={{ title: 'Conteo' }} />
        <Tab.Screen name="Transferir" component={TransferScreen} options={{ title: 'Transferir' }} />
      </Tab.Navigator>
    </>
  );
}

function AppContent() {
  const { isLoggedIn } = useAuth();
  if (!isLoggedIn) return <LoginScreen />;
  return <MainTabs />;
}

export default function App() {
  const [dbReady, setDbReady] = useState(false);

  useEffect(() => {
    initDatabase().then(() => setDbReady(true));
  }, []);

  if (!dbReady) return null;

  return (
    <AuthProvider>
      <SyncProvider>
        <NavigationContainer>
          <StatusBar style="light" />
          <AppContent />
        </NavigationContainer>
      </SyncProvider>
    </AuthProvider>
  );
}
