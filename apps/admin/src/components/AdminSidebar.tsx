'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import {
  LayoutDashboard,
  BookOpen,
  Bot,
  AlertTriangle,
  Building2,
} from 'lucide-react';

const NAV = [
  { href: '/', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/catalogo', label: 'Catálogo', icon: BookOpen },
  { href: '/scrapers', label: 'Scrapers', icon: Bot },
  { href: '/anomalias', label: 'Anomalías', icon: AlertTriangle },
  { href: '/farmacias', label: 'Farmacias', icon: Building2 },
];

export function AdminSidebar() {
  const pathname = usePathname();
  return (
    <aside className="w-60 border-r bg-gray-900 text-white h-screen fixed left-0 top-0 flex flex-col">
      <div className="px-6 py-5 border-b border-gray-700">
        <h1 className="font-bold text-lg text-red-400">FC Admin</h1>
        <p className="text-xs text-gray-400">Panel interno</p>
      </div>
      <nav className="flex-1 p-3 space-y-0.5">
        {NAV.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className={cn(
              'flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors',
              pathname === href
                ? 'bg-gray-700 text-white font-medium'
                : 'text-gray-400 hover:bg-gray-800 hover:text-white',
            )}
          >
            <Icon className="h-4 w-4" />
            {label}
          </Link>
        ))}
      </nav>
    </aside>
  );
}
