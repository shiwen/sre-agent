import MessageList from './MessageList';
import MessageInput from './MessageInput';
import { useChatStore } from '../hooks/useChat';
import { Trash2, AlertCircle } from 'lucide-react';

export default function Chat() {
  const { messages, isLoading, error, sendMessage, clearMessages } = useChatStore();
  
  return (
    <div className="flex flex-col h-full bg-gray-900">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-700 bg-gray-800">
        <div className="flex items-center gap-2">
          <h1 className="text-lg font-semibold text-gray-100">SRE Agent</h1>
          <span className="text-xs bg-blue-500 text-white px-2 py-0.5 rounded">AI Powered</span>
        </div>
        
        {messages.length > 0 && (
          <button
            onClick={clearMessages}
            className="flex items-center gap-1 text-gray-400 hover:text-gray-200 text-sm transition-colors"
          >
            <Trash2 className="w-4 h-4" />
            Clear
          </button>
        )}
      </div>
      
      {/* Error display */}
      {error && (
        <div className="px-4 py-2 bg-red-900/50 border-b border-red-700 flex items-center gap-2 text-red-200">
          <AlertCircle className="w-4 h-4" />
          <span className="text-sm">{error}</span>
        </div>
      )}
      
      {/* Messages */}
      <MessageList messages={messages} isLoading={isLoading} />
      
      {/* Input */}
      <MessageInput onSend={sendMessage} isLoading={isLoading} />
    </div>
  );
}