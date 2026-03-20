'use client';

import { useEffect, useState } from 'react';

export function useOrderStream() {
  const [orders, setOrders] = useState<any[]>([]);

  useEffect(() => {
    const apiUrl =
      process.env.NEXT_PUBLIC_API_URL || 'http://localhost:4000/api/v1';
    const token = localStorage.getItem('access_token');
    if (!token) return;

    const es = new EventSource(
      `${apiUrl}/dashboard/orders/stream?token=${token}`,
    );
    es.onmessage = (e) => {
      setOrders(JSON.parse(e.data));
    };
    return () => es.close();
  }, []);

  return orders;
}
