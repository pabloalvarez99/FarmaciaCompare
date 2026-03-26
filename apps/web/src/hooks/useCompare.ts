'use client';
import { useState, useEffect, useCallback } from 'react';

const STORAGE_KEY = 'fc-compare';
const MAX_COMPARE = 3;

function readStorage(): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.slice(0, MAX_COMPARE) : [];
  } catch {
    return [];
  }
}

function writeStorage(ids: string[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(ids));
    window.dispatchEvent(new Event('fc-compare-change'));
  } catch {}
}

export function useCompare() {
  const [ids, setIds] = useState<string[]>([]);

  useEffect(() => {
    setIds(readStorage());
    const handler = () => setIds(readStorage());
    window.addEventListener('fc-compare-change', handler);
    return () => window.removeEventListener('fc-compare-change', handler);
  }, []);

  const toggle = useCallback((id: string) => {
    const current = readStorage();
    let next: string[];
    if (current.includes(id)) {
      next = current.filter((x) => x !== id);
    } else if (current.length < MAX_COMPARE) {
      next = [...current, id];
    } else {
      // Already at max — replace oldest
      next = [...current.slice(1), id];
    }
    writeStorage(next);
    setIds(next);
  }, []);

  const remove = useCallback((id: string) => {
    const next = readStorage().filter((x) => x !== id);
    writeStorage(next);
    setIds(next);
  }, []);

  const clear = useCallback(() => {
    writeStorage([]);
    setIds([]);
  }, []);

  const isSelected = (id: string) => ids.includes(id);
  const isFull = ids.length >= MAX_COMPARE;

  return { ids, toggle, remove, clear, isSelected, isFull };
}
