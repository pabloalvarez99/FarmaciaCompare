import Link from 'next/link';

export default function MedicationComparisonNotFound() {
  return (
    <div className="mx-auto max-w-xl px-4 py-16 text-center">
      <h1 className="display text-2xl font-bold text-gray-900">
        No hay ofertas para este producto
      </h1>
      <p className="mx-auto mt-3 max-w-md text-gray-600">
        Ninguna de las farmacias que seguimos tiene hoy un listado vinculado a este
        producto del catálogo, o el enlace no es válido.
      </p>
      <div className="mt-8 flex flex-wrap justify-center gap-3">
        <Link
          href="/comparar"
          className="rounded-lg bg-blue-600 px-5 py-2.5 font-medium text-white transition-colors hover:bg-blue-700"
        >
          Ver comparaciones
        </Link>
        <Link
          href="/precios"
          className="rounded-lg border border-gray-300 bg-white px-5 py-2.5 font-medium text-gray-700 transition-colors hover:bg-gray-50"
        >
          Buscar por nombre
        </Link>
      </div>
    </div>
  );
}
