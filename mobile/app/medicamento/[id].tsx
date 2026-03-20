import { View, Text, FlatList, StyleSheet, ActivityIndicator } from 'react-native';
import { useLocalSearchParams } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../src/lib/api';

interface PriceEntry {
  id: string;
  price: number;
  originalPrice: number | null;
  stockStatus: string | null;
  pharmacy: { name: string; chain: string | null };
}

interface MedicationDetail {
  id: string;
  name: string;
  dosage: string;
  pharmaceuticalForm: string;
  prescriptionRequired: boolean;
  activeIngredient: { name: string } | null;
  prices: PriceEntry[];
}

function formatCLP(n: number) {
  return `$${n.toLocaleString('es-CL')}`;
}

export default function MedicationDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();

  const { data, isLoading } = useQuery<MedicationDetail>({
    queryKey: ['medication', id],
    queryFn: () => api.get(`/medications/${id}`).then((r) => r.data),
    enabled: !!id,
  });

  if (isLoading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color="#2563eb" />
      </View>
    );
  }

  if (!data) {
    return (
      <View style={styles.centered}>
        <Text style={styles.errorText}>Medicamento no encontrado</Text>
      </View>
    );
  }

  const sortedPrices = [...(data.prices || [])].sort((a, b) => a.price - b.price);
  const bestPrice = sortedPrices[0];

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.name}>{data.name}</Text>
        <Text style={styles.detail}>
          {data.activeIngredient?.name} · {data.dosage} · {data.pharmaceuticalForm}
        </Text>
        {data.prescriptionRequired && (
          <View style={styles.badge}>
            <Text style={styles.badgeText}>Requiere receta</Text>
          </View>
        )}
        {bestPrice && (
          <Text style={styles.bestPrice}>
            Desde {formatCLP(bestPrice.price)}
          </Text>
        )}
      </View>

      <Text style={styles.sectionTitle}>Precios por farmacia</Text>

      <FlatList
        data={sortedPrices}
        keyExtractor={(item) => item.id}
        renderItem={({ item, index }) => (
          <View style={[styles.priceCard, index === 0 && styles.bestCard]}>
            <View style={styles.priceRow}>
              <View style={{ flex: 1 }}>
                <Text style={styles.pharmacyName}>
                  {item.pharmacy.chain || item.pharmacy.name}
                </Text>
                {index === 0 && <Text style={styles.bestLabel}>Mejor precio</Text>}
              </View>
              <View style={styles.priceCol}>
                <Text style={[styles.price, index === 0 && styles.bestPriceText]}>
                  {formatCLP(item.price)}
                </Text>
                {item.originalPrice && item.originalPrice > item.price && (
                  <Text style={styles.originalPrice}>{formatCLP(item.originalPrice)}</Text>
                )}
              </View>
            </View>
            <Text style={[
              styles.stockText,
              item.stockStatus === 'in_stock' ? styles.inStock : styles.outStock,
            ]}>
              {item.stockStatus === 'in_stock' ? 'En stock' : 'Sin stock'}
            </Text>
          </View>
        )}
        ListEmptyComponent={
          <Text style={styles.emptyText}>No hay precios disponibles</Text>
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f9fafb' },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  errorText: { fontSize: 16, color: '#6b7280' },
  header: { backgroundColor: '#fff', padding: 20, borderBottomWidth: 1, borderBottomColor: '#e5e7eb' },
  name: { fontSize: 22, fontWeight: '700', color: '#111827' },
  detail: { fontSize: 14, color: '#6b7280', marginTop: 4 },
  badge: { marginTop: 8, backgroundColor: '#fef2f2', paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12, alignSelf: 'flex-start' },
  badgeText: { fontSize: 12, color: '#dc2626', fontWeight: '500' },
  bestPrice: { fontSize: 24, fontWeight: '700', color: '#2563eb', marginTop: 12 },
  sectionTitle: { fontSize: 16, fontWeight: '600', color: '#374151', paddingHorizontal: 16, paddingTop: 16, paddingBottom: 8 },
  priceCard: { backgroundColor: '#fff', marginHorizontal: 16, marginBottom: 8, padding: 16, borderRadius: 12, borderWidth: 1, borderColor: '#e5e7eb' },
  bestCard: { borderColor: '#2563eb', borderWidth: 2 },
  priceRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' },
  pharmacyName: { fontSize: 15, fontWeight: '600', color: '#111827' },
  bestLabel: { fontSize: 11, color: '#2563eb', fontWeight: '600', marginTop: 2 },
  priceCol: { alignItems: 'flex-end' },
  price: { fontSize: 18, fontWeight: '700', color: '#111827' },
  bestPriceText: { color: '#2563eb' },
  originalPrice: { fontSize: 13, color: '#9ca3af', textDecorationLine: 'line-through', marginTop: 2 },
  stockText: { fontSize: 12, marginTop: 8 },
  inStock: { color: '#16a34a' },
  outStock: { color: '#dc2626' },
  emptyText: { textAlign: 'center', color: '#6b7280', marginTop: 32 },
});
