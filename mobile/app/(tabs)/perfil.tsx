import { useState } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  TextInput,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { useAuthStore } from '../../src/stores/authStore';
import { useRouter } from 'expo-router';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../src/lib/api';

interface UserProfile {
  id: string;
  email: string;
  name: string | null;
  phone: string | null;
  createdAt: string;
}

export default function PerfilScreen() {
  const { user, logout, checkAuth } = useAuthStore();
  const router = useRouter();
  const queryClient = useQueryClient();

  const [editing, setEditing] = useState(false);
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');

  const { data: profile, isLoading } = useQuery<UserProfile>({
    queryKey: ['user-profile'],
    queryFn: () => api.get('/users/me').then((r) => r.data),
    enabled: !!user,
    onSuccess: (data: UserProfile) => {
      setName(data.name || '');
      setPhone(data.phone || '');
    },
  } as any);

  const updateMutation = useMutation({
    mutationFn: (body: { name: string; phone: string }) => api.put('/users/me', body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['user-profile'] });
      checkAuth();
      setEditing(false);
      Alert.alert('Perfil actualizado');
    },
  });

  const handleLogout = () => {
    Alert.alert('Cerrar sesión', '¿Estás seguro?', [
      { text: 'Cancelar', style: 'cancel' },
      {
        text: 'Cerrar sesión',
        style: 'destructive',
        onPress: () => {
          logout();
          queryClient.clear();
        },
      },
    ]);
  };

  if (!user) {
    return (
      <View style={styles.centered}>
        <View style={styles.avatarPlaceholder}>
          <Text style={styles.avatarText}>?</Text>
        </View>
        <Text style={styles.guestTitle}>Mi Cuenta</Text>
        <Text style={styles.guestSubtitle}>
          Inicia sesión para ver tu perfil, pedidos y alertas de precio
        </Text>
        <TouchableOpacity style={styles.primaryBtn} onPress={() => router.push('/(auth)/login')}>
          <Text style={styles.primaryBtnText}>Iniciar sesión</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.secondaryBtn} onPress={() => router.push('/(auth)/register')}>
          <Text style={styles.secondaryBtnText}>Crear cuenta</Text>
        </TouchableOpacity>
      </View>
    );
  }

  if (isLoading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color="#2563eb" />
      </View>
    );
  }

  const initials = (profile?.name || profile?.email || '?')
    .split(' ')
    .map((w) => w[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();

  const memberSince = profile?.createdAt
    ? new Date(profile.createdAt).toLocaleDateString('es-CL', { year: 'numeric', month: 'long' })
    : '';

  return (
    <ScrollView style={styles.container} contentContainerStyle={{ paddingBottom: 40 }}>
      <View style={styles.profileHeader}>
        <View style={styles.avatar}>
          <Text style={styles.avatarInitials}>{initials}</Text>
        </View>
        <Text style={styles.profileName}>{profile?.name || 'Sin nombre'}</Text>
        <Text style={styles.profileEmail}>{profile?.email}</Text>
        {memberSince && <Text style={styles.memberSince}>Miembro desde {memberSince}</Text>}
      </View>

      <View style={styles.section}>
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>Información personal</Text>
          {!editing && (
            <TouchableOpacity onPress={() => setEditing(true)}>
              <Text style={styles.editLink}>Editar</Text>
            </TouchableOpacity>
          )}
        </View>

        {editing ? (
          <View style={styles.editForm}>
            <Text style={styles.label}>Nombre</Text>
            <TextInput
              style={styles.input}
              value={name}
              onChangeText={setName}
              placeholder="Tu nombre"
              placeholderTextColor="#9ca3af"
            />
            <Text style={styles.label}>Teléfono</Text>
            <TextInput
              style={styles.input}
              value={phone}
              onChangeText={setPhone}
              placeholder="+56 9 1234 5678"
              placeholderTextColor="#9ca3af"
              keyboardType="phone-pad"
            />
            <View style={styles.editActions}>
              <TouchableOpacity
                style={styles.cancelBtn}
                onPress={() => {
                  setEditing(false);
                  setName(profile?.name || '');
                  setPhone(profile?.phone || '');
                }}
              >
                <Text style={styles.cancelBtnText}>Cancelar</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.saveBtn, updateMutation.isPending && { opacity: 0.6 }]}
                onPress={() => updateMutation.mutate({ name, phone })}
                disabled={updateMutation.isPending}
              >
                <Text style={styles.saveBtnText}>
                  {updateMutation.isPending ? 'Guardando...' : 'Guardar'}
                </Text>
              </TouchableOpacity>
            </View>
          </View>
        ) : (
          <View style={styles.infoRows}>
            <View style={styles.infoRow}>
              <Text style={styles.infoLabel}>Nombre</Text>
              <Text style={styles.infoValue}>{profile?.name || 'No especificado'}</Text>
            </View>
            <View style={styles.infoRow}>
              <Text style={styles.infoLabel}>Email</Text>
              <Text style={styles.infoValue}>{profile?.email}</Text>
            </View>
            <View style={styles.infoRow}>
              <Text style={styles.infoLabel}>Teléfono</Text>
              <Text style={styles.infoValue}>{profile?.phone || 'No especificado'}</Text>
            </View>
          </View>
        )}
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Acciones</Text>
        <TouchableOpacity style={styles.menuItem} onPress={() => router.push('/(tabs)/alertas')}>
          <Text style={styles.menuText}>Mis alertas de precio</Text>
          <Text style={styles.menuArrow}>→</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.menuItem}>
          <Text style={styles.menuText}>Mis pedidos</Text>
          <Text style={styles.menuArrow}>→</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.menuItem}>
          <Text style={styles.menuText}>Notificaciones</Text>
          <Text style={styles.menuArrow}>→</Text>
        </TouchableOpacity>
      </View>

      <TouchableOpacity style={styles.logoutBtn} onPress={handleLogout}>
        <Text style={styles.logoutText}>Cerrar sesión</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f9fafb' },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#f9fafb', paddingHorizontal: 32 },

  avatarPlaceholder: { width: 72, height: 72, borderRadius: 36, backgroundColor: '#e5e7eb', justifyContent: 'center', alignItems: 'center' },
  avatarText: { fontSize: 28, fontWeight: '700', color: '#9ca3af' },
  guestTitle: { fontSize: 22, fontWeight: '700', color: '#111827', marginTop: 16 },
  guestSubtitle: { fontSize: 14, color: '#6b7280', textAlign: 'center', marginTop: 8 },
  primaryBtn: { marginTop: 24, backgroundColor: '#2563eb', paddingHorizontal: 32, paddingVertical: 14, borderRadius: 10, width: '100%', alignItems: 'center' },
  primaryBtnText: { color: '#fff', fontWeight: '700', fontSize: 16 },
  secondaryBtn: { marginTop: 10, paddingHorizontal: 32, paddingVertical: 14, borderRadius: 10, width: '100%', alignItems: 'center', borderWidth: 1, borderColor: '#e5e7eb' },
  secondaryBtnText: { color: '#374151', fontWeight: '600', fontSize: 16 },

  profileHeader: { backgroundColor: '#fff', alignItems: 'center', paddingVertical: 28, paddingHorizontal: 16, borderBottomWidth: 1, borderBottomColor: '#e5e7eb' },
  avatar: { width: 72, height: 72, borderRadius: 36, backgroundColor: '#2563eb', justifyContent: 'center', alignItems: 'center' },
  avatarInitials: { fontSize: 26, fontWeight: '700', color: '#fff' },
  profileName: { fontSize: 20, fontWeight: '700', color: '#111827', marginTop: 12 },
  profileEmail: { fontSize: 14, color: '#6b7280', marginTop: 2 },
  memberSince: { fontSize: 12, color: '#9ca3af', marginTop: 4 },

  section: { backgroundColor: '#fff', marginTop: 12, paddingVertical: 16, paddingHorizontal: 16, borderTopWidth: 1, borderBottomWidth: 1, borderColor: '#e5e7eb' },
  sectionHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  sectionTitle: { fontSize: 16, fontWeight: '600', color: '#374151' },
  editLink: { fontSize: 14, color: '#2563eb', fontWeight: '500' },

  infoRows: { gap: 12 },
  infoRow: { flexDirection: 'row', justifyContent: 'space-between' },
  infoLabel: { fontSize: 14, color: '#6b7280' },
  infoValue: { fontSize: 14, color: '#111827', fontWeight: '500' },

  editForm: {},
  label: { fontSize: 13, fontWeight: '600', color: '#374151', marginBottom: 4, marginTop: 12 },
  input: { backgroundColor: '#f9fafb', borderWidth: 1, borderColor: '#e5e7eb', borderRadius: 8, paddingHorizontal: 12, paddingVertical: 10, fontSize: 15, color: '#111827' },
  editActions: { flexDirection: 'row', gap: 10, marginTop: 16 },
  cancelBtn: { flex: 1, paddingVertical: 12, borderRadius: 8, alignItems: 'center', borderWidth: 1, borderColor: '#e5e7eb' },
  cancelBtnText: { fontWeight: '600', color: '#6b7280' },
  saveBtn: { flex: 1, paddingVertical: 12, borderRadius: 8, alignItems: 'center', backgroundColor: '#2563eb' },
  saveBtnText: { fontWeight: '600', color: '#fff' },

  menuItem: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 14, borderBottomWidth: 1, borderBottomColor: '#f3f4f6' },
  menuText: { fontSize: 15, color: '#111827' },
  menuArrow: { fontSize: 16, color: '#9ca3af' },

  logoutBtn: { marginTop: 24, marginHorizontal: 16, paddingVertical: 14, borderRadius: 10, alignItems: 'center', backgroundColor: '#fef2f2', borderWidth: 1, borderColor: '#fecaca' },
  logoutText: { fontSize: 15, fontWeight: '600', color: '#dc2626' },
});
