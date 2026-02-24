import { describe, it, expect, beforeEach } from 'vitest';
import { useCharacterChatStore } from './characterChatStore';

const mockSession = {
  id: 's1',
  requester: { persona_id: 'p1', display_name: '캐릭터A', owner_id: 'u1' },
  responder: { persona_id: 'p2', display_name: '캐릭터B', owner_id: 'u2' },
  status: 'active',
  max_turns: 10,
  current_turn: 2,
  is_public: true,
  age_rating: 'all' as const,
  total_cost: 0.001,
  requested_at: '2026-01-01T00:00:00Z',
  started_at: '2026-01-01T00:01:00Z',
  completed_at: null,
};

const mockMessage = {
  id: 1,
  persona_id: 'p1',
  persona_display_name: '캐릭터A',
  content: '안녕하세요!',
  turn_number: 0,
  created_at: '2026-01-01T00:01:00Z',
};

describe('useCharacterChatStore', () => {
  beforeEach(() => {
    useCharacterChatStore.setState({
      incoming: null,
      outgoing: null,
      currentChat: null,
      loading: false,
      advancing: false,
    });
  });

  it('should start with null states', () => {
    const state = useCharacterChatStore.getState();
    expect(state.incoming).toBeNull();
    expect(state.outgoing).toBeNull();
    expect(state.currentChat).toBeNull();
  });

  it('should start with loading and advancing false', () => {
    const state = useCharacterChatStore.getState();
    expect(state.loading).toBe(false);
    expect(state.advancing).toBe(false);
  });

  it('should set incoming data', () => {
    useCharacterChatStore.setState({ incoming: { items: [mockSession], total: 1 } });
    expect(useCharacterChatStore.getState().incoming?.total).toBe(1);
    expect(useCharacterChatStore.getState().incoming?.items[0].status).toBe('active');
  });

  it('should set outgoing data', () => {
    useCharacterChatStore.setState({ outgoing: { items: [mockSession], total: 1 } });
    expect(useCharacterChatStore.getState().outgoing?.items).toHaveLength(1);
  });

  it('should set currentChat with session and messages', () => {
    useCharacterChatStore.setState({
      currentChat: { session: mockSession, messages: [mockMessage] },
    });
    const chat = useCharacterChatStore.getState().currentChat;
    expect(chat?.session.id).toBe('s1');
    expect(chat?.messages).toHaveLength(1);
    expect(chat?.messages[0].content).toBe('안녕하세요!');
  });

  it('should append message and increment turn', () => {
    useCharacterChatStore.setState({
      currentChat: { session: mockSession, messages: [mockMessage] },
    });

    const newMsg = {
      id: 2,
      persona_id: 'p2',
      persona_display_name: '캐릭터B',
      content: '반갑습니다!',
      turn_number: 1,
      created_at: '2026-01-01T00:02:00Z',
    };

    // advanceChat의 상태 업데이트 로직 시뮬레이션
    useCharacterChatStore.setState((s) => ({
      currentChat: s.currentChat
        ? {
            ...s.currentChat,
            messages: [...s.currentChat.messages, newMsg],
            session: {
              ...s.currentChat.session,
              current_turn: s.currentChat.session.current_turn + 1,
            },
          }
        : s.currentChat,
    }));

    const chat = useCharacterChatStore.getState().currentChat;
    expect(chat?.messages).toHaveLength(2);
    expect(chat?.messages[1].content).toBe('반갑습니다!');
    expect(chat?.session.current_turn).toBe(3);
  });

  it('should handle advancing state', () => {
    useCharacterChatStore.setState({ advancing: true });
    expect(useCharacterChatStore.getState().advancing).toBe(true);
    useCharacterChatStore.setState({ advancing: false });
    expect(useCharacterChatStore.getState().advancing).toBe(false);
  });
});
