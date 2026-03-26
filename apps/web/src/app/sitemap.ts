import { MetadataRoute } from 'next';
import { MEDICATIONS } from '@/lib/demo-data';

const BASE_URL = 'https://farmacia-compare-web.vercel.app';

export default function sitemap(): MetadataRoute.Sitemap {
  const medicationPages = MEDICATIONS.map((m) => ({
    url: `${BASE_URL}/medicamentos/${m.id}`,
    lastModified: new Date(),
    changeFrequency: 'daily' as const,
    priority: 0.8,
  }));

  return [
    {
      url: BASE_URL,
      lastModified: new Date(),
      changeFrequency: 'daily',
      priority: 1,
    },
    {
      url: `${BASE_URL}/buscar`,
      lastModified: new Date(),
      changeFrequency: 'daily',
      priority: 0.9,
    },
    ...medicationPages,
  ];
}
