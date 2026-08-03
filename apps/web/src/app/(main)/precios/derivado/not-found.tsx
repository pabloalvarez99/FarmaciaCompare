import Link from 'next/link';

export default function DerivedComparisonNotFound() {
  return (
    <div className="mx-auto max-w-xl px-4 py-16 text-center">
      <h1 className="display text-2xl font-bold text-foreground">
        No hay ofertas para este producto
      </h1>
      <p className="mx-auto mt-3 max-w-md text-muted-foreground">
        Ninguna de las farmacias que seguimos publica hoy un producto con esta marca,
        tamaño y descripción, o el enlace no es válido.
      </p>
      <div className="mt-8 flex flex-wrap justify-center gap-3">
        <Link
          href="/comparar?via=derivado"
          className="btn-solid"
        >
          Ver comparaciones
        </Link>
        <Link
          href="/precios"
          className="btn-quiet"
        >
          Buscar por nombre
        </Link>
      </div>
    </div>
  );
}
