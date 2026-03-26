'use client';

import { useMemo } from 'react';
import { formatCLP } from '@/lib/utils';

interface HistoryPoint {
  recordedAt: string;
  price: number;
  pharmacyName: string;
}

interface Props {
  data: HistoryPoint[];
}

const COLORS = [
  '#2563eb', // blue
  '#16a34a', // green
  '#ea580c', // orange
  '#9333ea', // purple
  '#dc2626', // red
  '#0891b2', // cyan
];

const W = 600;
const H = 200;
const PAD = { top: 12, right: 16, bottom: 32, left: 56 };

export function PriceHistoryChart({ data }: Props) {
  const { lines, xLabels, yMin, yMax } = useMemo(() => {
    if (!data.length) return { lines: [], xLabels: [], yMin: 0, yMax: 0 };

    // Group by pharmacy
    const byPharmacy = new Map<string, HistoryPoint[]>();
    for (const pt of data) {
      const list = byPharmacy.get(pt.pharmacyName) ?? [];
      list.push(pt);
      byPharmacy.set(pt.pharmacyName, list);
    }

    const allPrices = data.map((d) => d.price);
    const yMin = Math.min(...allPrices);
    const yMax = Math.max(...allPrices);
    const priceRange = yMax - yMin || 1;

    // X axis: unique dates sorted
    const allDates = [...new Set(data.map((d) => d.recordedAt.slice(0, 10)))].sort();
    const xStep = (W - PAD.left - PAD.right) / Math.max(allDates.length - 1, 1);

    const toX = (dateStr: string) => {
      const idx = allDates.indexOf(dateStr);
      return PAD.left + idx * xStep;
    };
    const toY = (price: number) =>
      PAD.top + ((yMax - price) / priceRange) * (H - PAD.top - PAD.bottom);

    const lines = Array.from(byPharmacy.entries()).map(([name, points], i) => {
      const sorted = [...points].sort((a, b) => a.recordedAt.localeCompare(b.recordedAt));
      const d = sorted
        .map((pt, j) => {
          const x = toX(pt.recordedAt.slice(0, 10));
          const y = toY(pt.price);
          return `${j === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`;
        })
        .join(' ');
      return { name, d, color: COLORS[i % COLORS.length] };
    });

    // X labels: show at most 7
    const step = Math.ceil(allDates.length / 7);
    const xLabels = allDates
      .filter((_, i) => i % step === 0 || i === allDates.length - 1)
      .map((date) => ({
        x: toX(date),
        label: date.slice(5), // MM-DD
      }));

    return { lines, xLabels, yMin, yMax };
  }, [data]);

  if (!data.length) return null;

  return (
    <div className="mt-8">
      <h2 className="text-lg font-semibold mb-3">Historial de precios (30 días)</h2>
      <div className="border rounded-lg p-4 bg-white overflow-x-auto">
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ minWidth: 300 }}>
          {/* Y grid lines */}
          {[0, 0.25, 0.5, 0.75, 1].map((t) => {
            const price = yMin + t * (yMax - yMin);
            const y = PAD.top + (1 - t) * (H - PAD.top - PAD.bottom);
            return (
              <g key={t}>
                <line
                  x1={PAD.left}
                  x2={W - PAD.right}
                  y1={y}
                  y2={y}
                  stroke="#e5e7eb"
                  strokeWidth={1}
                />
                <text x={PAD.left - 6} y={y + 4} textAnchor="end" fontSize={10} fill="#6b7280">
                  {formatCLP(Math.round(price))}
                </text>
              </g>
            );
          })}

          {/* X labels */}
          {xLabels.map(({ x, label }) => (
            <text
              key={label}
              x={x}
              y={H - PAD.bottom + 16}
              textAnchor="middle"
              fontSize={10}
              fill="#6b7280"
            >
              {label}
            </text>
          ))}

          {/* Lines */}
          {lines.map(({ name, d, color }) => (
            <path key={name} d={d} fill="none" stroke={color} strokeWidth={2} strokeLinejoin="round" />
          ))}
        </svg>

        {/* Legend */}
        {lines.length > 1 && (
          <div className="flex flex-wrap gap-4 mt-3 justify-center">
            {lines.map(({ name, color }) => (
              <div key={name} className="flex items-center gap-1.5 text-xs text-gray-600">
                <span className="inline-block w-4 h-0.5 rounded" style={{ background: color }} />
                {name}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
