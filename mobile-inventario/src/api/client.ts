/**
 * API Client for syncing with Django backend.
 * Handles auth, retries, and offline detection.
 */
import * as Network from 'expo-network';
import AsyncStorage from '@react-native-async-storage/async-storage';

const API_BASE = 'https://softcom.ccg.hn'; // Producción

async function getToken(): Promise<string | null> {
  return AsyncStorage.getItem('auth_token');
}

async function isOnline(): Promise<boolean> {
  try {
    const state = await Network.getNetworkStateAsync();
    return state.isConnected === true && state.isInternetReachable === true;
  } catch {
    return false;
  }
}

async function apiRequest(endpoint: string, options: RequestInit = {}): Promise<any> {
  const token = await getToken();
  const headers: any = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };
  if (token) headers['Authorization'] = `Token ${token}`;

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`API Error ${response.status}: ${text}`);
  }

  return response.json();
}

// ===== AUTH =====
export async function login(username: string, password: string): Promise<string> {
  const data = await apiRequest('/inventarios/api/auth/login/', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });
  await AsyncStorage.setItem('auth_token', data.token);
  await AsyncStorage.setItem('user_info', JSON.stringify(data.user));
  return data.token;
}

export async function logout(): Promise<void> {
  await AsyncStorage.removeItem('auth_token');
  await AsyncStorage.removeItem('user_info');
}

// ===== SYNC =====
export async function fetchMasterData(): Promise<{ materials: any[]; locations: any[]; stock: any[] }> {
  return apiRequest('/inventarios/api/mobile-sync/master/');
}

export async function pushOperations(operations: any[]): Promise<any> {
  return apiRequest('/inventarios/api/mobile-sync/push/', {
    method: 'POST',
    body: JSON.stringify({ operations }),
  });
}

export async function pushInventoryCounts(counts: any[]): Promise<any> {
  return apiRequest('/inventarios/api/mobile-sync/inventory-counts/', {
    method: 'POST',
    body: JSON.stringify({ counts }),
  });
}

// ===== MATERIALS =====
export async function createMaterial(payload: { nombre: string; sku?: string; codigo_barras?: string; unidad?: string; categoria_id?: number; descripcion?: string; }): Promise<any> {
  return apiRequest('/inventarios/api/mobile-sync/create-material/', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateMaterial(materialId: number, payload: { nombre?: string; codigo_barras?: string; descripcion?: string; unidad?: string; }): Promise<any> {
  return apiRequest(`/inventarios/api/mobile-sync/update-material/${materialId}/`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function fetchCategorias(): Promise<{ categorias: any[] }> {
  return apiRequest('/inventarios/api/mobile-sync/categorias/');
}

// ===== SOLICITUDES (por rol) =====

// Aprobador de salidas: solicitudes pendientes de autorización de su departamento
export async function fetchPendientesAprobacion(): Promise<{ solicitudes: any[] }> {
  return apiRequest('/inventarios/api/mobile/aprobaciones/');
}

export async function aprobarSolicitud(id: number, accion: 'aprobar' | 'rechazar'): Promise<any> {
  return apiRequest(`/inventarios/api/mobile/solicitudes/${id}/aprobar/`, {
    method: 'POST',
    body: JSON.stringify({ accion }),
  });
}

// Almacén: solicitudes listas para despacho / recolección
export async function fetchParaDespacho(): Promise<{ solicitudes: any[] }> {
  return apiRequest('/inventarios/api/mobile/despachos/');
}

// Almacén: despachar (pasa a LISTO_RECOLECCION)
export async function despacharSolicitud(id: number): Promise<any> {
  return apiRequest(`/inventarios/api/mobile/solicitudes/${id}/despachar/`, {
    method: 'POST',
    body: JSON.stringify({}),
  });
}

// Almacén: confirmar entrega con foto de quién recibe (base64) y cantidades
export async function confirmarEntrega(
  id: number,
  payload: { recibe_nombre?: string; foto_base64?: string; items?: { mov_id: number; cantidad: number }[] }
): Promise<any> {
  return apiRequest(`/inventarios/api/mobile/solicitudes/${id}/confirmar-entrega/`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

// Usuario común: mis solicitudes
export async function fetchMisSolicitudes(): Promise<{ solicitudes: any[] }> {
  return apiRequest('/inventarios/api/mobile/mis-solicitudes/');
}

export async function fetchSolicitudDetalle(id: number): Promise<{ solicitud: any }> {
  return apiRequest(`/inventarios/api/mobile/solicitudes/${id}/`);
}

// ===== PUSH NOTIFICATIONS =====
export async function registrarPushToken(expoPushToken: string): Promise<any> {
  return apiRequest('/inventarios/api/mobile/push-token/', {
    method: 'POST',
    body: JSON.stringify({ token: expoPushToken }),
  });
}

export { isOnline };
