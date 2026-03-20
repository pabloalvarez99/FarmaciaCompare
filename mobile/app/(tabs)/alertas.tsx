import { useState } from 'react';
import {
  View,
  Text,
  FlatList,
  TextInput,
  StyleSheet,
  ActivityIndicator,
  TouchableOpacity,
  Alert,
} from 'react-native';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../src/lib/api';
import { useAuthStore } from '../../src/stores/authStore';
import { useRouter } from 'expo-router';

interface PriceAlert {
  id: string;
  targetPrice: number;
  isActive: boolean;
  lastTriggered: string | null;
  createdAt: string;
  medication: {
    id: string;
    name: string;
    dosage: string;
    pharmaceuticalForm: string;
  };
}

interface MedicationResult {
  id: string;
  name: string;
  dosage: string;
  pharmaceuticalForm: string;
}

function formatCLP(n: number) {
  return `$${n.toLocaleString('es-CL')}`;
}

export default function AlertasScreen() {
  const { user } = useAuthStore();
  const router = useRouter();
  const queryClient = useQueryClient();

  const [showCreate, setShowCreate] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedMed, setSelectedMed] = useState<MedicationResult | null>(null);
  const [targetPrice, setTargetPrice] = useState('');

  const { data: alerts = [], isLoading } = useQuery<PriceAlert[]>({
    queryKey: ['price-alerts'],
    queryFn: () => api.get('/users/price-alerts').then((r) => r.data),
    enabled: !!user,
  });

  const { data: searchResults = [], isFetching: searching } = useQuery<MedicationResult[]>({
    queryKey: ['med-search-alert', searchQuery],
    queryFn: () =>
      api.get(`/medications/search?q=${encodeURIComponent(searchQuery)}`).then((r) => r.data.data || r.data),
    enabled: searchQuery.length >= 3,
  });

  const createMutation = useMutation({
    mutationFn: (body: { medicationId: string; targetPrice: number }) =>
      api.post('/users/price-alerts', body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['price-alerts'] });
      setShowCreate(false);
      setSelectedMed(null);
      setTargetPrice('');
      setSearchQuery('');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/users/price-alerts/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['price-alerts'] }),
  });

  if (!user) {
    return (
      <View style={styles.centered}>
        <Text style={styles.emptyTitle}>Alertas de Precio</Text>
        <Text style={styles.emptySubtitle}>
          Inicia sesión para crear alertas y recibir notificaciones cuando baje el precio
        </Text>
        <TouchableOpacity style={styles.loginBtn} onPress={() => router.push('/(auth)/login')}>
          <Text style={styles.loginBtnText}>Iniciar sesión</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const handleCreate = () => {
    if (!selectedMed) return;
    const price = parseInt(targetPrice, 10);
    if (!price || price <= 0) {
      Alert.alert('Error', 'Ingresa un precio válido');
      return;
    }
    createMutation.mutate({ medicationId: selectedMed.id, targetPrice: price });
  };

  const handleDelete = (id: string) => {
    Alert.alert('Eliminar alerta', '¿Estás seguro que deseas eliminar esta alerta?', [
      { text: 'Cancelar', style: 'cancel' },
      { text: 'Eliminar', style: 'destructive', onPress: () => deleteMutation.mutate(id) },
    ]);
  };

  if (showCreate) {
    return (
      <View style={styles.container}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => { setShowCreate(false); setSelectedMed(null); setSearchQuery(''); }}>
            <Text style={styles.backText}>← Volver</Text>
          </TouchableOpacity>
          <Text style={styles.title}>Nueva Alerta</Text>
        </View>

        {!selectedMed ? (
          <View style={styles.createForm}>
            <Text style={styles.label}>Buscar medicamento</Text>
            <TextInput
              style={styles.input}
              placeholder="Ej: Paracetamol, Ibuprofeno..."
              placeholderTextColor="#9ca3af"
              value={searchQuery}
              onChangeText={setSearchQuery}
              autoFocus
            />
            {searching && <ActivityIndicator style={{ marginTop: 12 }} color="#2563eb" />}
            <FlatList
              data={searchResults}
              keyExtractor={(item) => item.id}
              style={{ marginTop: 8 }}
              renderItem={({ item }) => (
                <TouchableOpacity style={styles.searchResult} onPress={() => setSelectedMed(item)}>
                  <Text style={styles.searchResultName}>{item.name}</Text>
                  <Text style={styles.searchResultDetail}>
                    {item.dosage} · {item.pharmaceuticalForm}
                  </Text>
                </TouchableOpacity>
              )}
              ListEmptyComponent={
                searchQuery.length >= 3 && !searching ? (
                  <Text style={styles.noResults}>Sin resultados</Text>
                ) : null
              }
            />
          </View>
        ) : (
          <View style={styles.createForm}>
            <View style={styles.selectedMed}>
              <Text style={styles.selectedMedName}>{selectedMed.name}</Text>
              <Text style={styles.selectedMedDetail}>
                {selectedMed.dosage} · {selectedMed.pharmaceuticalForm}
              </Text>
              <TouchableOpacity onPress={() => setSelectedMed(null)}>
                <Text style={styles.changeLink}>Cambiar</Text>
              </TouchableOpacity>
            </View>

            <Text style={styles.label}>Precio objetivo (CLP)</Text>
            <TextInput
              style={styles.input}
              placeholder="Ej: 5000"
              placeholderTextColor="#9ca3af"
              value={targetPrice}
              onChangeText={setTargetPrice}
              keyboardType="numeric"
              autoFocus
            />
            <Text style={styles.hint}>
              Te notificaremos cuando el precio baje a {targetPrice ? formatCLP(parseInt(targetPrice, 10) || 0) : '$0'} o menos
            </Text>

            <TouchableOpacity
              style={[styles.createBtn, createMutation.isPending && styles.createBtnDisabled]}
              onPress={handleCreate}
              disabled={createMutation.isPending}
            >
              <Text style={styles.createBtnText}>
                {createMutation.isPending ? 'Creando...' : 'Crear alerta'}
              </Text>
            </TouchableOpacity>
          </View>
        )}
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Alertas de Precio</Text>
        <TouchableOpacity style={styles.addBtn} onPress={() => setShowCreate(true)}>
          <Text style={styles.addBtnText}>+ Nueva</Text>
        </TouchableOpacity>
      </View>

      {isLoading ? (
        <View style={styles.centered}>
          <ActivityIndicator size="large" color="#2563eb" />
        </View>
      ) : (
        <FlatList
          data={alerts}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.list}
          renderItem={({ item }) => (
            <View style={[styles.alertCard, !item.isActive && styles.alertInactive]}>
              <View style={styles.alertTop}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.alertMedName}>{item.medication.name}</Text>
                  <Text style={styles.alertMedDetail}>
                    {item.medication.dosage} · {item.medication.pharmaceuticalForm}
                  </Text>
                </View>
                <TouchableOpacity onPress={() => handleDelete(item.id)}>
                  <Text style={styles.deleteText}>Eliminar</Text>
                </TouchableOpacity>
              </View>

              <View style={styles.alertBottom}>
                <View>
                  <Text style={styles.alertPriceLabel}>Precio objetivo</Text>
                  <Text style={styles.alertPrice}>{formatCLP(item.targetPrice)}</Text>
                </View>
                <View style={styles.alertStatus}>
                  <View style={[styles.statusDot, { backgroundColor: item.isActive ? '#16a34a' : '#9ca3af' }]} />
                  <Text style={styles.statusText}>{item.isActive ? 'Activa' : 'Pausada'}</Text>
                </View>
              </View>

              {item.lastTriggered && (
                <Text style={styles.triggeredText}>
                  Última notificación: {new Date(item.lastTriggered).toLocaleDateString('es-CL')}
                </Text>
              )}
            </View>
          )}
          ListEmptyComponent={
            <View style={styles.emptyState}>
              <Text style={styles.emptyTitle}>Sin alertas</Text>
              <Text style={styles.emptySubtitle}>
                Crea una alerta para recibir notificaciones cuando el precio de un medicamento baje
              </Text>
              <TouchableOpacity style={styles.createFirstBtn} onPress={() => setShowCreate(true)}>
                <Text style={styles.createFirstText}>Crear primera alerta</Text>
              </TouchableOpacity>
            </View>
          }
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f9fafb' },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  header: { backgroundColor: '#fff', padding: 16, borderBottomWidth: 1, borderBottomColor: '#e5e7eb', flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  title: { fontSize: 22, fontWeight: '700', color: '#111827' },
  backText: { fontSize: 15, color: '#2563eb', fontWeight: '600' },
  addBtn: { backgroundColor: '#2563eb', paddingHorizontal: 14, paddingVertical: 8, borderRadius: 8 },
  addBtnText: { color: '#fff', fontWeight: '600', fontSize: 14 },
  list: { padding: 12, paddingBottom: 24 },

  alertCard: { backgroundColor: '#fff', borderRadius: 12, padding: 16, marginBottom: 10, borderWidth: 1, borderColor: '#e5e7eb' },
  alertInactive: { opacity: 0.6 },
  alertTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' },
  alertMedName: { fontSize: 16, fontWeight: '600', color: '#111827' },
  alertMedDetail: { fontSize: 13, color: '#6b7280', marginTop: 2 },
  deleteText: { fontSize: 13, color: '#dc2626', fontWeight: '500' },
  alertBottom: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 12, paddingTop: 12, borderTopWidth: 1, borderTopColor: '#f3f4f6' },
  alertPriceLabel: { fontSize: 12, color: '#6b7280' },
  alertPrice: { fontSize: 20, fontWeight: '700', color: '#2563eb', marginTop: 2 },
  alertStatus: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  statusDot: { width: 8, height: 8, borderRadius: 4 },
  statusText: { fontSize: 13, color: '#6b7280' },
  triggeredText: { fontSize: 11, color: '#9ca3af', marginTop: 8 },

  emptyState: { alignItems: 'center', paddingTop: 60, paddingHorizontal: 32 },
  emptyTitle: { fontSize: 18, fontWeight: '600', color: '#374151' },
  emptySubtitle: { fontSize: 14, color: '#6b7280', textAlign: 'center', marginTop: 8 },
  createFirstBtn: { marginTop: 20, backgroundColor: '#2563eb', paddingHorizontal: 24, paddingVertical: 12, borderRadius: 10 },
  createFirstText: { color: '#fff', fontWeight: '600', fontSize: 15 },
  loginBtn: { marginTop: 20, backgroundColor: '#2563eb', paddingHorizontal: 24, paddingVertical: 12, borderRadius: 10 },
  loginBtnText: { color: '#fff', fontWeight: '600', fontSize: 15 },

  createForm: { padding: 16 },
  label: { fontSize: 14, fontWeight: '600', color: '#374151', marginBottom: 6, marginTop: 16 },
  input: { backgroundColor: '#fff', borderWidth: 1, borderColor: '#e5e7eb', borderRadius: 10, paddingHorizontal: 14, paddingVertical: 10, fontSize: 15, color: '#111827' },
  hint: { fontSize: 12, color: '#6b7280', marginTop: 6 },
  searchResult: { padding: 12, borderBottomWidth: 1, borderBottomColor: '#f3f4f6' },
  searchResultName: { fontSize: 15, fontWeight: '500', color: '#111827' },
  searchResultDetail: { fontSize: 12, color: '#6b7280', marginTop: 2 },
  noResults: { textAlign: 'center', color: '#6b7280', marginTop: 16 },
  selectedMed: { backgroundColor: '#eff6ff', padding: 12, borderRadius: 10 },
  selectedMedName: { fontSize: 15, fontWeight: '600', color: '#111827' },
  selectedMedDetail: { fontSize: 12, color: '#6b7280', marginTop: 2 },
  changeLink: { fontSize: 13, color: '#2563eb', fontWeight: '500', marginTop: 6 },
  createBtn: { backgroundColor: '#2563eb', paddingVertical: 14, borderRadius: 10, alignItems: 'center', marginTop: 24 },
  createBtnDisabled: { opacity: 0.6 },
  createBtnText: { color: '#fff', fontWeight: '700', fontSize: 16 },
});
