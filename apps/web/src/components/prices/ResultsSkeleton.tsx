/**
 * Streaming placeholder for the /precios result list.
 *
 * It mirrors the real card geometry — 72px thumb, two lines of copy, a price
 * block on the right — so nothing jumps when the data lands. Eight rows is
 * about a phone-and-a-half of scroll: enough to read as "a list is coming"
 * without pretending to know how many results there are.
 *
 * This is a component rather than a `loading.tsx` on purpose. A `loading.tsx`
 * in the `precios` segment also wraps `precios/[barcode]` in Suspense, which
 * starts the response before that page can call `notFound()` — every missing
 * barcode would then answer 200 with 404 content, and those URLs are in the
 * sitemap. Scoping the boundary to this page keeps the real status code.
 */
function RowSkeleton() {
  return (
    <li className="flex gap-3 p-3 sm:gap-4 sm:p-4">
      <div className="h-[72px] w-[72px] shrink-0 rounded-lg bg-edge" />
      <div className="flex min-w-0 flex-1 flex-col gap-2 sm:flex-row sm:items-start sm:justify-between sm:gap-6">
        <div className="min-w-0 flex-1 space-y-2">
          <div className="h-4 w-3/4 max-w-xs rounded bg-edge" />
          <div className="h-3 w-24 rounded bg-muted" />
          <div className="flex gap-1.5 pt-1">
            <div className="h-5 w-20 rounded bg-muted" />
            <div className="h-5 w-16 rounded bg-muted" />
          </div>
        </div>
        <div className="flex shrink-0 flex-col gap-1.5 sm:items-end">
          <div className="h-6 w-20 rounded bg-edge" />
          <div className="h-3 w-14 rounded bg-muted" />
        </div>
      </div>
    </li>
  );
}

export function ResultsSkeleton() {
  return (
    <div className="animate-pulse" aria-busy="true">
      <span className="sr-only">Cargando precios…</span>

      <div className="mb-6 flex flex-wrap gap-2">
        {[72, 88, 64, 96, 80].map((w, i) => (
          <div key={i} className="h-8 rounded-full bg-muted" style={{ width: w }} />
        ))}
      </div>

      <div className="mb-2 h-4 w-32 rounded bg-muted" />

      <ul className="divide-y divide-edge overflow-hidden rounded-xl border border-edge bg-card">
        {Array.from({ length: 8 }, (_, i) => (
          <RowSkeleton key={i} />
        ))}
      </ul>
    </div>
  );
}
