import type { StructuredData, SparkApp, YunikornQueue } from '../types';
import { Table, Database, Cpu } from 'lucide-react';

interface TaskTableProps {
  data: StructuredData;
}

export default function TaskTable({ data }: TaskTableProps) {
  if (!data || !data.data) {
    return null;
  }
  
  // Handle different data types
  if (data.type === 'spark_apps') {
    return <SparkAppsTable apps={data.data as SparkApp[]} />;
  }
  
  if (data.type === 'yunikorn_queues') {
    return <YunikornQueuesTable queues={data.data as YunikornQueue[]} />;
  }
  
  if (data.type === 'k8s_resources' || data.type === 'table') {
    return <GenericTable data={data.data as Record<string, unknown>[]} columns={data.columns} />;
  }
  
  // Fallback to generic table
  return <GenericTable data={data.data as Record<string, unknown>[]} columns={data.columns} />;
}

function SparkAppsTable({ apps: apps }: { apps: SparkApp[] }) {
  if (!apps || apps.length === 0) {
    return (
      <div className="text-gray-400 text-sm p-4 text-center">
        <Database className="w-8 h-8 mx-auto mb-2 opacity-50" />
        暂无 Spark 应用
      </div>
    );
  }
  
  return (
    <div className="bg-gray-800 rounded-lg overflow-hidden">
      <div className="px-4 py-2 bg-gray-700 text-gray-300 flex items-center gap-2">
        <Database className="w-4 h-4" />
        <span className="font-medium">Spark Applications ({apps.length})</span>
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-gray-700 text-gray-400">
            <th className="px-4 py-2 text-left">App ID</th>
            <th className="px-4 py-2 text-left">Name</th>
            <th className="px-4 py-2 text-left">State</th>
            <th className="px-4 py-2 text-left">Duration</th>
          </tr>
        </thead>
        <tbody>
          {apps.map((app, idx) => (
            <tr key={app.app_id || idx} className="border-t border-gray-700 hover:bg-gray-750">
              <td className="px-4 py-2 text-gray-300 truncate max-w-[200px]">{app.app_id}</td>
              <td className="px-4 py-2 text-gray-300">{app.app_name}</td>
              <td className="px-4 py-2">
                <StateBadge state={app.state} />
              </td>
              <td className="px-4 py-2 text-gray-300">{formatDuration(app.duration)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function YunikornQueuesTable({ queues }: { queues: YunikornQueue[] }) {
  if (!queues || queues.length === 0) {
    return (
      <div className="text-gray-400 text-sm p-4 text-center">
        <Cpu className="w-8 h-8 mx-auto mb-2 opacity-50" />
        暂无队列信息
      </div>
    );
  }
  
  return (
    <div className="bg-gray-800 rounded-lg overflow-hidden">
      <div className="px-4 py-2 bg-gray-700 text-gray-300 flex items-center gap-2">
        <Cpu className="w-4 h-4" />
        <span className="font-medium">YuniKorn Queues ({queues.length})</span>
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-gray-700 text-gray-400">
            <th className="px-4 py-2 text-left">Queue Name</th>
            <th className="px-4 py-2 text-left">Status</th>
            <th className="px-4 py-2 text-left">Capacity</th>
            <th className="px-4 py-2 text-left">Running Apps</th>
          </tr>
        </thead>
        <tbody>
          {queues.map((queue, idx) => (
            <tr key={queue.queue_name || idx} className="border-t border-gray-700 hover:bg-gray-750">
              <td className="px-4 py-2 text-gray-300">{queue.queue_name}</td>
              <td className="px-4 py-2">
                <StateBadge state={queue.status} />
              </td>
              <td className="px-4 py-2 text-gray-300">
                {queue.used_capacity !== undefined ? `${queue.used_capacity.toFixed(1)}%` : '-'}
                {queue.max_capacity !== undefined && ` / ${queue.max_capacity.toFixed(1)}%`}
              </td>
              <td className="px-4 py-2 text-gray-300">{queue.running_apps ?? '-'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function GenericTable({ data, columns }: { data: Record<string, unknown>[]; columns?: string[] }) {
  if (!data || data.length === 0) {
    return (
      <div className="text-gray-400 text-sm p-4 text-center">
        <Table className="w-8 h-8 mx-auto mb-2 opacity-50" />
        暂无数据
      </div>
    );
  }
  
  const actualColumns = columns || Object.keys(data[0]);
  
  return (
    <div className="bg-gray-800 rounded-lg overflow-hidden">
      <div className="px-4 py-2 bg-gray-700 text-gray-300 flex items-center gap-2">
        <Table className="w-4 h-4" />
        <span className="font-medium">Data ({data.length} rows)</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-700 text-gray-400">
              {actualColumns.map((col) => (
                <th key={col} className="px-4 py-2 text-left whitespace-nowrap">{col}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row, idx) => (
              <tr key={idx} className="border-t border-gray-700 hover:bg-gray-750">
                {actualColumns.map((col) => (
                  <td key={col} className="px-4 py-2 text-gray-300 truncate max-w-[200px]">
                    {formatValue(row[col])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function StateBadge({ state }: { state: string }) {
  const getStateColor = (state: string) => {
    const stateColors: Record<string, string> = {
      running: 'bg-green-500',
      completed: 'bg-blue-500',
      success: 'bg-green-500',
      active: 'bg-green-500',
      failed: 'bg-red-500',
      error: 'bg-red-500',
      pending: 'bg-yellow-500',
      waiting: 'bg-yellow-500',
      killed: 'bg-gray-500',
      stopped: 'bg-gray-500',
    };
    return stateColors[state.toLowerCase()] || 'bg-gray-400';
  };
  
  return (
    <span className={`${getStateColor(state)} text-white text-xs px-2 py-1 rounded-full uppercase`}>
      {state}
    </span>
  );
}

function formatDuration(ms: number | undefined): string {
  if (!ms) return '-';
  
  const seconds = Math.floor(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  
  if (hours > 0) {
    return `${hours}h ${minutes % 60}m`;
  }
  if (minutes > 0) {
    return `${minutes}m ${seconds % 60}s`;
  }
  return `${seconds}s`;
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return '-';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}