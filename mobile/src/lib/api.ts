import axios from 'axios';

const API_URL = process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:4000/api/v1';

export const api = axios.create({ baseURL: API_URL });

// Token interceptors will use expo-secure-store at runtime
api.interceptors.request.use(async (config) => {
  // SecureStore will be imported dynamically to avoid web issues
  try {
    const SecureStore = require('expo-secure-store');
    const token = await SecureStore.getItemAsync('accessToken');
    if (token) config.headers.Authorization = `Bearer ${token}`;
  } catch {}
  return config;
});
