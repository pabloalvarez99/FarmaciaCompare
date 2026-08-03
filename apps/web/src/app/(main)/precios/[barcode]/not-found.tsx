import Link from 'next/link';

/**
 * A barcode with no live offers is a normal outcome, not a broken link: the
 * product may have gone out of catalog since the page was indexed. The generic
 * 404 ("no encontramos lo que buscabas") would read as our mistake, so this
 * one explains what happened and puts the search back in reach.
 */
export default function ComparisonNotFound() {
  return (
    <div className="mx-auto max-w-xl px-4 py-16 text-center">
      <h1 className="display text-2xl font-bold text-foreground">
        No hay ofertas para este código
      </h1>
      <p className="mx-auto mt-3 max-w-md text-muted-foreground">
        Ninguna de las farmacias que seguimos publica hoy un precio para este código de
        barras. Puede que el producto haya salido de catálogo o que todavía no lo hayamos
        recolectado.
      </p>
      <div className="mt-8 flex flex-wrap justify-center gap-3">
        <Link
          href="/precios"
          className="btn-solid"
        >
          Buscar por nombre
        </Link>
        <Link
          href="/"
          className="btn-quiet"
        >
          Ir al inicio
        </Link>
      </div>
    </div>
  );
}
