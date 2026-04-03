import { useState, type FormEvent, type KeyboardEvent } from 'react';
import { Send, Loader2, Sparkles } from 'lucide-react';

interface MessageInputProps {
  onSend: (message: string) => void;
  isLoading?: boolean;
}

export default function MessageInput({ onSend, isLoading }: MessageInputProps) {
  const [input, setInput] = useState('');

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (input.trim() && !isLoading) {
      onSend(input.trim());
      setInput('');
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="p-4 border-t border-gray-700 bg-gray-800/50">
      <div className="max-w-4xl mx-auto">
        <div className="flex gap-2 items-end">
          <div className="flex-1 relative">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isLoading}
              placeholder="输入问题，例如：查看失败的 Spark 任务..."
              rows={1}
              className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 disabled:opacity-50 resize-none"
              style={{ minHeight: '48px', maxHeight: '200px' }}
            />
          </div>

          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="flex-shrink-0 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:cursor-not-allowed rounded-xl px-4 py-3 flex items-center gap-2 transition-colors"
          >
            {isLoading ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Send className="w-5 h-5" />
            )}
          </button>
        </div>

        <div className="mt-2 flex items-center justify-between text-xs text-gray-500">
          <div className="flex items-center gap-1">
            <Sparkles className="w-3 h-3" />
            <span>Shift + Enter 换行</span>
          </div>
          <span>支持 Markdown 格式</span>
        </div>
      </div>
    </form>
  );
}