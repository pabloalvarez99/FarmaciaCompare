import { create } from 'zustand';
import { api } from '@/lib/api';

interface AuthState {
  user: { id: string; email: string; name: string | null } | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  checkAuth: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isLoading: true,

  checkAuth: async () => {
    try {
      const SecureStore = require('expo-secure-store');
      const token = await SecureStore.getItemAsync('accessToken');
      if (!token) { set({ isLoading: false }); return; }
      const { data } = await api.get('/users/me');
      set({ user: data, isLoading: false });
    } catch {
      set({ user: null, isLoading: false });
    }
  },

  login: async (email, password) => {
    const { data } = await api.post('/auth/login', { email, password });
    const SecureStore = require('expo-secure-store');
    await SecureStore.setItemAsync('accessToken', data.accessToken);
    await SecureStore.setItemAsync('refreshToken', data.refreshToken);
    set({ user: data.user });
  },

  logout: async () => {
    const SecureStore = require('expo-secure-store');
    await SecureStore.deleteItemAsync('accessToken');
    await SecureStore.deleteItemAsync('refreshToken');
    set({ user: null });
  },
}));
