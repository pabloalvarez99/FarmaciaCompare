import Link from 'next/link';

export function Footer() {
  return (
    <footer className="bg-gray-900 text-gray-400">
      <div className="max-w-7xl mx-auto px-4 py-12">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
          <div>
            <h3 className="text-white font-semibold mb-3">FarmaciaCompare</h3>
            <p className="text-sm leading-relaxed">
              Compara precios de medicamentos en todas las farmacias de Chile.
            </p>
          </div>
          {/* These used to point at /buscar?chain=…, which redirects to /precios
              and drops the filter — a link that silently does something other
              than what it says. /precios has no chain filter yet, so the column
              now offers what it can actually deliver. */}
          <div>
            <h4 className="text-white text-sm font-medium mb-3">Comparar</h4>
            <ul className="space-y-2 text-sm">
              <li><Link href="/comparar" className="hover:text-white transition-colors">Comparar precios</Link></li>
              <li><Link href="/precios" className="hover:text-white transition-colors">Buscar listados</Link></li>
              <li><Link href="/farmacias" className="hover:text-white transition-colors">Farmacias de la región</Link></li>
              <li><Link href="/alertas" className="hover:text-white transition-colors">Alertas de precio</Link></li>
            </ul>
          </div>
          <div>
            <h4 className="text-white text-sm font-medium mb-3">Popular</h4>
            <ul className="space-y-2 text-sm">
              <li><Link href="/comparar?q=paracetamol" className="hover:text-white transition-colors">Paracetamol</Link></li>
              <li><Link href="/comparar?q=ibuprofeno" className="hover:text-white transition-colors">Ibuprofeno</Link></li>
              <li><Link href="/comparar?q=losart%C3%A1n" className="hover:text-white transition-colors">Losartán</Link></li>
              <li><Link href="/comparar?q=omeprazol" className="hover:text-white transition-colors">Omeprazol</Link></li>
            </ul>
          </div>
          <div>
            <h4 className="text-white text-sm font-medium mb-3">Legal</h4>
            <ul className="space-y-2 text-sm">
              <li><Link href="/terminos" className="hover:text-white transition-colors">Términos de uso</Link></li>
              <li><Link href="/privacidad" className="hover:text-white transition-colors">Política de privacidad</Link></li>
              <li><Link href="/contacto" className="hover:text-white transition-colors">Contacto</Link></li>
            </ul>
          </div>
        </div>
        <div className="border-t border-gray-800 mt-8 pt-8 text-center text-sm">
          <p>&copy; {new Date().getFullYear()} FarmaciaCompare. Todos los derechos reservados.</p>
          <p className="mt-1 text-xs text-gray-500">
            Los precios mostrados son referenciales y pueden variar. Consulte directamente con la farmacia.
          </p>
        </div>
      </div>
    </footer>
  );
}
