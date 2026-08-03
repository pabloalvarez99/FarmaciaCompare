/**
 * Build /comparar URLs while preserving q, via and minSaving.
 * Default path is catalog (medication); only set via=barcode when explicit.
 */
export function compararHref(opts: {
  q?: string;
  via?: 'barcode' | 'medication';
  minSaving?: number;
}): string {
  const params = new URLSearchParams();
  if (opts.q) params.set('q', opts.q);
  if (opts.via === 'barcode') params.set('via', 'barcode');
  if (opts.minSaving && opts.minSaving > 0) {
    params.set('minSaving', String(opts.minSaving));
  }
  const qs = params.toString();
  return qs ? `/comparar?${qs}` : '/comparar';
}
