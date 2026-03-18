import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';

export function useSearch(query: string, page = 1) {
  return useQuery({
    queryKey: ['medications', 'search', query, page],
    queryFn: async () => {
      const { data } = await apiClient.get('/medications/search', { params: { q: query, page, limit: 20 } });
      return data;
    },
    enabled: query.length >= 2,
    staleTime: 60 * 1000,
  });
}
