'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { apiClient } from '@/lib/api-client';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

interface UserProfile {
  id: string;
  email: string;
  name: string | null;
  phone: string | null;
  createdAt: string;
}

export default function CuentaPage() {
  const router = useRouter();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem('accessToken');
    if (!token) { router.push('/login'); return; }
    apiClient
      .get('/users/me')
      .then((r) => {
        setProfile(r.data);
        setName(r.data.name || '');
        setPhone(r.data.phone || '');
      })
      .catch(() => router.push('/login'))
      .finally(() => setLoading(false));
  }, [router]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const { data } = await apiClient.put('/users/me', { name, phone });
      setProfile(data);
      setEditing(false);
    } catch { /* noop */ }
    setSaving(false);
  };

  if (loading) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-12">
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-12 bg-muted rounded animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (!profile) return null;

  const initials = (profile.name || profile.email)
    .split(' ')
    .map((w) => w[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();

  const memberSince = new Date(profile.createdAt).toLocaleDateString('es-CL', {
    year: 'numeric',
    month: 'long',
  });

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold text-foreground mb-6">Mi Cuenta</h1>

      <Card className="p-6 mb-6">
        <div className="flex items-center gap-4 mb-6">
          <div className="w-16 h-16 bg-foreground text-white rounded-full flex items-center justify-center text-xl font-bold">
            {initials}
          </div>
          <div>
            <p className="text-lg font-semibold text-foreground">{profile.name || 'Sin nombre'}</p>
            <p className="text-sm text-muted-foreground">{profile.email}</p>
            <p className="text-xs text-muted-foreground mt-1">Miembro desde {memberSince}</p>
          </div>
        </div>

        {editing ? (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">Nombre</label>
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Tu nombre" />
            </div>
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">Teléfono</label>
              <Input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+56 9 1234 5678" />
            </div>
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">Email</label>
              <Input value={profile.email} disabled className="bg-muted/60" />
              <p className="text-xs text-muted-foreground mt-1">El email no se puede cambiar</p>
            </div>
            <div className="flex gap-2 pt-2">
              <Button
                variant="outline"
                onClick={() => {
                  setEditing(false);
                  setName(profile.name || '');
                  setPhone(profile.phone || '');
                }}
              >
                Cancelar
              </Button>
              <Button onClick={handleSave} disabled={saving}>
                {saving ? 'Guardando...' : 'Guardar cambios'}
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="flex justify-between py-2 border-b border-edge">
              <span className="text-sm text-muted-foreground">Nombre</span>
              <span className="text-sm font-medium">{profile.name || 'No especificado'}</span>
            </div>
            <div className="flex justify-between py-2 border-b border-edge">
              <span className="text-sm text-muted-foreground">Email</span>
              <span className="text-sm font-medium">{profile.email}</span>
            </div>
            <div className="flex justify-between py-2 border-b border-edge">
              <span className="text-sm text-muted-foreground">Teléfono</span>
              <span className="text-sm font-medium">{profile.phone || 'No especificado'}</span>
            </div>
            <Button variant="outline" className="mt-4" onClick={() => setEditing(true)}>
              Editar perfil
            </Button>
          </div>
        )}
      </Card>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <Card
          className="p-4 hover:bg-muted/60 cursor-pointer transition-colors"
          onClick={() => router.push('/pedidos')}
        >
          <p className="font-medium text-foreground">Mis pedidos</p>
          <p className="text-sm text-muted-foreground mt-1">Ver historial de compras</p>
        </Card>
        <Card
          className="p-4 hover:bg-muted/60 cursor-pointer transition-colors"
          onClick={() => router.push('/alertas')}
        >
          <p className="font-medium text-foreground">Alertas de precio</p>
          <p className="text-sm text-muted-foreground mt-1">Gestionar notificaciones</p>
        </Card>
        <Card className="p-4 hover:bg-muted/60 cursor-pointer transition-colors">
          <p className="font-medium text-foreground">Recetas</p>
          <p className="text-sm text-muted-foreground mt-1">Subir y ver recetas</p>
        </Card>
      </div>
    </div>
  );
}
