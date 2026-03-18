import { Suspense } from 'react';
import { SearchBar } from '@/components/search/SearchBar';
import { SearchResults } from '@/components/search/SearchResults';

interface Props {
  searchParams: { q?: string; page?: string };
}

export default function BuscarPage({ searchParams }: Props) {
  const query = searchParams.q ?? '';
  const page = parseInt(searchParams.page ?? '1');
  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <div className="mb-6"><SearchBar defaultValue={query} /></div>
      {query.length >= 2 ? (
        <Suspense fallback={<div className="space-y-3">{Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="border rounded-lg p-4 animate-pulse bg-gray-50 h-24" />))}</div>}>
          <SearchResults query={query} page={page} />
        </Suspense>
      ) : (
        <div className="text-center text-muted-foreground py-16"><p>Ingresa al menos 2 caracteres para buscar</p></div>
      )}
    </div>
  );
}
