'use client';
import { useSearch } from '@/hooks/useSearch';
import { MedicationCard } from './MedicationCard';
import { Button } from '@/components/ui/button';
import { useRouter } from 'next/navigation';

export function SearchResults({ query, page }: { query: string; page: number }) {
  const { data, isLoading, error } = useSearch(query, page);
  const router = useRouter();

  if (isLoading) return (
    <div className="space-y-3">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="border rounded-lg p-4 animate-pulse bg-gray-50 h-24" />
      ))}
    </div>
  );
  if (error) return <p className="text-red-500 text-center py-8">Error al buscar. Intenta nuevamente.</p>;
  if (!data || data.results.length === 0) return (
    <div className="text-center py-16 text-muted-foreground">
      <p className="text-lg">No se encontraron resultados para &quot;{query}&quot;</p>
      <p className="text-sm mt-1">Intenta con otro término de búsqueda</p>
    </div>
  );

  return (
    <div>
      <p className="text-sm text-muted-foreground mb-4">{data.total} resultados para &quot;{query}&quot;</p>
      <div className="space-y-3">
        {data.results.map((med: any) => <MedicationCard key={med.id} med={med} />)}
      </div>
      {data.totalPages > 1 && (
        <div className="flex justify-center gap-2 mt-6">
          <Button variant="outline" disabled={page <= 1}
            onClick={() => router.push(`/buscar?q=${encodeURIComponent(query)}&page=${page - 1}`)}>Anterior</Button>
          <span className="py-2 px-3 text-sm text-muted-foreground">Página {page} de {data.totalPages}</span>
          <Button variant="outline" disabled={page >= data.totalPages}
            onClick={() => router.push(`/buscar?q=${encodeURIComponent(query)}&page=${page + 1}`)}>Siguiente</Button>
        </div>
      )}
    </div>
  );
}
