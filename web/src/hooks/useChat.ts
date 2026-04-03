import { create } from 'zustand';
import type { Message, ChatRequest, StructuredData } from '../types';
import { sendMessage, sendMessageStream } from '../api/client';

interface ChatStore {
  messages: Message[];
  sessionId: string | null;
  isLoading: boolean;
  isStreaming: boolean;
  error: string | null;
  addMessage: (message: Message) => void;
  sendMessage: (content: string) => Promise<void>;
  sendMessageStream: (content: string) => Promise<void>;
  clearMessages: () => void;
  setSessionId: (id: string | null) => void;
}

const generateId = () => `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

export const useChatStore = create<ChatStore>((set, get) => ({
  messages: [],
  sessionId: null,
  isLoading: false,
  isStreaming: false,
  error: null,

  addMessage: (message) => set((state) => ({
    messages: [...state.messages, message]
  })),

  setSessionId: (id) => set({ sessionId: id }),

  sendMessage: async (content: string) => {
    const userMessage: Message = {
      id: generateId(),
      role: 'user',
      content,
      timestamp: new Date(),
    };

    set((state) => ({
      messages: [...state.messages, userMessage],
      isLoading: true,
      error: null,
    }));

    try {
      const request: ChatRequest = {
        message: content,
        session_id: get().sessionId || undefined,
      };

      const response = await sendMessage(request);

      const structuredData: StructuredData | undefined = response.structured_data
        ? {
            type: response.structured_data.type || 'table',
            data: response.structured_data.data,
            columns: response.structured_data.columns,
          }
        : undefined;

      const assistantMessage: Message = {
        id: generateId(),
        role: 'assistant',
        content: response.response,
        timestamp: new Date(),
        structuredData,
      };

      set((state) => ({
        messages: [...state.messages, assistantMessage],
        sessionId: response.session_id || null,
        isLoading: false,
      }));
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      set(() => ({
        isLoading: false,
        error: errorMessage,
      }));
    }
  },

  sendMessageStream: async (content: string) => {
    const userMessage: Message = {
      id: generateId(),
      role: 'user',
      content,
      timestamp: new Date(),
    };

    // 创建一个空的助手消息占位符
    const assistantMessageId = generateId();
    const assistantMessage: Message = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
    };

    set((state) => ({
      messages: [...state.messages, userMessage, assistantMessage],
      isStreaming: true,
      error: null,
    }));

    try {
      const request: ChatRequest = {
        message: content,
        session_id: get().sessionId || undefined,
      };

      let fullContent = '';
      let structuredData: StructuredData | undefined;

      await sendMessageStream(request, {
        onStart: (sessionId) => {
          set({ sessionId });
        },
        onChunk: (text) => {
          fullContent += text;
          set((state) => ({
            messages: state.messages.map((m) =>
              m.id === assistantMessageId
                ? { ...m, content: fullContent }
                : m
            ),
          }));
        },
        onData: (data) => {
          structuredData = data as StructuredData;
          set((state) => ({
            messages: state.messages.map((m) =>
              m.id === assistantMessageId
                ? { ...m, structuredData }
                : m
            ),
          }));
        },
        onDone: (sessionId) => {
          set({ sessionId, isStreaming: false });
        },
        onError: (error) => {
          set({ error, isStreaming: false });
        },
      });
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      set(() => ({
        isStreaming: false,
        error: errorMessage,
      }));
    }
  },

  clearMessages: () => set({
    messages: [],
    sessionId: null,
    error: null,
  }),
}));