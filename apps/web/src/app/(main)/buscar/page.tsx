import { redirect } from 'next/navigation';

/**
 * /buscar was built on the curated `medications` catalog, which has no rows
 * yet, so it could only ever render the illustrative demo dataset. Invented
 * prices on a price comparator are worse than none, so this route forwards to
 * /precios, which serves scraped data.
 *
 * Bring the page back once the catalog is imported and products are linked to
 * medications: then it can group results by drug instead of listing one row per
 * pharmacy product.
 */
interface Props {
  searchParams: { q?: string };
}

export default function BuscarPage({ searchParams }: Props) {
  const query = searchParams.q;
  redirect(query ? `/precios?q=${encodeURIComponent(query)}` : '/precios');
}
