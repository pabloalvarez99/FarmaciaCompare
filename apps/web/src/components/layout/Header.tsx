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

  return (
    <header className="sticky top-0 z-50 bg-white/95 backdrop-blur border-b border-gray-200">
      <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between gap-4">
        <Link href="/" className="flex items-center gap-2 shrink-0">
          <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
            <span className="text-white font-bold text-sm">FC</span>
          </div>
          <span className="font-semibold text-gray-900 hidden sm:block">FarmaciaCompare</span>
        </Link>

        {!isHome && (
          <div className="min-w-0 flex-1 max-w-md">
            <SearchBar size="sm" />
          </div>
        )}

        <nav className="flex items-center gap-1 sm:gap-2">
          {/* Comparar is the savings surface (catalog + barcode groups). Precios
              is the full listing search. Both stay visible: phones need the
              money path first. */}
          <Link
            href="/comparar"
            className={`px-2 sm:px-3 py-1.5 text-sm rounded-lg transition-colors ${
              pathname.startsWith('/comparar')
                ? 'bg-blue-50 font-medium text-blue-700'
                : 'text-gray-700 hover:text-blue-700 hover:bg-blue-50'
            }`}
          >
            Comparar
          </Link>
          <Link
            href="/precios"
            className={`px-2 sm:px-3 py-1.5 text-sm rounded-lg transition-colors ${
              pathname.startsWith('/precios')
                ? 'bg-blue-50 font-medium text-blue-700'
                : 'text-gray-700 hover:text-blue-700 hover:bg-blue-50'
            }`}
          >
            Precios
          </Link>
          <Link
            href="/farmacias"
            className={`hidden px-2 sm:px-3 py-1.5 text-sm rounded-lg transition-colors sm:inline ${
              pathname.startsWith('/farmacias')
                ? 'bg-blue-50 font-medium text-blue-700'
                : 'text-gray-700 hover:text-blue-700 hover:bg-blue-50'
            }`}
          >
            Farmacias
          </Link>
          {user ? (
            <div className="relative">
              <button
                onClick={() => setMenuOpen(!menuOpen)}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg hover:bg-gray-100 transition-colors"
              >
                <div className="w-7 h-7 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-xs font-medium">
                  {user.name?.charAt(0)?.toUpperCase() || user.email.charAt(0).toUpperCase()}
                </div>
                <span className="text-sm text-gray-700 hidden md:block">{user.name || user.email}</span>
              </button>
              {menuOpen && (
                <div className="absolute right-0 mt-1 w-48 bg-white border border-gray-200 rounded-lg shadow-lg py-1 z-50">
                  <Link
                    href="/cuenta"
                    className="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
                    onClick={() => setMenuOpen(false)}
                  >
                    Mi cuenta
                  </Link>
                  <Link
                    href="/pedidos"
                    className="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
                    onClick={() => setMenuOpen(false)}
                  >
                    Mis pedidos
                  </Link>
                  <Link
                    href="/alertas"
                    className="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
                    onClick={() => setMenuOpen(false)}
                  >
                    Alertas de precio
                  </Link>
                  <hr className="my-1 border-gray-100" />
                  <button
                    onClick={handleLogout}
                    className="block w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-red-50"
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
                className="hidden px-3 py-1.5 text-sm text-gray-600 transition-colors hover:text-gray-900 sm:inline"
              >
                Ingresar
              </Link>
              {/* Hidden on phones: nav keeps Comparar + Precios only; auth is
                  secondary until alerts matter. Ingresar already sm-only. */}
              <Link
                href="/registro"
                className="hidden px-4 py-1.5 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors sm:inline"
              >
                Crear cuenta
              </Link>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}
