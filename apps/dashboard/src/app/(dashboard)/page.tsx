import { Card } from '@/components/ui/card';

export default function DashboardHome() {
  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Resumen</h1>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="p-6">
          <p className="text-sm text-muted-foreground">Productos activos</p>
          <p className="text-3xl font-bold mt-1">&mdash;</p>
        </Card>
        <Card className="p-6">
          <p className="text-sm text-muted-foreground">Pedidos hoy</p>
          <p className="text-3xl font-bold mt-1">&mdash;</p>
        </Card>
        <Card className="p-6">
          <p className="text-sm text-muted-foreground">Ventas del mes</p>
          <p className="text-3xl font-bold mt-1">&mdash;</p>
        </Card>
        <Card className="p-6">
          <p className="text-sm text-muted-foreground">Ticket promedio</p>
          <p className="text-3xl font-bold mt-1">&mdash;</p>
        </Card>
      </div>
    </div>
  );
}
