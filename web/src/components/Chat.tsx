import { useState, useEffect, useRef } from 'react';
import MessageList from './MessageList';
import MessageInput from './MessageInput';
import SessionSidebar from './SessionSidebar';
import { useChatStore } from '../hooks/useChat';
import { listSessions } from '../api/client';
import { Trash2, AlertCircle, Menu, X, Zap } from 'lucide-react';
import type { Session } from '../types';

export default function Chat() {
  const { messages, isLoading, isStreaming, error, sendMessageStream, clearMessages, sessionId, setSessionId } = useChatStore();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sessions, setSessions] = useState<Session[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // 加载会话列表
  useEffect(() => {
    loadSessions();
  }, []);

  const loadSessions = async () => {
    try {
      const sessionList = await listSessions();
      setSessions(sessionList);
    } catch (err) {
      console.error('Failed to load sessions:', err);
    }
  };

  const handleSend = async (content: string) => {
    await sendMessageStream(content);
    loadSessions(); // 刷新会话列表
  };

  const handleNewChat = () => {
    clearMessages();
    setSessionId(null);
  };

  return (
    <div className="flex h-full bg-gray-900">
      {/* 侧边栏 */}
      <SessionSidebar
        sessions={sessions}
        currentSessionId={sessionId}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        onNewChat={handleNewChat}
      />

      {/* 主聊天区域 */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-700 bg-gray-800">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="lg:hidden p-1.5 text-gray-400 hover:text-gray-200 hover:bg-gray-700 rounded-lg"
            >
              {sidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center">
                <Zap className="w-5 h-5 text-white" />
              </div>
              <div>
                <h1 className="text-lg font-semibold text-gray-100">SRE Agent</h1>
                <p className="text-xs text-gray-400">Spark on K8s 智能运维助手</p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {messages.length > 0 && (
              <button
                onClick={handleNewChat}
                className="flex items-center gap-1.5 px-3 py-1.5 text-gray-400 hover:text-gray-200 hover:bg-gray-700 text-sm rounded-lg transition-colors"
              >
                <Trash2 className="w-4 h-4" />
                清空对话
              </button>
            )}
          </div>
        </div>

        {/* Error display */}
        {error && (
          <div className="px-4 py-2 bg-red-900/50 border-b border-red-700 flex items-center gap-2 text-red-200">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span className="text-sm">{error}</span>
          </div>
        )}

        {/* Messages */}
        <MessageList
          messages={messages}
          isLoading={isLoading || isStreaming}
          messagesEndRef={messagesEndRef}
        />

        {/* Input */}
        <MessageInput onSend={handleSend} isLoading={isLoading || isStreaming} />
      </div>
    </div>
  );
}