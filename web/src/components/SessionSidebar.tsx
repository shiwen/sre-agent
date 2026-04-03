import { Plus, MessageSquare } from 'lucide-react';
import type { Session } from '../types';

interface SessionSidebarProps {
  sessions: Session[];
  currentSessionId: string | null;
  isOpen: boolean;
  onClose: () => void;
  onNewChat: () => void;
}

export default function SessionSidebar({
  sessions,
  currentSessionId,
  isOpen,
  onClose,
  onNewChat,
}: SessionSidebarProps) {
  return (
    <>
      {/* 遮罩层（移动端） */}
      {isOpen && (
        <div
          className="lg:hidden fixed inset-0 bg-black/50 z-40"
          onClick={onClose}
        />
      )}

      {/* 侧边栏 */}
      <aside
        className={`
          fixed lg:static inset-y-0 left-0 z-50
          w-64 bg-gray-800 border-r border-gray-700
          transform transition-transform duration-200 ease-in-out
          ${isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
          flex flex-col
        `}
      >
        {/* 头部 */}
        <div className="p-4 border-b border-gray-700">
          <button
            onClick={onNewChat}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
          >
            <Plus className="w-4 h-4" />
            新建对话
          </button>
        </div>

        {/* 会话列表 */}
        <div className="flex-1 overflow-y-auto p-2">
          {sessions.length === 0 ? (
            <div className="text-center text-gray-500 py-8">
              <MessageSquare className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p className="text-sm">暂无历史对话</p>
            </div>
          ) : (
            <div className="space-y-1">
              {sessions.map((session) => (
                <button
                  key={session.id}
                  className={`
                    w-full text-left p-3 rounded-lg transition-colors
                    ${session.id === currentSessionId
                      ? 'bg-gray-700 text-white'
                      : 'text-gray-400 hover:bg-gray-700/50 hover:text-gray-200'
                    }
                  `}
                >
                  <div className="flex items-start gap-2">
                    <MessageSquare className="w-4 h-4 mt-0.5 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">
                        对话 {session.id.slice(0, 8)}
                      </p>
                      <p className="text-xs text-gray-500">
                        {session.message_count || 0} 条消息
                      </p>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* 底部 */}
        <div className="p-4 border-t border-gray-700">
          <p className="text-xs text-gray-500 text-center">
            SRE Agent v0.1.0
          </p>
        </div>
      </aside>
    </>
  );
}