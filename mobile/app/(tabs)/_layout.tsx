import { Tabs } from 'expo-router';
import { Search, MapPin, Bell, User } from 'lucide-react-native';

export default function TabLayout() {
  return (
    <Tabs screenOptions={{ tabBarActiveTintColor: '#2563eb', headerShown: false }}>
      <Tabs.Screen name="index" options={{ title: 'Buscar', tabBarIcon: ({ color }) => <Search color={color} size={22} /> }} />
      <Tabs.Screen name="mapa" options={{ title: 'Mapa', tabBarIcon: ({ color }) => <MapPin color={color} size={22} /> }} />
      <Tabs.Screen name="alertas" options={{ title: 'Alertas', tabBarIcon: ({ color }) => <Bell color={color} size={22} /> }} />
      <Tabs.Screen name="perfil" options={{ title: 'Perfil', tabBarIcon: ({ color }) => <User color={color} size={22} /> }} />
    </Tabs>
  );
}
