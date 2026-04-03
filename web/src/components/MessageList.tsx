import type { Message } from '../types';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import TaskTable from './TaskTable';
import { Bot, User } from 'lucide-react';
import type { RefObject } from 'react';

interface MessageListProps {
  messages: Message[];
  isLoading: boolean;
  messagesEndRef: RefObject<HTMLDivElement | null>;
}

export default function MessageList({ messages, isLoading, messagesEndRef }: MessageListProps) {
  if (messages.length === 0 && !isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center text-gray-400">
        <div className="text-center max-w-md px-4">
          <Bot className="w-16 h-16 mx-auto mb-4 opacity-50" />
          <p className="text-lg font-medium text-gray-300">SRE Agent</p>
          <p className="text-sm mt-2 text-gray-500">Spark on K8s 智能运维助手</p>
          <p className="text-sm mt-4 text-gray-500">输入问题开始对话，例如：</p>
          <ul className="text-sm mt-3 space-y-2 text-gray-400">
            <li className="bg-gray-800/50 px-3 py-2 rounded-lg">"查看当前的 Spark 应用状态"</li>
            <li className="bg-gray-800/50 px-3 py-2 rounded-lg">"YuniKorn 队列资源使用情况"</li>
            <li className="bg-gray-800/50 px-3 py-2 rounded-lg">"分析最近的任务失败原因"</li>
          </ul>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      {messages.map((message) => (
        <div
          key={message.id}
          className={`flex gap-3 ${
            message.role === 'user' ? 'justify-end' : 'justify-start'
          }`}
        >
          {message.role === 'assistant' && (
            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center">
              <Bot className="w-5 h-5 text-white" />
            </div>
          )}

          <div
            className={`max-w-[85%] rounded-lg p-3 ${
              message.role === 'user'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-800 text-gray-100 border border-gray-700'
            }`}
          >
            {message.role === 'assistant' ? (
              <div className="prose prose-invert prose-sm max-w-none">
                {message.content ? (
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {message.content}
                  </ReactMarkdown>
                ) : (
                  <div className="flex gap-1 py-1">
                    <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                    <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                    <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                  </div>
                )}

                {message.structuredData && (
                  <div className="mt-4">
                    <TaskTable data={message.structuredData} />
                  </div>
                )}
              </div>
            ) : (
              <p className="whitespace-pre-wrap">{message.content}</p>
            )}

            <div className="text-xs mt-2 opacity-60">
              {message.timestamp.toLocaleTimeString()}
            </div>
          </div>

          {message.role === 'user' && (
            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gray-600 flex items-center justify-center">
              <User className="w-5 h-5 text-white" />
            </div>
          )}
        </div>
      ))}

      {isLoading && (
        <div className="flex gap-3 justify-start">
          <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center">
            <Bot className="w-5 h-5 text-white" />
          </div>
          <div className="bg-gray-800 rounded-lg p-3 border border-gray-700">
            <div className="flex gap-1">
              <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
              <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
              <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
            </div>
          </div>
        </div>
      )}

      <div ref={messagesEndRef} />
    </div>
  );
}