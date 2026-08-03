import Link from 'next/link';
import { SearchBar } from '@/components/search/SearchBar';

export default function NotFound() {
  return (
    <div className="mx-auto flex min-h-[60vh] max-w-xl flex-col items-center justify-center px-4 py-16 text-center">
      <h1 className="display text-3xl font-bold text-foreground">
        Esta página no existe
      </h1>
      <p className="mt-3 max-w-sm text-muted-foreground">
        El enlace puede estar mal escrito, o el producto puede haber salido de catálogo.
        Búscalo por su nombre.
      </p>
      <div className="mt-8 w-full max-w-md">
        <SearchBar />
      </div>
      <div className="mt-6 flex flex-wrap justify-center gap-3">
        <Link href="/comparar" className="btn-solid">
          Ver diferencias de precio
        </Link>
        <Link href="/" className="btn-quiet">
          Ir al inicio
        </Link>
      </div>
    </div>
  );
}
