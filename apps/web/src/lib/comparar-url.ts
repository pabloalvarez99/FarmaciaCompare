/**
 * Build /comparar URLs while preserving q, via and minSaving.
 *
 * Default path is catalog (medication); `barcode` and `derivado` are only set
 * when explicit, so the default URL stays clean and every existing link keeps
 * meaning what it meant.
 */
export function compararHref(opts: {
  q?: string;
  via?: 'barcode' | 'medication' | 'derivado';
  minSaving?: number;
}): string {
  const params = new URLSearchParams();
  if (opts.q) params.set('q', opts.q);
  if (opts.via === 'barcode') params.set('via', 'barcode');
  if (opts.via === 'derivado') params.set('via', 'derivado');
  if (opts.minSaving && opts.minSaving > 0) {
    params.set('minSaving', String(opts.minSaving));
  }
  const qs = params.toString();
  return qs ? `/comparar?${qs}` : '/comparar';
}
