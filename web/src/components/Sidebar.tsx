import { useState, useEffect } from 'react'
import {
  MessageSquare,
  LayoutDashboard,
  Layers,
  Search,
  Settings,
  Activity,
  ChevronDown,
  ChevronRight,
  Server,
} from 'lucide-react'
import { sparkService, queueService, healthService } from '../services/api'
import type { SparkApplication, QueueInfo } from '../types/chat'

interface SidebarProps {
  activeTab: string
  onTabChange: (tab: string) => void
}

export function Sidebar({ activeTab, onTabChange }: SidebarProps) {
  const [sparkExpanded, setSparkExpanded] = useState(false)
  const [queueExpanded, setQueueExpanded] = useState(false)
  const [sparkApps, setSparkApps] = useState<SparkApplication[]>([])
  const [queues, setQueues] = useState<QueueInfo[]>([])
  const [health, setHealth] = useState<{ status: string } | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true)
      try {
        const [apps, queueList, healthStatus] = await Promise.all([
          sparkService.listApplications(),
          queueService.listQueues(),
          healthService.checkHealth(),
        ])
        setSparkApps(apps)
        setQueues(queueList)
        setHealth(healthStatus)
      } catch (error) {
        console.error('Failed to fetch sidebar data:', error)
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  const statusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'running':
      case 'completed':
        return 'text-green-500'
      case 'pending':
        return 'text-yellow-500'
      case 'failed':
      case 'error':
        return 'text-red-500'
      default:
        return 'text-gray-400'
    }
  }

  return (
    <div className="w-64 bg-gray-900 border-r border-gray-700 flex flex-col">
      <div className="p-4 border-b border-gray-700">
        <h1 className="font-bold text-lg flex items-center gap-2">
          <Server className="w-6 h-6 text-blue-500" />
          SRE Agent
        </h1>
        <div className="flex items-center gap-2 mt-2 text-sm">
          <Activity className={`w-4 h-4 ${health?.status === 'healthy' ? 'text-green-500' : 'text-red-500'}`} />
          <span className="text-gray-400">{health?.status || 'Checking...'}</span>
        </div>
      </div>

      <nav className="flex-1 p-2">
        <NavItem
          icon={<MessageSquare className="w-5 h-5" />}
          label="Chat"
          active={activeTab === 'chat'}
          onClick={() => onTabChange('chat')}
        />

        <NavItem
          icon={<LayoutDashboard className="w-5 h-5" />}
          label="Dashboard"
          active={activeTab === 'dashboard'}
          onClick={() => onTabChange('dashboard')}
        />

        <NavItem
          icon={<Search className="w-5 h-5" />}
          label="Patrol"
          active={activeTab === 'patrol'}
          onClick={() => onTabChange('patrol')}
        />

        <div className="border-t border-gray-700 my-2" />

        <CollapsibleItem
          icon={<Layers className="w-5 h-5" />}
          label="Spark Apps"
          expanded={sparkExpanded}
          onToggle={() => setSparkExpanded(!sparkExpanded)}
          loading={loading}
        >
          {sparkApps.map((app) => (
            <div
              key={app.name}
              className="px-3 py-1 text-sm flex items-center justify-between hover:bg-gray-800 rounded cursor-pointer"
            >
              <span className="truncate">{app.name}</span>
              <span className={`text-xs ${statusColor(app.status)}`}>
                {app.status}
              </span>
            </div>
          ))}
          {sparkApps.length === 0 && !loading && (
            <div className="px-3 py-2 text-sm text-gray-500">No applications</div>
          )}
        </CollapsibleItem>

        <CollapsibleItem
          icon={<Activity className="w-5 h-5" />}
          label="Queues"
          expanded={queueExpanded}
          onToggle={() => setQueueExpanded(!queueExpanded)}
          loading={loading}
        >
          {queues.map((queue) => (
            <div
              key={queue.name}
              className="px-3 py-1 text-sm flex items-center justify-between hover:bg-gray-800 rounded cursor-pointer"
            >
              <span className="truncate">{queue.name}</span>
              <span className="text-xs text-gray-400">
                {queue.running_applications}/{queue.capacity}
              </span>
            </div>
          ))}
          {queues.length === 0 && !loading && (
            <div className="px-3 py-2 text-sm text-gray-500">No queues</div>
          )}
        </CollapsibleItem>
      </nav>

      <div className="p-2 border-t border-gray-700">
        <NavItem
          icon={<Settings className="w-5 h-5" />}
          label="Settings"
          active={activeTab === 'settings'}
          onClick={() => onTabChange('settings')}
        />
      </div>
    </div>
  )
}

interface NavItemProps {
  icon: React.ReactNode
  label: string
  active: boolean
  onClick: () => void
}

function NavItem({ icon, label, active, onClick }: NavItemProps) {
  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg transition-colors ${
        active
          ? 'bg-blue-600 text-white'
          : 'text-gray-400 hover:bg-gray-800 hover:text-white'
      }`}
    >
      {icon}
      <span>{label}</span>
    </button>
  )
}

interface CollapsibleItemProps {
  icon: React.ReactNode
  label: string
  expanded: boolean
  onToggle: () => void
  children: React.ReactNode
  loading?: boolean
}

function CollapsibleItem({ icon, label, expanded, onToggle, children, loading }: CollapsibleItemProps) {
  return (
    <div>
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-2 px-3 py-2 text-gray-400 hover:bg-gray-800 hover:text-white rounded-lg transition-colors"
      >
        {icon}
        <span className="flex-1">{label}</span>
        {loading ? (
          <Activity className="w-4 h-4 animate-pulse" />
        ) : expanded ? (
          <ChevronDown className="w-4 h-4" />
        ) : (
          <ChevronRight className="w-4 h-4" />
        )}
      </button>
      {expanded && <div className="ml-4 mt-1 space-y-1">{children}</div>}
    </div>
  )
}