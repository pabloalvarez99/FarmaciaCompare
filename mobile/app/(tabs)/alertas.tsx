import { View, Text, StyleSheet } from 'react-native';

export default function AlertasScreen() {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>Alertas de Precio</Text>
      <Text style={styles.subtitle}>Recibe notificaciones cuando baje el precio de tus medicamentos</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#f9fafb' },
  title: { fontSize: 20, fontWeight: '600', color: '#111827' },
  subtitle: { fontSize: 14, color: '#6b7280', marginTop: 4, textAlign: 'center', paddingHorizontal: 32 },
});
