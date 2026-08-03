import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { QueryProvider } from '@/components/providers/QueryProvider';

/*
 * globals.css asks for `--font-body` and `--font-display` (the `.figure`,
 * `.display` and `.label` voices). Without the variable they silently fell
 * back to the system UI font, so every price on the site was set in a
 * different typeface from the copy around it. One family fills both roles:
 * Inter carries real tabular figures, which is the whole point of `.figure`.
 */
const inter = Inter({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-body',
});

const BASE_URL = 'https://farmacia-compare-web.vercel.app';

export const metadata: Metadata = {
  metadataBase: new URL(BASE_URL),
  title: {
    default: 'FarmaciaCompare — Compara precios de medicamentos en Chile',
    template: '%s | FarmaciaCompare',
  },
  description:
    'Compara precios de medicamentos en Cruz Verde, Salcobrand, Ahumada, Dr. Simi y farmacias independientes. Región de Coquimbo y Santiago.',
  keywords: 'medicamentos, farmacias, Chile, precios, comparar, paracetamol, ibuprofeno, La Serena, Coquimbo',
  openGraph: {
    type: 'website',
    locale: 'es_CL',
    url: BASE_URL,
    siteName: 'FarmaciaCompare',
    title: 'FarmaciaCompare — Compara precios de medicamentos en Chile',
    description:
      'Compara precios de medicamentos en las principales farmacias de Chile. Ahorra en Cruz Verde, Salcobrand, Ahumada y Dr. Simi.',
  },
  twitter: {
    card: 'summary',
    title: 'FarmaciaCompare',
    description: 'Compara precios de medicamentos en farmacias de Chile.',
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es" className={inter.variable}>
      <body className={inter.className}>
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  );
}
