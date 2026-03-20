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
          <div>
            <h4 className="text-white text-sm font-medium mb-3">Farmacias</h4>
            <ul className="space-y-2 text-sm">
              <li><Link href="/buscar?chain=cruz-verde" className="hover:text-white transition-colors">Cruz Verde</Link></li>
              <li><Link href="/buscar?chain=salcobrand" className="hover:text-white transition-colors">Salcobrand</Link></li>
              <li><Link href="/buscar?chain=ahumada" className="hover:text-white transition-colors">Ahumada</Link></li>
              <li><Link href="/buscar?chain=dr-simi" className="hover:text-white transition-colors">Dr. Simi</Link></li>
            </ul>
          </div>
          <div>
            <h4 className="text-white text-sm font-medium mb-3">Popular</h4>
            <ul className="space-y-2 text-sm">
              <li><Link href="/buscar?q=paracetamol" className="hover:text-white transition-colors">Paracetamol</Link></li>
              <li><Link href="/buscar?q=ibuprofeno" className="hover:text-white transition-colors">Ibuprofeno</Link></li>
              <li><Link href="/buscar?q=losartan" className="hover:text-white transition-colors">Losartán</Link></li>
              <li><Link href="/buscar?q=omeprazol" className="hover:text-white transition-colors">Omeprazol</Link></li>
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
