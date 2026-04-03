import { create } from 'zustand';
import type { Message, ChatRequest } from '../types';
import { sendMessage } from '../api/client';

interface ChatStore {
  messages: Message[];
  conversationId: string | null;
  isLoading: boolean;
  error: string | null;
  addMessage: (message: Message) => void;
  sendMessage: (content: string) => Promise<void>;
  clearMessages: () => void;
}

const generateId = () => `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

export const useChatStore = create<ChatStore>((set, get) => ({
  messages: [],
  conversationId: null,
  isLoading: false,
  error: null,
  
  addMessage: (message) => set((state) => ({
    messages: [...state.messages, message]
  })),
  
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
        conversation_id: get().conversationId ?? undefined,
      };
      
      const response = await sendMessage(request);
      
      const assistantMessage: Message = {
        id: generateId(),
        role: 'assistant',
        content: response.response,
        timestamp: new Date(),
        structuredData: response.structured_data,
      };
      
      set((state) => ({
        messages: [...state.messages, assistantMessage],
        conversationId: response.conversation_id,
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
  
  clearMessages: () => set({
    messages: [],
    conversationId: null,
    error: null,
  }),
}));