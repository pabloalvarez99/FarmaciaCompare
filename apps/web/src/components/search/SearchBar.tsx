'use client';
import { useState, useCallback, useRef, useEffect, KeyboardEvent } from 'react';
import { useRouter } from 'next/navigation';
import { Search } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { searchMedications } from '@/lib/demo-data';
import { formatCLP } from '@/lib/utils';
import Link from 'next/link';

interface SearchBarProps {
  defaultValue?: string;
  size?: 'default' | 'sm' | 'lg';
}

export function SearchBar({ defaultValue = '', size = 'default' }: SearchBarProps) {
  const [query, setQuery] = useState(defaultValue);
  const [open, setOpen] = useState(false);
  const [activeIdx, setActiveIdx] = useState(-1);
  const router = useRouter();
  const containerRef = useRef<HTMLDivElement>(null);

  const suggestions = query.trim().length >= 1
    ? searchMedications(query.trim()).slice(0, 6)
    : [];

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      setOpen(false);
      if (query.trim().length >= 2) {
        router.push(`/buscar?q=${encodeURIComponent(query.trim())}`);
      }
    },
    [query, router],
  );

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (!open || suggestions.length === 0) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIdx((i) => Math.min(i + 1, suggestions.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIdx((i) => Math.max(i - 1, -1));
    } else if (e.key === 'Enter' && activeIdx >= 0) {
      e.preventDefault();
      const med = suggestions[activeIdx];
      if (med) {
        setOpen(false);
        router.push(`/medicamentos/${med.id}`);
      }
    } else if (e.key === 'Escape') {
      setOpen(false);
      setActiveIdx(-1);
    }
  };

  // Close when clicking outside
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <form onSubmit={handleSubmit} className="flex gap-2 w-full">
      <div className="relative flex-1" ref={containerRef}>
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground h-4 w-4 z-10 pointer-events-none" />
        <Input
          type="search"
          placeholder="Buscar medicamento, principio activo..."
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
            setActiveIdx(-1);
          }}
          onFocus={() => {
            if (query.trim().length >= 1) setOpen(true);
          }}
          onKeyDown={handleKeyDown}
          className={`pl-10 ${size === 'lg' ? 'h-12 text-base' : ''}`}
          autoComplete="off"
          aria-autocomplete="list"
          aria-expanded={open && suggestions.length > 0}
        />

        {open && suggestions.length > 0 && (
          <div
            role="listbox"
            className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-xl z-50 overflow-hidden"
          >
            {suggestions.map((med, i) => (
              <Link
                key={med.id}
                href={`/medicamentos/${med.id}`}
                role="option"
                aria-selected={i === activeIdx}
                onClick={() => {
                  setOpen(false);
                  setQuery(med.name);
                }}
                className={`flex items-center justify-between px-4 py-3 border-b last:border-b-0 transition-colors ${
                  i === activeIdx ? 'bg-blue-50' : 'hover:bg-gray-50'
                }`}
              >
                <div className="min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate">{med.name}</p>
                  <p className="text-xs text-gray-400">
                    {med.activeIngredient.name} · {med.dosage} · {med.pharmaceuticalForm}
                  </p>
                </div>
                {med.prices[0] && (
                  <div className="text-right ml-4 shrink-0">
                    <p className="text-xs text-gray-400">Desde</p>
                    <p className="text-sm font-bold text-blue-600">
                      {formatCLP(med.prices[0].price)}
                    </p>
                  </div>
                )}
              </Link>
            ))}
            {query.trim().length >= 2 && (
              <button
                type="submit"
                className="w-full px-4 py-2.5 text-sm text-blue-600 hover:bg-blue-50 text-left border-t border-gray-100 transition-colors"
              >
                Ver todos los resultados para &ldquo;{query.trim()}&rdquo; →
              </button>
            )}
          </div>
        )}
      </div>
      <Button type="submit" disabled={query.trim().length < 2}>
        Buscar
      </Button>
    </form>
  );
}
