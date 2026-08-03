'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState, useEffect } from 'react';
import { SearchBar } from '../search/SearchBar';

export function Header() {
  const pathname = usePathname();
  const isHome = pathname === '/';
  const [user, setUser] = useState<{ name: string; email: string } | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem('accessToken');
    if (token) {
      fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/users/me`, {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then((r) => (r.ok ? r.json() : null))
        .then((data) => setUser(data))
        .catch(() => setUser(null));
    }
  }, []);

  const handleLogout = () => {
    localStorage.removeItem('accessToken');
    localStorage.removeItem('refreshToken');
    setUser(null);
    window.location.href = '/';
  };

  // One treatment for every nav item: an ink underline on the current section.
  // Colour is reserved for money, so "where am I" is drawn, not tinted.
  const navLink = (href: string) =>
    `rounded px-2 py-1.5 text-sm transition-colors sm:px-3 ${
      pathname.startsWith(href)
        ? 'font-semibold text-foreground underline decoration-2 underline-offset-8'
        : 'text-muted-foreground hover:text-foreground'
    }`;

  return (
    <header className="sticky top-0 z-50 border-b border-edge bg-card/95 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4">
        <Link href="/" className="flex shrink-0 items-center gap-2">
          {/* The mark is the spread itself: a short ink bar and a long green
              one — the cheapest price and the money left on the table. */}
          <span
            aria-hidden
            className="flex h-8 w-8 flex-col items-center justify-center gap-1 rounded-md bg-foreground px-1.5"
          >
            <span className="h-[3px] w-2.5 self-start rounded-full bg-white" />
            <span className="h-[3px] w-full rounded-full bg-save" />
          </span>
          <span className="display hidden font-semibold text-foreground sm:block">
            FarmaciaCompare
          </span>
        </Link>

        {!isHome && (
          <div className="min-w-0 max-w-md flex-1">
            <SearchBar size="sm" />
          </div>
        )}

        <nav className="flex items-center gap-1 sm:gap-2">
          {/* Comparar is the savings surface (catalog + barcode groups). Precios
              is the full listing search. Both stay visible: phones need the
              money path first. */}
          <Link
            href="/comparar"
            aria-current={pathname.startsWith('/comparar') ? 'page' : undefined}
            className={navLink('/comparar')}
          >
            Comparar
          </Link>
          <Link
            href="/precios"
            aria-current={pathname.startsWith('/precios') ? 'page' : undefined}
            className={navLink('/precios')}
          >
            Precios
          </Link>
          <Link
            href="/farmacias"
            aria-current={pathname.startsWith('/farmacias') ? 'page' : undefined}
            className={`hidden sm:inline ${navLink('/farmacias')}`}
          >
            Farmacias
          </Link>
          {user ? (
            <div className="relative">
              <button
                onClick={() => setMenuOpen(!menuOpen)}
                aria-expanded={menuOpen}
                aria-haspopup="menu"
                className="flex items-center gap-2 rounded-md px-3 py-1.5 transition-colors hover:bg-muted"
              >
                <span className="flex h-7 w-7 items-center justify-center rounded-full bg-muted text-xs font-semibold text-foreground">
                  {user.name?.charAt(0)?.toUpperCase() || user.email.charAt(0).toUpperCase()}
                </span>
                <span className="hidden text-sm text-foreground md:block">
                  {user.name || user.email}
                </span>
              </button>
              {menuOpen && (
                <div className="absolute right-0 z-50 mt-1 w-48 rounded-lg border border-edge bg-card py-1 shadow-lg">
                  <Link
                    href="/cuenta"
                    className="block px-4 py-2 text-sm text-foreground hover:bg-muted"
                    onClick={() => setMenuOpen(false)}
                  >
                    Mi cuenta
                  </Link>
                  <Link
                    href="/pedidos"
                    className="block px-4 py-2 text-sm text-foreground hover:bg-muted"
                    onClick={() => setMenuOpen(false)}
                  >
                    Mis pedidos
                  </Link>
                  <Link
                    href="/alertas"
                    className="block px-4 py-2 text-sm text-foreground hover:bg-muted"
                    onClick={() => setMenuOpen(false)}
                  >
                    Alertas de precio
                  </Link>
                  <hr className="my-1 border-edge" />
                  <button
                    onClick={handleLogout}
                    className="block w-full px-4 py-2 text-left text-sm text-high hover:bg-high-tint"
                  >
                    Cerrar sesión
                  </button>
                </div>
              )}
            </div>
          ) : (
            <>
              {/* Hidden on phones: with the search field in the same row there
                  is no space for two auth links, and an account buys nothing
                  until alerts ship. /registro links to /login anyway. */}
              <Link
                href="/login"
                className="hidden px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground sm:inline"
              >
                Ingresar
              </Link>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}
