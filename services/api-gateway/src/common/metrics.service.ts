import { Injectable } from '@nestjs/common';

@Injectable()
export class MetricsService {
  private counters = new Map<string, number>();
  private gauges = new Map<string, number>();
  private histogramBuckets = [5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000];
  private histograms = new Map<string, number[]>();

  incrementCounter(
    name: string,
    labels: Record<string, string> = {},
    value = 1,
  ) {
    const key = this.makeKey(name, labels);
    this.counters.set(key, (this.counters.get(key) || 0) + value);
  }

  setGauge(
    name: string,
    value: number,
    labels: Record<string, string> = {},
  ) {
    const key = this.makeKey(name, labels);
    this.gauges.set(key, value);
  }

  observeHistogram(
    name: string,
    value: number,
    labels: Record<string, string> = {},
  ) {
    const key = this.makeKey(name, labels);
    if (!this.histograms.has(key)) {
      this.histograms.set(key, []);
    }
    this.histograms.get(key)!.push(value);
  }

  getMetrics(): string {
    const lines: string[] = [];

    for (const [key, value] of this.counters) {
      const name = key.split('{')[0];
      lines.push(`# TYPE ${name} counter`);
      lines.push(`${key} ${value}`);
    }

    for (const [key, value] of this.gauges) {
      const name = key.split('{')[0];
      lines.push(`# TYPE ${name} gauge`);
      lines.push(`${key} ${value}`);
    }

    for (const [key, values] of this.histograms) {
      const name = key.split('{')[0];
      lines.push(`# TYPE ${name} histogram`);
      const sum = values.reduce((a, b) => a + b, 0);
      const count = values.length;
      for (const bucket of this.histogramBuckets) {
        const le = values.filter((v) => v <= bucket).length;
        lines.push(`${name}_bucket{le="${bucket}"} ${le}`);
      }
      lines.push(`${name}_bucket{le="+Inf"} ${count}`);
      lines.push(`${name}_sum ${sum}`);
      lines.push(`${name}_count ${count}`);
    }

    return lines.join('\n') + '\n';
  }

  private makeKey(name: string, labels: Record<string, string>): string {
    const labelStr = Object.entries(labels)
      .map(([k, v]) => `${k}="${v}"`)
      .join(',');
    return labelStr ? `${name}{${labelStr}}` : name;
  }
}
