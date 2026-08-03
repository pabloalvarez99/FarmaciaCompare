import Link from 'next/link';
import { Header } from '@/components/layout/Header';
import { Footer } from '@/components/layout/Footer';
import { REGION_LABEL } from '@/lib/regions';

export default function MainLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <Header />
      {/* Subtle regional framing — product is Coquimbo-first; prices online are national. */}
      <div className="bg-blue-50 border-b border-blue-100">
        <div className="max-w-7xl mx-auto px-4 py-1.5 flex flex-wrap items-center justify-between gap-2 text-xs text-blue-800">
          <span>
            Foco {REGION_LABEL} · La Serena · Coquimbo · Ovalle
          </span>
          <Link href="/farmacias" className="font-medium text-blue-700 hover:underline shrink-0">
            Farmacias en la región
          </Link>
        </div>
      </div>
      {/* pb-20 used to reserve room for the CompareBar tray; without it that
          was just dead space above the footer. */}
      <main className="min-h-[calc(100vh-4rem)]">{children}</main>
      <Footer />
      {/* CompareBar is out until the compare tray is rebuilt on scraped data:
          it resolved its selections through the demo dataset, so a stale
          localStorage entry could still surface an invented product. */}
    </>
  );
}
