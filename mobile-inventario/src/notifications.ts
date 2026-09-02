/**
 * Notificaciones push (Expo).
 * - Pide permisos, obtiene el Expo push token y lo registra en el backend.
 * - Configura el canal de Android y el handler de presentación.
 */
import { Platform } from 'react-native';
import * as Notifications from 'expo-notifications';
import * as Device from 'expo-device';
import Constants from 'expo-constants';
import { registrarPushToken } from './api/client';

// Cómo se muestran las notificaciones cuando la app está en primer plano
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
  }),
});

function getProjectId(): string | undefined {
  return (
    (Constants?.expoConfig as any)?.extra?.eas?.projectId ||
    (Constants as any)?.easConfig?.projectId
  );
}

/**
 * Registra el dispositivo para push: pide permisos, obtiene el token y lo envía al backend.
 * Devuelve el token o null si no fue posible.
 */
export async function registerForPushNotifications(): Promise<string | null> {
  try {
    if (!Device.isDevice) {
      // Las push reales no funcionan en simuladores/emuladores.
      return null;
    }

    if (Platform.OS === 'android') {
      await Notifications.setNotificationChannelAsync('default', {
        name: 'General',
        importance: Notifications.AndroidImportance.MAX,
        vibrationPattern: [0, 250, 250, 250],
        lightColor: '#0070f2',
      });
    }

    const { status: existing } = await Notifications.getPermissionsAsync();
    let finalStatus = existing;
    if (existing !== 'granted') {
      const { status } = await Notifications.requestPermissionsAsync();
      finalStatus = status;
    }
    if (finalStatus !== 'granted') {
      return null;
    }

    const projectId = getProjectId();
    const tokenData = await Notifications.getExpoPushTokenAsync(
      projectId ? { projectId } : undefined
    );
    const token = tokenData.data;

    if (token) {
      try {
        await registrarPushToken(token);
      } catch (e) {
        // No bloquear el login si el registro del token falla
      }
    }
    return token || null;
  } catch (e) {
    return null;
  }
}
