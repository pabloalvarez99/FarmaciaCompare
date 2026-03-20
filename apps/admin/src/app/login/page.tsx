'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

export default function AdminLoginPage() {
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
        `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:4000/api/v1'}/auth/login`,
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
      localStorage.setItem('admin_token', data.accessToken);
      document.cookie = `adminToken=${data.accessToken}; path=/; max-age=86400`;
      router.push('/');
    } catch {
      setError('Error de conexión');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center">
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-8 w-full max-w-sm">
        <h1 className="text-xl font-bold text-white mb-1">FC Admin</h1>
        <p className="text-sm text-gray-400 mb-6">Acceso restringido</p>

        {error && (
          <div className="bg-red-900/30 border border-red-800 text-red-400 text-sm px-3 py-2 rounded mb-4">{error}</div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <input
            type="email"
            required
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-white text-sm focus:ring-2 focus:ring-red-500 focus:border-red-500 outline-none"
          />
          <input
            type="password"
            required
            placeholder="Contraseña"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-white text-sm focus:ring-2 focus:ring-red-500 focus:border-red-500 outline-none"
          />
          <button
            type="submit"
            disabled={loading}
            className="w-full py-2 bg-red-600 hover:bg-red-700 text-white rounded text-sm font-medium disabled:opacity-50"
          >
            {loading ? 'Ingresando...' : 'Ingresar'}
          </button>
        </form>
      </div>
    </div>
  );
}
