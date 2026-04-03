import type { Message } from '../types/chat'
import { User, Bot, AlertCircle, CheckCircle, Clock } from 'lucide-react'

interface ChatMessageProps {
  message: Message
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user'
  const isSystem = message.role === 'system'

  return (
    <div
      className={`flex gap-3 p-4 ${isUser ? 'justify-end' : 'justify-start'}`}
    >
      {!isUser && (
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center">
          {isSystem ? (
            <AlertCircle className="w-5 h-5 text-white" />
          ) : (
            <Bot className="w-5 h-5 text-white" />
          )}
        </div>
      )}

      <div
        className={`max-w-[80%] rounded-lg p-3 ${
          isUser
            ? 'bg-blue-600 text-white'
            : isSystem
            ? 'bg-yellow-900/50 border border-yellow-700'
            : 'bg-gray-800 border border-gray-700'
        }`}
      >
        <div className="flex items-center gap-2 mb-1">
          <span className="font-medium text-sm">
            {isUser ? 'You' : isSystem ? 'System' : 'SRE Agent'}
          </span>
          <span className="text-xs text-gray-400">
            {message.timestamp.toLocaleTimeString()}
          </span>
        </div>
        <div className="whitespace-pre-wrap">{message.content}</div>
      </div>

      {isUser && (
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gray-600 flex items-center justify-center">
          <User className="w-5 h-5 text-white" />
        </div>
      )}
    </div>
  )
}

interface ActionStatusProps {
  status: 'pending' | 'running' | 'completed' | 'failed'
}

export function ActionStatus({ status }: ActionStatusProps) {
  const statusConfig = {
    pending: { icon: Clock, color: 'text-yellow-500', text: 'Pending' },
    running: { icon: Clock, color: 'text-blue-500', text: 'Running' },
    completed: { icon: CheckCircle, color: 'text-green-500', text: 'Completed' },
    failed: { icon: AlertCircle, color: 'text-red-500', text: 'Failed' },
  }

  const config = statusConfig[status]
  const Icon = config.icon

  return (
    <span className={`flex items-center gap-1 ${config.color}`}>
      <Icon className="w-4 h-4" />
      {config.text}
    </span>
  )
}