'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';

export default function RegisterPage() {
  const router = useRouter();
  const [form, setForm] = useState({ name: '', email: '', password: '', confirmPassword: '' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const update = (field: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [field]: e.target.value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (form.password !== form.confirmPassword) {
      setError('Las contraseñas no coinciden');
      return;
    }
    if (form.password.length < 8) {
      setError('La contraseña debe tener al menos 8 caracteres');
      return;
    }

    setLoading(true);
    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/v1/auth/register`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: form.name,
            email: form.email,
            password: form.password,
          }),
        },
      );
      const data = await res.json();
      if (!res.ok) {
        setError(data.message || 'Error al crear la cuenta');
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
          <h1 className="text-2xl font-bold text-foreground">Crear cuenta</h1>
          <p className="text-sm text-muted-foreground mt-1">Recibe alertas de precio y guarda tus medicamentos</p>
        </div>

        <form onSubmit={handleSubmit} className="bg-card rounded-xl border border-edge p-6 space-y-4">
          {error && (
            <div className="bg-high-tint text-high text-sm px-3 py-2 rounded-lg border border-high/25">
              {error}
            </div>
          )}

          <div>
            <label htmlFor="name" className="block text-sm font-medium text-foreground mb-1">
              Nombre
            </label>
            <input
              id="name"
              type="text"
              required
              value={form.name}
              onChange={update('name')}
              className="w-full px-3 py-2 border border-edge rounded-lg text-sm focus:border-foreground outline-none"
              placeholder="Tu nombre"
            />
          </div>

          <div>
            <label htmlFor="email" className="block text-sm font-medium text-foreground mb-1">
              Correo electrónico
            </label>
            <input
              id="email"
              type="email"
              required
              value={form.email}
              onChange={update('email')}
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
              value={form.password}
              onChange={update('password')}
              className="w-full px-3 py-2 border border-edge rounded-lg text-sm focus:border-foreground outline-none"
              placeholder="Mínimo 8 caracteres"
            />
          </div>

          <div>
            <label htmlFor="confirmPassword" className="block text-sm font-medium text-foreground mb-1">
              Confirmar contraseña
            </label>
            <input
              id="confirmPassword"
              type="password"
              required
              value={form.confirmPassword}
              onChange={update('confirmPassword')}
              className="w-full px-3 py-2 border border-edge rounded-lg text-sm focus:border-foreground outline-none"
              placeholder="Repetir contraseña"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 bg-foreground text-white text-sm font-medium rounded-lg hover:bg-foreground/90 disabled:opacity-50 transition-colors"
          >
            {loading ? 'Creando cuenta...' : 'Crear cuenta'}
          </button>
        </form>

        <p className="text-center text-sm text-muted-foreground mt-4">
          ¿Ya tienes cuenta?{' '}
          <Link href="/login" className="text-foreground hover:underline font-medium">
            Ingresar
          </Link>
        </p>
      </div>
    </div>
  );
}
