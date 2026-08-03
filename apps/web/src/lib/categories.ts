/**
 * Presentation for the seven canonical categories.
 *
 * The list, the ids and the counts all come from `/products/categories` — this
 * file never invents a category and never carries a number. It exists for two
 * jobs the API cannot do:
 *
 * 1. Accents. The API returns `Dermocosmetica`, `Cosmetica y maquillaje`,
 *    `Cuidado del bebe`. Correct Spanish is a rendering concern, and a comparator
 *    aimed at Chilean readers cannot spell its own sections wrong.
 * 2. A plain-language line saying what is actually inside each one, so the chips
 *    are a way in rather than a taxonomy to decode.
 *
 * Anything the API adds later still renders — it falls back to the API's own
 * name and shows no blurb. An unknown category is better than a missing one.
 */
export interface CategoryDisplay {
  label: string;
  blurb: string;
}

const DISPLAY: Record<string, CategoryDisplay> = {
  medicamento: {
    label: 'Medicamentos',
    blurb: 'Con y sin receta, de marca y bioequivalentes',
  },
  suplemento: {
    label: 'Suplementos y vitaminas',
    blurb: 'Vitaminas, minerales, proteínas',
  },
  dermocosmetica: {
    label: 'Dermocosmética',
    blurb: 'Protector solar, serums, tratamiento facial',
  },
  cosmetica: {
    label: 'Cosmética y maquillaje',
    blurb: 'Maquillaje y cuidado capilar',
  },
  higiene: {
    label: 'Higiene y cuidado personal',
    blurb: 'Desodorante, cuidado bucal, cuidado íntimo',
  },
  bebe: {
    label: 'Cuidado del bebé',
    blurb: 'Fórmula, pañales, higiene infantil',
  },
  dispositivo: {
    label: 'Dispositivos y accesorios',
    blurb: 'Presión, glucosa, mascarillas, órtesis',
  },
};

export function categoryLabel(id: string, apiName: string): string {
  return DISPLAY[id]?.label ?? apiName;
}

export function categoryBlurb(id: string): string | null {
  return DISPLAY[id]?.blurb ?? null;
}
