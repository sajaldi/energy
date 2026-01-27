import React from 'react';
import { View } from 'react-native';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { AuditListScreen } from './screens/AuditListScreen';
import { AuditExecutionScreen } from './screens/AuditExecutionScreen';
import { Colors } from './constants/Colors';

export type RootStackParamList = {
  AuditList: undefined;
  AuditExecution: { auditoriaId: number; auditoriaNombre: string };
};

const Stack = createNativeStackNavigator<RootStackParamList>();

export default function App() {
  return (
    <View style={{ flex: 1 }}>
      <NavigationContainer>
        <Stack.Navigator initialRouteName="AuditList">
          <Stack.Screen
            name="AuditList"
            component={AuditListScreen}
          />
          <Stack.Screen
            name="AuditExecution"
            component={AuditExecutionScreen}
          />
        </Stack.Navigator>
      </NavigationContainer>
    </View>
  );
}
