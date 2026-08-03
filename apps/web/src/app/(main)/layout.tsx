import Link from 'next/link';
import { Header } from '@/components/layout/Header';
import { Footer } from '@/components/layout/Footer';
import { REGION_LABEL } from '@/lib/regions';

export default function MainLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <Header />
      {/* Subtle regional framing — product is Coquimbo-first; prices online are national. */}
      <div className="border-b border-edge bg-muted/60">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-2 px-4 py-1.5 text-xs text-muted-foreground">
          <span>Precios de tiendas online que despachan a todo Chile</span>
          <Link
            href="/farmacias"
            className="shrink-0 font-medium text-foreground underline decoration-foreground/30 underline-offset-2 hover:decoration-foreground"
          >
            Farmacias de la {REGION_LABEL}
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
