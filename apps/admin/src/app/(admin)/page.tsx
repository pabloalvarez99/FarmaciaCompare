import { Card } from '@/components/ui/card';

export default function AdminHome() {
  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Admin Dashboard</h1>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="p-6 bg-gray-900 border-gray-800">
          <p className="text-sm text-gray-400">Total medicamentos</p>
          <p className="text-3xl font-bold mt-1">&mdash;</p>
        </Card>
        <Card className="p-6 bg-gray-900 border-gray-800">
          <p className="text-sm text-gray-400">Productos sin vincular</p>
          <p className="text-3xl font-bold mt-1">&mdash;</p>
        </Card>
        <Card className="p-6 bg-gray-900 border-gray-800">
          <p className="text-sm text-gray-400">Scrapers activos</p>
          <p className="text-3xl font-bold mt-1">&mdash;</p>
        </Card>
        <Card className="p-6 bg-gray-900 border-gray-800">
          <p className="text-sm text-gray-400">Anomalías detectadas</p>
          <p className="text-3xl font-bold mt-1">&mdash;</p>
        </Card>
      </div>
    </div>
  );
}
