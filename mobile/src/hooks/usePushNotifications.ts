import { useEffect } from 'react';
import { api } from '@/lib/api';

export function usePushNotifications() {
  useEffect(() => {
    (async () => {
      try {
        const Notifications = require('expo-notifications');
        const { status } = await Notifications.requestPermissionsAsync();
        if (status !== 'granted') return;
        const token = (await Notifications.getExpoPushTokenAsync()).data;
        await api.post('/users/push-token', { token });
      } catch {}
    })();
  }, []);
}
