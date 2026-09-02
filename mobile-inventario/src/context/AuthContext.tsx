import React, { createContext, useContext, useState, useEffect } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { login as apiLogin, logout as apiLogout } from '../api/client';
import { registerForPushNotifications } from '../notifications';

interface AuthState {
  isLoggedIn: boolean;
  user: any | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState>({
  isLoggedIn: false,
  user: null,
  login: async () => {},
  logout: async () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [user, setUser] = useState<any>(null);

  useEffect(() => {
    AsyncStorage.getItem('auth_token').then(token => {
      if (token) {
        setIsLoggedIn(true);
        AsyncStorage.getItem('user_info').then(info => {
          if (info) setUser(JSON.parse(info));
        });
        // Re-registrar el token push por si cambió o no se había guardado
        registerForPushNotifications();
      }
    });
  }, []);

  const login = async (username: string, password: string) => {
    await apiLogin(username, password);
    const info = await AsyncStorage.getItem('user_info');
    setUser(info ? JSON.parse(info) : null);
    setIsLoggedIn(true);
    // Registrar el dispositivo para notificaciones push tras iniciar sesión
    registerForPushNotifications();
  };

  const logout = async () => {
    await apiLogout();
    setUser(null);
    setIsLoggedIn(false);
  };

  return (
    <AuthContext.Provider value={{ isLoggedIn, user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
