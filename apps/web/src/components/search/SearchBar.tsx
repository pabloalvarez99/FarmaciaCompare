'use client';
import { useState, useCallback, useRef, useEffect, KeyboardEvent } from 'react';
import { useRouter } from 'next/navigation';
import { Search } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { formatCLP } from '@/lib/utils';

interface SearchBarProps {
  defaultValue?: string;
  size?: 'default' | 'sm' | 'lg';
  /** Form submit target. Default `comparar` surfaces multi-chain savings first. */
  destination?: 'comparar' | 'precios';
}

interface Suggestion {
  id: string;
  name: string;
  price: number;
  pharmacy: string;
}

/**
 * Suggestions come from the scraped-product search. They used to be drawn from
 * the demo dataset, which meant the very first thing a visitor typed returned
 * invented products at invented prices.
 *
 * Form submit goes to /comparar (product value: where is it cheaper). Clicking a
 * suggestion still opens that listing on /precios — a specific pharmacy price.
 */
export function SearchBar({
  defaultValue = '',
  size = 'default',
  destination = 'comparar',
}: SearchBarProps) {
  const [query, setQuery] = useState(defaultValue);
  const [open, setOpen] = useState(false);
  const [activeIdx, setActiveIdx] = useState(-1);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const router = useRouter();
  const containerRef = useRef<HTMLDivElement>(null);

  const goToSearch = useCallback(
    (term: string) => {
      setOpen(false);
      router.push(`/${destination}?q=${encodeURIComponent(term)}`);
    },
    [router, destination],
  );

  /** Specific pharmacy listing from autocomplete. */
  const goToListing = useCallback(
    (term: string) => {
      setOpen(false);
      router.push(`/precios?q=${encodeURIComponent(term)}`);
    },
    [router],
  );

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      if (query.trim().length >= 2) goToSearch(query.trim());
    },
    [query, goToSearch],
  );

  // Debounced lookup; aborts the in-flight request so results cannot arrive out
  // of order and overwrite a newer query.
  useEffect(() => {
    const term = query.trim();
    if (term.length < 2) {
      setSuggestions([]);
      return;
    }

    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const res = await fetch(
          `/api/v1/medications/search?q=${encodeURIComponent(term)}&limit=6`,
          { signal: controller.signal },
        );
        if (!res.ok) return;
        const data = await res.json();
        setSuggestions(
          (data.results ?? []).map((r: any) => ({
            id: r.id,
            name: r.name,
            price: r.price,
            pharmacy: (r.pharmacy?.name ?? '').replace(' (Online)', ''),
          })),
        );
      } catch {
        // Aborted or offline: keep whatever is on screen.
      }
    }, 250);

    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [query]);

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
      const item = suggestions[activeIdx];
      if (item) goToListing(item.name);
    } else if (e.key === 'Escape') {
      setOpen(false);
      setActiveIdx(-1);
    }
  };

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
          placeholder="Buscar medicamento, marca o principio activo..."
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
            setActiveIdx(-1);
          }}
          onFocus={() => {
            if (query.trim().length >= 2) setOpen(true);
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
            {suggestions.map((item, i) => (
              <button
                key={item.id}
                type="button"
                role="option"
                aria-selected={i === activeIdx}
                onClick={() => goToListing(item.name)}
                className={`flex w-full items-center justify-between px-4 py-3 border-b last:border-b-0 text-left transition-colors ${
                  i === activeIdx ? 'bg-blue-50' : 'hover:bg-gray-50'
                }`}
              >
                <div className="min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate">{item.name}</p>
                  <p className="text-xs text-gray-400">{item.pharmacy}</p>
                </div>
                <div className="text-right ml-4 shrink-0">
                  <p className="text-sm font-bold text-blue-600">{formatCLP(item.price)}</p>
                </div>
              </button>
            ))}
            {query.trim().length >= 2 && (
              <button
                type="submit"
                className="w-full px-4 py-2.5 text-sm text-blue-600 hover:bg-blue-50 text-left border-t border-gray-100 transition-colors"
              >
                Comparar precios de &ldquo;{query.trim()}&rdquo; →
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
