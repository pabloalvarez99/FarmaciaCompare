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

/*
 * The scope in this copy is the whole catalogue, not just medicines. It used to
 * say "precios de medicamentos", which is what the site was before suplementos,
 * dermocosmética, cosmética, higiene, bebé and dispositivos were classified —
 * two thirds of the products are outside that word today.
 */
const TAGLINE = 'El mismo producto, en todas las farmacias online de Chile';

export const metadata: Metadata = {
  metadataBase: new URL(BASE_URL),
  title: {
    default: `FarmaciaCompare — ${TAGLINE}`,
    template: '%s | FarmaciaCompare',
  },
  description:
    'Compara el precio del mismo remedio, suplemento o producto de higiene en Cruz Verde, Salcobrand, Ahumada, Dr. Simi, Farmex, Preunic y más. Precios recogidos de sus tiendas online.',
  keywords:
    'medicamentos, farmacias, Chile, precios, comparar, paracetamol, ibuprofeno, La Serena, Coquimbo',
  openGraph: {
    type: 'website',
    locale: 'es_CL',
    url: BASE_URL,
    siteName: 'FarmaciaCompare',
    title: `FarmaciaCompare — ${TAGLINE}`,
    description:
      'El mismo producto no cuesta lo mismo en cada farmacia. Acá ves cuánto cambia, con la farmacia al lado de cada precio.',
  },
  twitter: {
    card: 'summary',
    title: 'FarmaciaCompare',
    description: TAGLINE,
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
