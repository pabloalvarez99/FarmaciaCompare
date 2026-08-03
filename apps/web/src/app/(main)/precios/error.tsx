'use client';

import Link from 'next/link';
import { useEffect } from 'react';

/**
 * Every fetch helper in `lib/api-products` already degrades to empty results,
 * so this boundary is for the failures that are *not* the API being down —
 * a bad render, a malformed payload. It says so plainly instead of implying
 * the pharmacies have no prices today.
 */
export default function PreciosError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error('[precios]', error);
  }, [error]);

  return (
    <div className="mx-auto max-w-2xl px-4 py-16 text-center">
      <h1 className="display text-2xl font-bold text-foreground">
        No pudimos mostrar los precios
      </h1>
      <p className="mx-auto mt-3 max-w-md text-muted-foreground">
        Algo falló al armar esta página. No es que las farmacias no tengan precio hoy:
        es un error nuestro.
      </p>
      {error.digest && (
        <p className="mt-2 font-mono text-xs text-muted-foreground">ref {error.digest}</p>
      )}
      <div className="mt-8 flex flex-wrap justify-center gap-3">
        <button type="button" onClick={reset} className="btn-solid">
          Reintentar
        </button>
        <Link href="/precios" className="btn-quiet">
          Volver a buscar
        </Link>
      </div>
    </div>
  );
}
