import { MetadataRoute } from 'next';

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: '*',
      allow: '/',
      disallow: ['/cuenta', '/pedidos', '/alertas', '/api/'],
    },
    sitemap: 'https://farmacia-compare-web.vercel.app/sitemap.xml',
  };
}
