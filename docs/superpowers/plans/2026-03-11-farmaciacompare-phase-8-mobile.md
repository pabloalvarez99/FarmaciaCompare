# FarmaciaCompare Phase 8 — Mobile App Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Build the React Native (Expo) mobile app for iOS and Android — medication search, price comparison, pharmacy map, price alerts with push notifications, and prescription camera upload.

**Architecture:** Expo SDK 51 with Expo Router (file-based navigation). Zustand for auth state. React Query for server data. expo-notifications for push alerts. expo-location for nearby pharmacies. expo-camera for prescription capture.

**Tech Stack:** React Native, Expo SDK 51, Expo Router, TypeScript, NativeWind (Tailwind for RN), @tanstack/react-query, Zustand, expo-notifications, expo-location, expo-camera, react-native-maps, @gorhom/bottom-sheet.

**Prerequisites:** Phases 1–5 complete (auth and medications API live).

---

## Chunk 1: Mobile App Scaffold

### Task 1: Initialize Expo app

**Files:**
- Create: `mobile/app/` (Expo Router structure)
- Create: `mobile/app.json`
- Create: `mobile/src/lib/api.ts`
- Create: `mobile/src/stores/authStore.ts`

- [ ] **Step 1: Create Expo app**

```bash
cd mobile
npx create-expo-app app --template blank-typescript
cd app
npx expo install expo-router expo-notifications expo-location expo-camera react-native-maps expo-secure-store expo-image-picker
npx expo install nativewind tailwindcss
pnpm add @tanstack/react-query zustand @gorhom/bottom-sheet react-native-gesture-handler react-native-reanimated
```

- [ ] **Step 2: Configure `mobile/app/app.json`**

```json
{
  "expo": {
    "name": "FarmaciaCompare",
    "slug": "farmacia-compare",
    "version": "1.0.0",
    "scheme": "farmaciacompare",
    "orientation": "portrait",
    "plugins": [
      "expo-router",
      "expo-notifications",
      ["expo-location", { "locationAlwaysAndWhenInUsePermission": "Para mostrarte farmacias cercanas" }],
      ["expo-camera", { "cameraPermission": "Para fotografiar tu receta médica" }]
    ],
    "android": {
      "package": "cl.farmaciacompare.app",
      "googleServicesFile": "./google-services.json"
    },
    "ios": {
      "bundleIdentifier": "cl.farmaciacompare.app",
      "googleServicesFile": "./GoogleService-Info.plist"
    }
  }
}
```

- [ ] **Step 3: Create `mobile/app/src/lib/api.ts`**

```typescript
import axios from 'axios';
import * as SecureStore from 'expo-secure-store';

const API_URL = process.env.EXPO_PUBLIC_API_URL ?? 'https://api.farmaciacompare.cl/api/v1';

export const api = axios.create({ baseURL: API_URL });

api.interceptors.request.use(async (config) => {
  const token = await SecureStore.getItemAsync('accessToken');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    if (error.response?.status === 401) {
      const refreshToken = await SecureStore.getItemAsync('refreshToken');
      if (refreshToken) {
        try {
          const { data } = await api.post('/auth/refresh', { refreshToken });
          await SecureStore.setItemAsync('accessToken', data.accessToken);
          await SecureStore.setItemAsync('refreshToken', data.refreshToken);
          error.config.headers.Authorization = `Bearer ${data.accessToken}`;
          return api(error.config);
        } catch {
          await SecureStore.deleteItemAsync('accessToken');
          await SecureStore.deleteItemAsync('refreshToken');
        }
      }
    }
    return Promise.reject(error);
  },
);
```

- [ ] **Step 4: Create `mobile/app/src/stores/authStore.ts`**

```typescript
import { create } from 'zustand';
import * as SecureStore from 'expo-secure-store';
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
    const token = await SecureStore.getItemAsync('accessToken');
    if (!token) { set({ isLoading: false }); return; }
    try {
      const { data } = await api.get('/users/me');
      set({ user: data, isLoading: false });
    } catch {
      set({ user: null, isLoading: false });
    }
  },

  login: async (email, password) => {
    const { data } = await api.post('/auth/login', { email, password });
    await SecureStore.setItemAsync('accessToken', data.accessToken);
    await SecureStore.setItemAsync('refreshToken', data.refreshToken);
    set({ user: data.user });
  },

  logout: async () => {
    await SecureStore.deleteItemAsync('accessToken');
    await SecureStore.deleteItemAsync('refreshToken');
    set({ user: null });
  },
}));
```

- [ ] **Step 5: Commit**

```bash
git add mobile/
git commit -m "chore: scaffold React Native Expo app with auth store and API client"
```

---

## Chunk 2: Navigation and Screens

### Task 2: Tab navigation and core screens

**Files (Expo Router file structure):**
```
mobile/app/
├── _layout.tsx               # Root layout, QueryClient, gesture handler
├── (auth)/
│   ├── login.tsx
│   └── register.tsx
└── (tabs)/
    ├── _layout.tsx           # Bottom tab navigator
    ├── index.tsx             # Search tab
    ├── mapa.tsx              # Map tab
    ├── alertas.tsx           # Price alerts tab
    └── perfil.tsx            # Profile tab
```

- [ ] **Step 1: Create root layout `mobile/app/app/_layout.tsx`**

```tsx
import { Stack } from 'expo-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { useEffect } from 'react';
import { useAuthStore } from '@/stores/authStore';

const queryClient = new QueryClient({ defaultOptions: { queries: { staleTime: 60000 } } });

export default function RootLayout() {
  const checkAuth = useAuthStore((s) => s.checkAuth);
  useEffect(() => { checkAuth(); }, []);

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <QueryClientProvider client={queryClient}>
        <Stack screenOptions={{ headerShown: false }} />
      </QueryClientProvider>
    </GestureHandlerRootView>
  );
}
```

- [ ] **Step 2: Create tab layout `mobile/app/app/(tabs)/_layout.tsx`**

```tsx
import { Tabs } from 'expo-router';
import { Search, MapPin, Bell, User } from 'lucide-react-native';

export default function TabLayout() {
  return (
    <Tabs screenOptions={{
      tabBarActiveTintColor: '#2563eb',
      headerShown: false,
    }}>
      <Tabs.Screen name="index" options={{ title: 'Buscar', tabBarIcon: ({ color }) => <Search color={color} size={22} /> }} />
      <Tabs.Screen name="mapa" options={{ title: 'Mapa', tabBarIcon: ({ color }) => <MapPin color={color} size={22} /> }} />
      <Tabs.Screen name="alertas" options={{ title: 'Alertas', tabBarIcon: ({ color }) => <Bell color={color} size={22} /> }} />
      <Tabs.Screen name="perfil" options={{ title: 'Perfil', tabBarIcon: ({ color }) => <User color={color} size={22} /> }} />
    </Tabs>
  );
}
```

- [ ] **Step 3: Create search screen `mobile/app/app/(tabs)/index.tsx`**

```tsx
import { View, TextInput, FlatList, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useRouter } from 'expo-router';
import { api } from '@/lib/api';

function MedicationItem({ item }: { item: any }) {
  const router = useRouter();
  return (
    <TouchableOpacity
      style={styles.card}
      onPress={() => router.push(`/medicamento/${item.id}`)}
    >
      <Text style={styles.name}>{item.name}</Text>
      <Text style={styles.sub}>{item.activeIngredientName} · {item.dosage}</Text>
      <View style={styles.row}>
        <Text style={styles.pharmacies}>{item.pharmacyCount} farmacias</Text>
        {item.lowestPrice && (
          <Text style={styles.price}>
            Desde ${item.lowestPrice.toLocaleString('es-CL')}
          </Text>
        )}
      </View>
    </TouchableOpacity>
  );
}

export default function SearchScreen() {
  const [query, setQuery] = useState('');

  const { data, isLoading } = useQuery({
    queryKey: ['search', query],
    queryFn: () => api.get('/medications/search', { params: { q: query, limit: 20 } }).then(r => r.data),
    enabled: query.length >= 2,
  });

  return (
    <View style={styles.container}>
      <View style={styles.searchContainer}>
        <TextInput
          style={styles.input}
          placeholder="Buscar medicamento..."
          value={query}
          onChangeText={setQuery}
          clearButtonMode="while-editing"
          autoCapitalize="none"
        />
      </View>
      <FlatList
        data={data?.results ?? []}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => <MedicationItem item={item} />}
        ListEmptyComponent={
          !isLoading && query.length >= 2 ? (
            <Text style={styles.empty}>No se encontraron resultados</Text>
          ) : null
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f9fafb' },
  searchContainer: { padding: 16, backgroundColor: '#fff', borderBottomWidth: 1, borderBottomColor: '#e5e7eb' },
  input: { height: 44, borderWidth: 1, borderColor: '#e5e7eb', borderRadius: 10, paddingHorizontal: 12, backgroundColor: '#f3f4f6', fontSize: 16 },
  card: { backgroundColor: '#fff', marginHorizontal: 16, marginTop: 10, padding: 16, borderRadius: 12, borderWidth: 1, borderColor: '#e5e7eb' },
  name: { fontSize: 16, fontWeight: '600', color: '#111827' },
  sub: { fontSize: 13, color: '#6b7280', marginTop: 2 },
  row: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 8 },
  pharmacies: { fontSize: 13, color: '#6b7280' },
  price: { fontSize: 16, fontWeight: '700', color: '#2563eb' },
  empty: { textAlign: 'center', padding: 32, color: '#9ca3af' },
});
```

- [ ] **Step 4: Commit**

```bash
git add mobile/
git commit -m "feat: implement tab navigation and medication search screen"
```

---

## Chunk 3: Push Notifications for Price Alerts

### Task 3: Price alert push notifications

**Files:**
- Create: `services/api-gateway/src/notifications/notifications.service.ts`
- Create: `mobile/app/app/(tabs)/alertas.tsx`
- Modify: `services/api-gateway/src/app.module.ts` (register schedule)

- [ ] **Step 1: Register push token endpoint**

```typescript
// POST /users/push-token
// Saves Expo push token to user record (add push_token column via Prisma migration)
```

Add to Prisma schema:
```prisma
model User {
  // ... existing fields
  pushToken String? @map("push_token")
}
```

Run: `pnpm db:migrate`

- [ ] **Step 2: Register device token from app**

```typescript
// mobile/app/src/hooks/usePushNotifications.ts
import * as Notifications from 'expo-notifications';
import { useEffect } from 'react';
import { api } from '@/lib/api';

export function usePushNotifications() {
  useEffect(() => {
    (async () => {
      const { status } = await Notifications.requestPermissionsAsync();
      if (status !== 'granted') return;
      const token = (await Notifications.getExpoPushTokenAsync()).data;
      await api.post('/users/push-token', { token });
    })();
  }, []);
}
```

- [ ] **Step 3: Scheduled alert checker (NestJS cron)**

```typescript
// services/api-gateway/src/notifications/notifications.service.ts
import { Injectable } from '@nestjs/common';
import { Cron, CronExpression } from '@nestjs/schedule';
import { prisma } from '@farmacia/database';
import Expo from 'expo-server-sdk';

@Injectable()
export class NotificationsService {
  private expo = new Expo();

  @Cron(CronExpression.EVERY_HOUR)
  async checkPriceAlerts() {
    const activeAlerts = await prisma.priceAlert.findMany({
      where: { isActive: true },
      include: {
        user: { select: { pushToken: true } },
        medication: { select: { name: true } },
      },
    });

    const messages: Expo.ExpoPushMessage[] = [];

    for (const alert of activeAlerts) {
      if (!alert.user.pushToken) continue;

      // Find current lowest price for this medication (optionally filtered by pharmacy)
      const lowestPriceRecord = await prisma.price.findFirst({
        where: {
          pharmacyProduct: {
            medicationId: alert.medicationId,
            ...(alert.pharmacyId ? { pharmacyId: alert.pharmacyId } : {}),
          },
        },
        orderBy: { price: 'asc' },
        take: 1,
      });

      if (!lowestPriceRecord) continue;
      if (lowestPriceRecord.price <= alert.targetPrice) {
        messages.push({
          to: alert.user.pushToken,
          title: '💊 Alerta de precio',
          body: `${alert.medication.name} bajó a $${lowestPriceRecord.price.toLocaleString('es-CL')}`,
          data: { medicationId: alert.medicationId },
        });

        await prisma.priceAlert.update({
          where: { id: alert.id },
          data: { lastTriggered: new Date() },
        });
      }
    }

    if (messages.length > 0) {
      const chunks = this.expo.chunkPushNotifications(messages);
      for (const chunk of chunks) {
        await this.expo.sendPushNotificationsAsync(chunk);
      }
    }
  }
}
```

Install: `pnpm add expo-server-sdk`

- [ ] **Step 4: Create alerts screen**

```tsx
// mobile/app/app/(tabs)/alertas.tsx
// Shows user's active alerts with medication name, target price
// "Add Alert" button → search medication → set target price
```

- [ ] **Step 5: Commit**

```bash
git add mobile/ services/api-gateway/src/notifications/
git commit -m "feat: implement push notification price alerts with hourly checker"
```

---

## Chunk 4: Pharmacy Map

### Task 4: Nearby pharmacy map with react-native-maps

- [ ] **Step 1: Create `mobile/app/app/(tabs)/mapa.tsx`**

```tsx
import MapView, { Marker, PROVIDER_GOOGLE } from 'react-native-maps';
import { View, StyleSheet } from 'react-native';
import { useQuery } from '@tanstack/react-query';
import * as Location from 'expo-location';
import { useState, useEffect } from 'react';
import { api } from '@/lib/api';

const CHAIN_COLORS: Record<string, string> = {
  cruz_verde: '#22c55e',
  salcobrand: '#3b82f6',
  ahumada: '#f97316',
  dr_simi: '#eab308',
};

export default function MapScreen() {
  const [location, setLocation] = useState<{ lat: number; lng: number } | null>(null);

  useEffect(() => {
    (async () => {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') return;
      const loc = await Location.getCurrentPositionAsync({});
      setLocation({ lat: loc.coords.latitude, lng: loc.coords.longitude });
    })();
  }, []);

  const { data: pharmacies } = useQuery({
    queryKey: ['pharmacies', location?.lat, location?.lng],
    queryFn: () =>
      api.get('/pharmacies', {
        params: { lat: location!.lat, lng: location!.lng, radius: 5 },
      }).then(r => r.data),
    enabled: !!location,
  });

  if (!location) {
    return <View style={styles.loading} />;
  }

  return (
    <MapView
      provider={PROVIDER_GOOGLE}
      style={styles.map}
      initialRegion={{
        latitude: location.lat,
        longitude: location.lng,
        latitudeDelta: 0.05,
        longitudeDelta: 0.05,
      }}
      showsUserLocation
    >
      {pharmacies?.map((pharmacy: any) => (
        <Marker
          key={pharmacy.id}
          coordinate={{ latitude: pharmacy.lat, longitude: pharmacy.lng }}
          title={pharmacy.name}
          description={pharmacy.address}
          pinColor={CHAIN_COLORS[pharmacy.chain] ?? '#6b7280'}
        />
      ))}
    </MapView>
  );
}

const styles = StyleSheet.create({
  map: { flex: 1 },
  loading: { flex: 1, backgroundColor: '#f9fafb' },
});
```

- [ ] **Step 2: Add pharmacies endpoint to API Gateway**

```typescript
// GET /pharmacies?lat=&lng=&radius=
// Uses Haversine formula in PostgreSQL for distance calculation
```

```sql
-- In MedicationsService.findNearby():
SELECT *, (
  6371 * acos(cos(radians($1)) * cos(radians(lat)) *
  cos(radians(lng) - radians($2)) + sin(radians($1)) * sin(radians(lat)))
) AS distance_km
FROM pharmacies
WHERE is_active = true AND lat IS NOT NULL
HAVING distance_km <= $3
ORDER BY distance_km
LIMIT 50;
```

Use `prisma.$queryRaw` with the above query.

- [ ] **Step 3: Commit**

```bash
git add mobile/ services/api-gateway/src/
git commit -m "feat: implement pharmacy map with nearby search using GPS"
```

---

## Phase 8 Complete

**What was built:**
- React Native Expo app (iOS + Android)
- Search screen with medication search and price preview
- Tab navigation (Search, Map, Alerts, Profile)
- Push notifications for price alerts (hourly checker)
- Pharmacy map with GPS location and color-coded chains
- Auth with SecureStore token persistence

**Next:** Phase 9 — Scale & Ops (Kubernetes, Terraform, CI/CD, observability).
