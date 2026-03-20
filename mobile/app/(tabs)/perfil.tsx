import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { useAuthStore } from '@/stores/authStore';
import { useRouter } from 'expo-router';

export default function PerfilScreen() {
  const { user, logout } = useAuthStore();
  const router = useRouter();

  if (!user) {
    return (
      <View style={styles.container}>
        <Text style={styles.title}>Mi Perfil</Text>
        <TouchableOpacity style={styles.button} onPress={() => router.push('/(auth)/login')}>
          <Text style={styles.buttonText}>Iniciar sesión</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>{user.name ?? user.email}</Text>
      <Text style={styles.email}>{user.email}</Text>
      <TouchableOpacity style={[styles.button, { backgroundColor: '#ef4444' }]} onPress={logout}>
        <Text style={styles.buttonText}>Cerrar sesión</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#f9fafb', padding: 16 },
  title: { fontSize: 20, fontWeight: '600', color: '#111827' },
  email: { fontSize: 14, color: '#6b7280', marginTop: 4 },
  button: { marginTop: 24, backgroundColor: '#2563eb', paddingHorizontal: 24, paddingVertical: 12, borderRadius: 10 },
  buttonText: { color: '#fff', fontWeight: '600', fontSize: 16 },
});
