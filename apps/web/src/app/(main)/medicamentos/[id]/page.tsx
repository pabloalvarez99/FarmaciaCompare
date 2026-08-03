import { redirect } from 'next/navigation';

interface Props {
  params: { id: string };
}

/**
 * Legacy /medicamentos/:id URLs. Real multi-chain comparison by catalog id
 * lives at /precios/medicamento/:id (matcher-linked offers, no invented prices).
 */
export default function MedicamentoPage({ params }: Props) {
  const id = params.id?.trim();
  if (id) redirect(`/precios/medicamento/${encodeURIComponent(id)}`);
  redirect('/comparar');
}
