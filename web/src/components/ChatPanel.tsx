import { useState, useRef, useEffect } from 'react'
import type { Message, Action } from '../types/chat'
import { ChatMessage, ActionStatus } from './ChatMessage'
import { ChatInput } from './ChatInput'
import { chatService } from '../services/api'
import { Sparkles, RefreshCw } from 'lucide-react'

export function ChatPanel() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      role: 'assistant',
      content: 'Hello! I am SRE Agent for Spark on Kubernetes. I can help you with:\n\n• Spark application monitoring and troubleshooting\n• YuniKorn queue management\n• Kubernetes resource queries\n• Automated patrol and issue detection\n\nWhat would you like to know?',
      timestamp: new Date(),
    },
  ])
  const [isLoading, setIsLoading] = useState(false)
  const [sessionId, setSessionId] = useState<string>()
  const [actions, setActions] = useState<Action[]>([])
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async (content: string) => {
    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content,
      timestamp: new Date(),
    }
    setMessages((prev) => [...prev, userMessage])
    setIsLoading(true)
    setActions([])

    try {
      const response = await chatService.sendMessage({
        message: content,
        session_id: sessionId,
      })

      setSessionId(response.session_id)

      if (response.actions) {
        setActions(response.actions)
      }

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: response.response,
        timestamp: new Date(),
      }
      setMessages((prev) => [...prev, assistantMessage])
    } catch (error) {
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'system',
        content: `Error: ${error instanceof Error ? error.message : 'Failed to send message'}`,
        timestamp: new Date(),
      }
      setMessages((prev) => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  const handleClear = () => {
    setMessages([
      {
        id: '1',
        role: 'assistant',
        content: 'Session cleared. What would you like to know?',
        timestamp: new Date(),
      },
    ])
    setSessionId(undefined)
    setActions([])
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between p-4 border-b border-gray-700">
        <div className="flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-blue-500" />
          <h2 className="font-semibold">SRE Agent Chat</h2>
        </div>
        <button
          onClick={handleClear}
          className="text-gray-400 hover:text-white flex items-center gap-1"
        >
          <RefreshCw className="w-4 h-4" />
          Clear
        </button>
      </div>

      <div className="flex-1 overflow-y-auto">
        {messages.map((message) => (
          <ChatMessage key={message.id} message={message} />
        ))}

        {actions.length > 0 && (
          <div className="p-4 border-t border-gray-700">
            <h3 className="font-medium mb-2">Actions</h3>
            <div className="space-y-2">
              {actions.map((action, index) => (
                <div
                  key={index}
                  className="bg-gray-800 rounded-lg p-3 border border-gray-700"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium">{action.type}</span>
                    <ActionStatus status={action.status} />
                  </div>
                  <p className="text-sm text-gray-400 mt-1">{action.description}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <ChatInput onSend={handleSend} disabled={isLoading} />
    </div>
  )
}