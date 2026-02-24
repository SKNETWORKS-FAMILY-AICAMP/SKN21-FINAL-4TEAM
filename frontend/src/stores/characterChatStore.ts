import { create } from 'zustand';
import { api } from '@/lib/api';

type ChatParticipant = {
  persona_id: string;
  display_name: string;
  owner_id: string;
};

type ChatSession = {
  id: string;
  requester: ChatParticipant;
  responder: ChatParticipant;
  status: string;
  max_turns: number;
  current_turn: number;
  is_public: boolean;
  age_rating: 'all' | '15+' | '18+';
  total_cost: number;
  requested_at: string;
  started_at: string | null;
  completed_at: string | null;
};

type ChatMessage = {
  id: number;
  persona_id: string;
  persona_display_name: string;
  content: string;
  turn_number: number;
  created_at: string;
};

type ChatDetail = {
  session: ChatSession;
  messages: ChatMessage[];
};

type CharacterChatState = {
  incoming: { items: ChatSession[]; total: number } | null;
  outgoing: { items: ChatSession[]; total: number } | null;
  currentChat: ChatDetail | null;
  loading: boolean;
  advancing: boolean;
  fetchIncoming: () => Promise<void>;
  fetchOutgoing: () => Promise<void>;
  fetchChat: (sessionId: string) => Promise<void>;
  requestChat: (
    requesterPersonaId: string,
    responderPersonaId: string,
    maxTurns?: number,
  ) => Promise<ChatSession>;
  respondToRequest: (sessionId: string, accept: boolean) => Promise<void>;
  advanceChat: (sessionId: string) => Promise<ChatMessage>;
};

export const useCharacterChatStore = create<CharacterChatState>((set) => ({
  incoming: null,
  outgoing: null,
  currentChat: null,
  loading: false,
  advancing: false,
  fetchIncoming: async () => {
    set({ loading: true });
    try {
      const data = await api.get<{ items: ChatSession[]; total: number }>(
        '/character-chats/requests/incoming',
      );
      set({ incoming: data });
    } catch (err) {
      console.error('Failed to fetch incoming requests:', err);
    } finally {
      set({ loading: false });
    }
  },
  fetchOutgoing: async () => {
    set({ loading: true });
    try {
      const data = await api.get<{ items: ChatSession[]; total: number }>(
        '/character-chats/requests/outgoing',
      );
      set({ outgoing: data });
    } catch (err) {
      console.error('Failed to fetch outgoing requests:', err);
    } finally {
      set({ loading: false });
    }
  },
  fetchChat: async (sessionId: string) => {
    set({ loading: true });
    try {
      const data = await api.get<ChatDetail>(`/character-chats/${sessionId}`);
      set({ currentChat: data });
    } catch (err) {
      console.error('Failed to fetch chat:', err);
    } finally {
      set({ loading: false });
    }
  },
  requestChat: async (requesterPersonaId, responderPersonaId, maxTurns = 10) => {
    const data = await api.post<ChatSession>('/character-chats/request', {
      requester_persona_id: requesterPersonaId,
      responder_persona_id: responderPersonaId,
      max_turns: maxTurns,
    });
    return data;
  },
  respondToRequest: async (sessionId, accept) => {
    await api.post(`/character-chats/${sessionId}/respond`, { accept });
  },
  advanceChat: async (sessionId) => {
    set({ advancing: true });
    try {
      const msg = await api.post<ChatMessage>(`/character-chats/${sessionId}/advance`);
      set((s) => ({
        currentChat: s.currentChat
          ? {
              ...s.currentChat,
              messages: [...s.currentChat.messages, msg],
              session: {
                ...s.currentChat.session,
                current_turn: s.currentChat.session.current_turn + 1,
              },
            }
          : s.currentChat,
      }));
      return msg;
    } finally {
      set({ advancing: false });
    }
  },
}));

export type { ChatSession, ChatMessage, ChatDetail, ChatParticipant };
