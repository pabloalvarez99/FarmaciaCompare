'use client';
import { useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Search } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';

interface SearchBarProps {
  defaultValue?: string;
  size?: 'default' | 'sm' | 'lg';
}

export function SearchBar({ defaultValue = '', size = 'default' }: SearchBarProps) {
  const [query, setQuery] = useState(defaultValue);
  const router = useRouter();
  const handleSubmit = useCallback((e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim().length >= 2) {
      router.push(`/buscar?q=${encodeURIComponent(query.trim())}`);
    }
  }, [query, router]);

  return (
    <form onSubmit={handleSubmit} className="flex gap-2 w-full">
      <div className="relative flex-1">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground h-4 w-4" />
        <Input type="search" placeholder="Buscar medicamento, principio activo..." value={query}
          onChange={(e) => setQuery(e.target.value)} className={`pl-10 ${size === 'lg' ? 'h-12 text-base' : ''}`} autoComplete="off" />
      </div>
      <Button type="submit" disabled={query.trim().length < 2}>Buscar</Button>
    </form>
  );
}
