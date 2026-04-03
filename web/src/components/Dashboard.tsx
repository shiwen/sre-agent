import { useState, useEffect } from 'react'
import { Activity, AlertTriangle, CheckCircle, Clock, Server, Layers } from 'lucide-react'
import { sparkService, queueService } from '../services/api'
import type { SparkApplication, QueueInfo } from '../types/chat'

export function Dashboard() {
  const [sparkApps, setSparkApps] = useState<SparkApplication[]>([])
  const [queues, setQueues] = useState<QueueInfo[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [apps, queueList] = await Promise.all([
          sparkService.listApplications(),
          queueService.listQueues(),
        ])
        setSparkApps(apps)
        setQueues(queueList)
      } catch (error) {
        console.error('Failed to fetch dashboard data:', error)
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  const stats = {
    totalApps: sparkApps.length,
    runningApps: sparkApps.filter((a) => a.status === 'RUNNING').length,
    failedApps: sparkApps.filter((a) => a.status === 'FAILED').length,
    totalQueues: queues.length,
    totalCapacity: queues.reduce((sum, q) => sum + q.capacity, 0),
    activeApplications: queues.reduce((sum, q) => sum + q.running_applications, 0),
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Activity className="w-8 h-8 animate-pulse text-blue-500" />
      </div>
    )
  }

  return (
    <div className="p-6">
      <h2 className="text-xl font-bold mb-6">Dashboard</h2>

      <div className="grid grid-cols-3 gap-4 mb-6">
        <StatCard
          icon={<Server className="w-6 h-6 text-blue-500" />}
          title="Spark Applications"
          value={stats.totalApps}
          subtitle={`${stats.runningApps} running`}
        />
        <StatCard
          icon={<AlertTriangle className="w-6 h-6 text-red-500" />}
          title="Failed Applications"
          value={stats.failedApps}
          subtitle="Last 24 hours"
        />
        <StatCard
          icon={<Layers className="w-6 h-6 text-green-500" />}
          title="YuniKorn Queues"
          value={stats.totalQueues}
          subtitle={`Capacity: ${stats.totalCapacity}`}
        />
      </div>

      <div className="grid grid-cols-2 gap-6">
        <div className="bg-gray-800 rounded-lg border border-gray-700">
          <div className="p-4 border-b border-gray-700">
            <h3 className="font-semibold">Spark Applications</h3>
          </div>
          <div className="p-4 max-h-60 overflow-y-auto">
            {sparkApps.length === 0 ? (
              <p className="text-gray-500 text-center">No applications found</p>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-gray-400">
                    <th className="text-left pb-2">Name</th>
                    <th className="text-left pb-2">Status</th>
                    <th className="text-right pb-2">Executors</th>
                  </tr>
                </thead>
                <tbody>
                  {sparkApps.map((app) => (
                    <tr key={app.name} className="border-t border-gray-700">
                      <td className="py-2">{app.name}</td>
                      <td className="py-2">
                        <StatusBadge status={app.status} />
                      </td>
                      <td className="py-2 text-right">{app.executor_count || '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg border border-gray-700">
          <div className="p-4 border-b border-gray-700">
            <h3 className="font-semibold">Queue Status</h3>
          </div>
          <div className="p-4 max-h-60 overflow-y-auto">
            {queues.length === 0 ? (
              <p className="text-gray-500 text-center">No queues found</p>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-gray-400">
                    <th className="text-left pb-2">Name</th>
                    <th className="text-right pb-2">Running</th>
                    <th className="text-right pb-2">Pending</th>
                    <th className="text-right pb-2">Usage</th>
                  </tr>
                </thead>
                <tbody>
                  {queues.map((queue) => (
                    <tr key={queue.name} className="border-t border-gray-700">
                      <td className="py-2">{queue.name}</td>
                      <td className="py-2 text-right">{queue.running_applications}</td>
                      <td className="py-2 text-right">{queue.pending_applications}</td>
                      <td className="py-2 text-right">
                        {Math.round(queue.used_capacity / queue.capacity * 100)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

interface StatCardProps {
  icon: React.ReactNode
  title: string
  value: number
  subtitle: string
}

function StatCard({ icon, title, value, subtitle }: StatCardProps) {
  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
      <div className="flex items-center gap-2 mb-2">
        {icon}
        <span className="text-gray-400">{title}</span>
      </div>
      <div className="text-2xl font-bold">{value}</div>
      <div className="text-sm text-gray-500">{subtitle}</div>
    </div>
  )
}

function StatusBadge({ status: string }) {
  const status = string.toLowerCase()
  const colors = {
    running: 'bg-green-900 text-green-500',
    completed: 'bg-blue-900 text-blue-500',
    pending: 'bg-yellow-900 text-yellow-500',
    failed: 'bg-red-900 text-red-500',
    unknown: 'bg-gray-700 text-gray-400',
  }

  const colorClass = colors[status as keyof typeof colors] || colors.unknown

  return (
    <span className={`px-2 py-1 rounded text-xs ${colorClass}`}>
      {status.toUpperCase()}
    </span>
  )
}