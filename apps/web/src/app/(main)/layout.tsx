import { Header } from '@/components/layout/Header';
import { Footer } from '@/components/layout/Footer';
import { CompareBar } from '@/components/compare/CompareBar';

export default function MainLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <Header />
      <main className="min-h-[calc(100vh-4rem)] pb-20">{children}</main>
      <Footer />
      <CompareBar />
    </>
  );
}
