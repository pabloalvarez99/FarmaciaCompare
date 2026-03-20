import { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  FlatList,
  TextInput,
  StyleSheet,
  ActivityIndicator,
  TouchableOpacity,
  Linking,
  Platform,
} from 'react-native';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../src/lib/api';

interface PharmacyLocation {
  id: string;
  name: string;
  chain: string | null;
  address: string | null;
  city: string | null;
  region: string | null;
  phone: string | null;
  latitude: number | null;
  longitude: number | null;
  isActive: boolean;
}

function getDistanceKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) * Math.cos((lat2 * Math.PI) / 180) * Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

export default function MapScreen() {
  const [search, setSearch] = useState('');
  const [userLat, setUserLat] = useState<number | null>(null);
  const [userLon, setUserLon] = useState<number | null>(null);
  const [locationError, setLocationError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const Location = require('expo-location');
        const { status } = await Location.requestForegroundPermissionsAsync();
        if (status !== 'granted') {
          setLocationError('Permiso de ubicación denegado');
          return;
        }
        const loc = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });
        setUserLat(loc.coords.latitude);
        setUserLon(loc.coords.longitude);
      } catch {
        setLocationError('No se pudo obtener la ubicación');
      }
    })();
  }, []);

  const { data: pharmacies = [], isLoading } = useQuery<PharmacyLocation[]>({
    queryKey: ['pharmacies-map'],
    queryFn: () => api.get('/pharmacies').then((r) => r.data),
  });

  const filtered = pharmacies
    .filter((p) => {
      if (!search.trim()) return true;
      const q = search.toLowerCase();
      return (
        p.name.toLowerCase().includes(q) ||
        (p.chain && p.chain.toLowerCase().includes(q)) ||
        (p.city && p.city.toLowerCase().includes(q)) ||
        (p.address && p.address.toLowerCase().includes(q))
      );
    })
    .map((p) => {
      const distance =
        userLat != null && userLon != null && p.latitude != null && p.longitude != null
          ? getDistanceKm(userLat, userLon, p.latitude, p.longitude)
          : null;
      return { ...p, distance };
    })
    .sort((a, b) => {
      if (a.distance != null && b.distance != null) return a.distance - b.distance;
      if (a.distance != null) return -1;
      if (b.distance != null) return 1;
      return a.name.localeCompare(b.name);
    });

  const openInMaps = useCallback((lat: number, lon: number, name: string) => {
    const label = encodeURIComponent(name);
    const url =
      Platform.OS === 'ios'
        ? `maps:0,0?q=${label}@${lat},${lon}`
        : `geo:${lat},${lon}?q=${lat},${lon}(${label})`;
    Linking.openURL(url).catch(() => {
      Linking.openURL(`https://www.google.com/maps/search/?api=1&query=${lat},${lon}`);
    });
  }, []);

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Farmacias Cercanas</Text>
        {locationError && <Text style={styles.locationError}>{locationError}</Text>}
        {userLat != null && !locationError && (
          <Text style={styles.locationOk}>Ubicación detectada</Text>
        )}
      </View>

      <View style={styles.searchWrap}>
        <TextInput
          style={styles.searchInput}
          placeholder="Buscar farmacia, cadena o ciudad..."
          placeholderTextColor="#9ca3af"
          value={search}
          onChangeText={setSearch}
        />
      </View>

      {isLoading ? (
        <View style={styles.centered}>
          <ActivityIndicator size="large" color="#2563eb" />
        </View>
      ) : (
        <FlatList
          data={filtered}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.list}
          renderItem={({ item }) => (
            <View style={styles.card}>
              <View style={styles.cardTop}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.pharmacyName}>
                    {item.chain ? `${item.chain} - ${item.name}` : item.name}
                  </Text>
                  {item.address && <Text style={styles.address}>{item.address}</Text>}
                  <Text style={styles.cityRegion}>
                    {[item.city, item.region].filter(Boolean).join(', ') || 'Sin ubicación'}
                  </Text>
                </View>
                <View style={styles.rightCol}>
                  {item.distance != null && (
                    <View style={styles.distanceBadge}>
                      <Text style={styles.distanceText}>
                        {item.distance < 1
                          ? `${Math.round(item.distance * 1000)} m`
                          : `${item.distance.toFixed(1)} km`}
                      </Text>
                    </View>
                  )}
                  <View
                    style={[styles.statusDot, { backgroundColor: item.isActive ? '#16a34a' : '#9ca3af' }]}
                  />
                </View>
              </View>

              <View style={styles.cardActions}>
                {item.phone && (
                  <TouchableOpacity
                    style={styles.actionBtn}
                    onPress={() => Linking.openURL(`tel:${item.phone}`)}
                  >
                    <Text style={styles.actionText}>Llamar</Text>
                  </TouchableOpacity>
                )}
                {item.latitude != null && item.longitude != null && (
                  <TouchableOpacity
                    style={[styles.actionBtn, styles.actionPrimary]}
                    onPress={() => openInMaps(item.latitude!, item.longitude!, item.name)}
                  >
                    <Text style={[styles.actionText, { color: '#fff' }]}>Cómo llegar</Text>
                  </TouchableOpacity>
                )}
              </View>
            </View>
          )}
          ListEmptyComponent={
            <View style={styles.centered}>
              <Text style={styles.emptyText}>
                {search ? 'No se encontraron farmacias' : 'No hay farmacias disponibles'}
              </Text>
            </View>
          }
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f9fafb' },
  header: { backgroundColor: '#fff', paddingHorizontal: 16, paddingTop: 16, paddingBottom: 12, borderBottomWidth: 1, borderBottomColor: '#e5e7eb' },
  title: { fontSize: 22, fontWeight: '700', color: '#111827' },
  locationError: { fontSize: 12, color: '#dc2626', marginTop: 4 },
  locationOk: { fontSize: 12, color: '#16a34a', marginTop: 4 },
  searchWrap: { padding: 12 },
  searchInput: { backgroundColor: '#fff', borderWidth: 1, borderColor: '#e5e7eb', borderRadius: 10, paddingHorizontal: 14, paddingVertical: 10, fontSize: 15, color: '#111827' },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center', paddingTop: 40 },
  list: { paddingHorizontal: 12, paddingBottom: 24 },
  card: { backgroundColor: '#fff', borderRadius: 12, padding: 16, marginBottom: 10, borderWidth: 1, borderColor: '#e5e7eb' },
  cardTop: { flexDirection: 'row', justifyContent: 'space-between' },
  pharmacyName: { fontSize: 16, fontWeight: '600', color: '#111827' },
  address: { fontSize: 13, color: '#6b7280', marginTop: 2 },
  cityRegion: { fontSize: 12, color: '#9ca3af', marginTop: 2 },
  rightCol: { alignItems: 'flex-end', gap: 6 },
  distanceBadge: { backgroundColor: '#eff6ff', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8 },
  distanceText: { fontSize: 12, fontWeight: '600', color: '#2563eb' },
  statusDot: { width: 8, height: 8, borderRadius: 4 },
  cardActions: { flexDirection: 'row', gap: 8, marginTop: 12 },
  actionBtn: { paddingHorizontal: 14, paddingVertical: 8, borderRadius: 8, borderWidth: 1, borderColor: '#e5e7eb' },
  actionPrimary: { backgroundColor: '#2563eb', borderColor: '#2563eb' },
  actionText: { fontSize: 13, fontWeight: '600', color: '#374151' },
  emptyText: { fontSize: 15, color: '#6b7280' },
});
