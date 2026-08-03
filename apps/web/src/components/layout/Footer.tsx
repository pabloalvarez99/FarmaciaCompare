import Link from 'next/link';

/**
 * The footer is where a price site earns or loses the benefit of the doubt, so
 * it says what we do and what we do not do, in that order.
 *
 * It used to carry links to /terminos, /privacidad and /contacto. None of those
 * routes exist — all three answered 404. A dead legal link on a health site is
 * worse than an absent one, so they are gone until there is a page behind them.
 */
export function Footer() {
  return (
    <footer className="mt-16 border-t border-edge bg-foreground text-white/70">
      <div className="mx-auto max-w-5xl px-4 py-12">
        <div className="grid grid-cols-2 gap-8 md:grid-cols-4">
          <div className="col-span-2 md:col-span-1">
            <h2 className="display font-semibold text-white">FarmaciaCompare</h2>
            <p className="mt-3 text-sm leading-relaxed">
              El mismo producto, en todas las farmacias online de Chile que lo venden,
              con lo que cobra cada una.
            </p>
          </div>

          <div>
            <h3 className="label mb-3 text-white/50">Comparar</h3>
            <ul className="space-y-2 text-sm">
              <li>
                <Link href="/comparar" className="hover:text-white">
                  Mayores diferencias
                </Link>
              </li>
              <li>
                <Link href="/precios" className="hover:text-white">
                  Buscar un producto
                </Link>
              </li>
              <li>
                <Link href="/farmacias" className="hover:text-white">
                  Farmacias de la región
                </Link>
              </li>
            </ul>
          </div>

          <div>
            <h3 className="label mb-3 text-white/50">Buscado a menudo</h3>
            <ul className="space-y-2 text-sm">
              <li>
                <Link href="/comparar?q=paracetamol" className="hover:text-white">
                  Paracetamol
                </Link>
              </li>
              <li>
                <Link href="/comparar?q=losart%C3%A1n" className="hover:text-white">
                  Losartán
                </Link>
              </li>
              <li>
                <Link href="/comparar?q=omeprazol" className="hover:text-white">
                  Omeprazol
                </Link>
              </li>
              <li>
                <Link href="/comparar?via=derivado&q=pa%C3%B1ales" className="hover:text-white">
                  Pañales
                </Link>
              </li>
            </ul>
          </div>

          <div>
            <h3 className="label mb-3 text-white/50">Lo que no hacemos</h3>
            <ul className="space-y-2 text-sm">
              <li>No vendemos: la compra ocurre en la farmacia.</li>
              <li>No damos consejo médico ni sugerimos reemplazos.</li>
              <li>No inventamos precios. Si un dato falta, lo decimos.</li>
            </ul>
          </div>
        </div>

        <div className="mt-10 border-t border-white/15 pt-6 text-sm">
          <p>
            Los precios se recogen de los sitios web de cada farmacia y cambian durante
            el día. Confirma el precio y el stock en la farmacia antes de comprar.
          </p>
          <p className="mt-2 text-xs text-white/50">
            © {new Date().getFullYear()} FarmaciaCompare
          </p>
        </div>
      </div>
    </footer>
  );
}
