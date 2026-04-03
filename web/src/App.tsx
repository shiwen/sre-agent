import { useState } from 'react'
import { Sidebar } from './components/Sidebar'
import { ChatPanel } from './components/ChatPanel'
import { Dashboard } from './components/Dashboard'
import { PatrolPanel } from './components/PatrolPanel'

function App() {
  const [activeTab, setActiveTab] = useState('chat')

  const renderContent = () => {
    switch (activeTab) {
      case 'chat':
        return <ChatPanel />
      case 'dashboard':
        return <Dashboard />
      case 'patrol':
        return <PatrolPanel />
      case 'settings':
        return <SettingsPanel />
      default:
        return <ChatPanel />
    }
  }

  return (
    <div className="flex h-screen bg-gray-900">
      <Sidebar activeTab={activeTab} onTabChange={setActiveTab} />
      <main className="flex-1 flex flex-col overflow-hidden">
        {renderContent()}
      </main>
    </div>
  )
}

function SettingsPanel() {
  return (
    <div className="p-6">
      <h2 className="text-xl font-bold mb-6">Settings</h2>
      
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-4 mb-4">
        <h3 className="font-semibold mb-4">LLM Configuration</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">Primary Endpoint</label>
            <input
              type="text"
              placeholder="http://localhost:8000/v1"
              className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Model</label>
            <input
              type="text"
              placeholder="glm-4"
              className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2"
            />
          </div>
        </div>
      </div>

      <div className="bg-gray-800 rounded-lg border border-gray-700 p-4 mb-4">
        <h3 className="font-semibold mb-4">Patrol Configuration</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">Interval (minutes)</label>
            <input
              type="number"
              defaultValue={30}
              className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Notification Channel</label>
            <select className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2">
              <option value="feishu">Feishu</option>
              <option value="slack">Slack</option>
              <option value="none">None</option>
            </select>
          </div>
        </div>
      </div>

      <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
        <h3 className="font-semibold mb-4">Kubernetes Configuration</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">Namespace</label>
            <input
              type="text"
              defaultValue="spark-operator"
              className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2"
            />
          </div>
        </div>
      </div>
    </div>
  )
}

export default App