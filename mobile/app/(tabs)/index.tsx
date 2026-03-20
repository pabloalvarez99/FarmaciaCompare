import { View, TextInput, FlatList, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useRouter } from 'expo-router';
import { api } from '@/lib/api';

export default function SearchScreen() {
  const [query, setQuery] = useState('');
  const router = useRouter();

  const { data, isLoading } = useQuery({
    queryKey: ['search', query],
    queryFn: () => api.get('/medications/search', { params: { q: query, limit: 20 } }).then(r => r.data),
    enabled: query.length >= 2,
  });

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>FarmaciaCompare</Text>
        <TextInput style={styles.input} placeholder="Buscar medicamento..." value={query}
          onChangeText={setQuery} clearButtonMode="while-editing" autoCapitalize="none" />
      </View>
      <FlatList data={data?.results ?? []} keyExtractor={(item) => item.id}
        renderItem={({ item }) => (
          <TouchableOpacity style={styles.card} onPress={() => router.push(`/medicamento/${item.id}`)}>
            <Text style={styles.name}>{item.name}</Text>
            <Text style={styles.sub}>{item.activeIngredientName} · {item.dosage}</Text>
            <View style={styles.row}>
              <Text style={styles.pharmacies}>{item.pharmacyCount} farmacias</Text>
              {item.lowestPrice && <Text style={styles.price}>Desde ${item.lowestPrice.toLocaleString('es-CL')}</Text>}
            </View>
          </TouchableOpacity>
        )}
        ListEmptyComponent={!isLoading && query.length >= 2 ? <Text style={styles.empty}>No se encontraron resultados</Text> : null}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f9fafb' },
  header: { padding: 16, paddingTop: 60, backgroundColor: '#fff', borderBottomWidth: 1, borderBottomColor: '#e5e7eb' },
  title: { fontSize: 24, fontWeight: '700', color: '#2563eb', marginBottom: 12 },
  input: { height: 44, borderWidth: 1, borderColor: '#e5e7eb', borderRadius: 10, paddingHorizontal: 12, backgroundColor: '#f3f4f6', fontSize: 16 },
  card: { backgroundColor: '#fff', marginHorizontal: 16, marginTop: 10, padding: 16, borderRadius: 12, borderWidth: 1, borderColor: '#e5e7eb' },
  name: { fontSize: 16, fontWeight: '600', color: '#111827' },
  sub: { fontSize: 13, color: '#6b7280', marginTop: 2 },
  row: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 8 },
  pharmacies: { fontSize: 13, color: '#6b7280' },
  price: { fontSize: 16, fontWeight: '700', color: '#2563eb' },
  empty: { textAlign: 'center', padding: 32, color: '#9ca3af' },
});
