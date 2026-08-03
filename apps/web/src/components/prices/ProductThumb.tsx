'use client';

import { useState } from 'react';

/**
 * Thumbnail for scraped pharmacy product images.
 *
 * Plain <img>, not next/image: these are ten unrelated pharmacy CDNs and
 * declaring `remotePatterns` for each (plus paying for the optimiser on images
 * that are already 40px on screen) buys nothing.
 *
 * `width`/`height` are set on the element *and* in `style` so the box is
 * reserved before the bytes arrive — no layout shift as rows fill in. When the
 * URL is null or the request fails we still render a same-size neutral tile, so
 * a product without a photo keeps its row aligned with the ones that have one.
 *
 * `referrerPolicy="no-referrer"` because several of these CDNs 403 a hotlink
 * that carries an unfamiliar Referer header.
 */
export function ProductThumb({
  src,
  alt,
  size = 40,
  className = '',
}: {
  src: string | null | undefined;
  alt: string;
  size?: number;
  className?: string;
}) {
  const [failed, setFailed] = useState(false);

  const box = `shrink-0 overflow-hidden rounded-lg border border-gray-200 ${className}`;

  if (!src || failed) {
    return (
      <div
        aria-hidden
        className={`${box} flex items-center justify-center bg-gray-50`}
        style={{ width: size, height: size }}
      >
        {/* A capsule outline, not an emoji: it has to read at 36px and stay
            quiet next to the price it sits beside. */}
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={1.5}
          className="text-gray-300"
          style={{ width: Math.round(size * 0.42), height: Math.round(size * 0.42) }}
        >
          <rect x="2.5" y="8" width="19" height="8" rx="4" />
          <line x1="12" y1="8" x2="12" y2="16" />
        </svg>
      </div>
    );
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt={alt}
      width={size}
      height={size}
      loading="lazy"
      decoding="async"
      referrerPolicy="no-referrer"
      onError={() => setFailed(true)}
      className={`${box} bg-white object-contain`}
      style={{ width: size, height: size }}
    />
  );
}
