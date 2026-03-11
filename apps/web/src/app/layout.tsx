import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'FarmaciaCompare — Compara precios de medicamentos en Chile',
  description:
    'Compara precios de medicamentos en todas las farmacias de Chile. Cruz Verde, Salcobrand, Ahumada, Dr. Simi y más.',
  keywords: 'medicamentos, farmacias, Chile, precios, comparar, paracetamol, ibuprofeno',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body className={inter.className}>{children}</body>
    </html>
  );
}
