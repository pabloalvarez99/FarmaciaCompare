'use client';

import { useState } from 'react';

export default function AdminLoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center">
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-8 w-full max-w-sm">
        <h1 className="text-xl font-bold text-white mb-1">FC Admin</h1>
        <p className="text-sm text-gray-400 mb-6">Acceso restringido</p>
        <form className="space-y-4">
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-white text-sm"
          />
          <input
            type="password"
            placeholder="Contraseña"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-white text-sm"
          />
          <button
            type="submit"
            className="w-full py-2 bg-red-600 hover:bg-red-700 text-white rounded text-sm font-medium"
          >
            Ingresar
          </button>
        </form>
      </div>
    </div>
  );
}
