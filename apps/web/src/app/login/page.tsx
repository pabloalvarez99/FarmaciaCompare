'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/v1/auth/login`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password }),
        },
      );
      const data = await res.json();
      if (!res.ok) {
        setError(data.message || 'Credenciales incorrectas');
        return;
      }
      localStorage.setItem('accessToken', data.accessToken);
      localStorage.setItem('refreshToken', data.refreshToken);
      router.push('/');
    } catch {
      setError('Error de conexión. Intente nuevamente.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-muted/60 px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="w-12 h-12 bg-foreground rounded-xl flex items-center justify-center mx-auto mb-4">
            <span className="text-white font-bold text-lg">FC</span>
          </div>
          <h1 className="text-2xl font-bold text-foreground">Ingresar</h1>
          <p className="text-sm text-muted-foreground mt-1">Compara precios y ahorra en tus medicamentos</p>
        </div>

        <form onSubmit={handleSubmit} className="bg-card rounded-xl border border-edge p-6 space-y-4">
          {error && (
            <div className="bg-high-tint text-high text-sm px-3 py-2 rounded-lg border border-high/25">
              {error}
            </div>
          )}

          <div>
            <label htmlFor="email" className="block text-sm font-medium text-foreground mb-1">
              Correo electrónico
            </label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-3 py-2 border border-edge rounded-lg text-sm focus:border-foreground outline-none"
              placeholder="tu@email.com"
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-foreground mb-1">
              Contraseña
            </label>
            <input
              id="password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2 border border-edge rounded-lg text-sm focus:border-foreground outline-none"
              placeholder="••••••••"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 bg-foreground text-white text-sm font-medium rounded-lg hover:bg-foreground/90 disabled:opacity-50 transition-colors"
          >
            {loading ? 'Ingresando...' : 'Ingresar'}
          </button>
        </form>

        <p className="text-center text-sm text-muted-foreground mt-4">
          ¿No tienes cuenta?{' '}
          <Link href="/registro" className="text-foreground hover:underline font-medium">
            Crear cuenta
          </Link>
        </p>
      </div>
    </div>
  );
}
