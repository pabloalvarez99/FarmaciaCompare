import { MetadataRoute } from 'next';
import { comparisonHref, getComparisons } from '@/lib/api-products';

const BASE_URL = 'https://farmacia-compare-web.vercel.app';

export const revalidate = 3600;

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  // Only real comparison pages get indexed. Catalog groups first (higher
  // coverage); barcode groups still indexed for exact-EAN pages.
  const [medGroups, barcodeGroups] = await Promise.all([
    getComparisons('', 100, 0, 'medication'),
    getComparisons('', 100, 0, 'barcode'),
  ]);

  const seen = new Set<string>();
  const comparisonPages: MetadataRoute.Sitemap = [];
  for (const g of [...medGroups, ...barcodeGroups]) {
    const path = comparisonHref(g);
    if (!path || seen.has(path)) continue;
    seen.add(path);
    comparisonPages.push({
      url: `${BASE_URL}${path}`,
      lastModified: new Date(),
      changeFrequency: 'daily',
      priority: 0.8,
    });
  }

  return [
    {
      url: BASE_URL,
      lastModified: new Date(),
      changeFrequency: 'daily',
      priority: 1,
    },
    {
      url: `${BASE_URL}/comparar`,
      lastModified: new Date(),
      changeFrequency: 'daily',
      priority: 0.95,
    },
    {
      url: `${BASE_URL}/precios`,
      lastModified: new Date(),
      changeFrequency: 'daily',
      priority: 0.9,
    },
    ...comparisonPages,
  ];
}
