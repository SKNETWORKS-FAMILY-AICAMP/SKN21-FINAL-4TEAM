'use client';

import { useEffect, useCallback, useState, useRef } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import dynamic from 'next/dynamic';
import { ChevronDown, Flag, Gem } from 'lucide-react';
import { ChatWindow } from '@/components/chat/ChatWindow';
import { MessageInput } from '@/components/chat/MessageInput';
import { RelationshipBar } from '@/components/chat/RelationshipBar';
import { useChatStore } from '@/stores/chatStore';
import { useLive2DStore } from '@/stores/live2dStore';
import { api } from '@/lib/api';
import { connectSSE } from '@/lib/sse';
import { ReportModal } from '@/components/persona/ReportModal';

const BackgroundLayer = dynamic(
  () => import('@/components/live2d/BackgroundLayer').then((m) => ({ default: m.BackgroundLayer })),
  { ssr: false },
);

const Live2DCanvas = dynamic(
  () => import('@/components/live2d/Live2DCanvas').then((m) => ({ default: m.Live2DCanvas })),
  { ssr: false },
);

const Live2DController = dynamic(
  () =>
    import('@/components/live2d/Live2DController').then((m) => ({ default: m.Live2DController })),
  { ssr: false },
);

type LLMModel = {
  id: string;
  display_name: string;
  provider: string;
  tier: string;
  credit_per_1k_tokens: number;
};

export default function ChatPage() {
  const params = useParams();
  const sessionId = params.sessionId as string;
  const { messages, isStreaming, addMessage, appendToLastMessage, setStreaming, clearMessages, setMessages, updateMessage } =
    useChatStore();
  const { currentEmotion, modelPath } = useLive2DStore();
  const [personaId, setPersonaId] = useState<string | null>(null);
  const [personaName, setPersonaName] = useState<string>('');
  const [reportOpen, setReportOpen] = useState(false);

  // 모델 선택 상태
  const [models, setModels] = useState<LLMModel[]>([]);
  const [currentModelId, setCurrentModelId] = useState<string | null>(null);
  const [modelDropdownOpen, setModelDropdownOpen] = useState(false);
  const [modelSwitching, setModelSwitching] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const abortController = new AbortController();
    clearMessages();

    // Load session detail
    api
      .get<{ persona_id: string; llm_model_id: string | null; persona_name?: string }>(`/chat/sessions/${sessionId}`, {
        signal: abortController.signal,
      })
      .then((res) => {
        setPersonaId(res.persona_id);
        setCurrentModelId(res.llm_model_id);
        if (res.persona_name) setPersonaName(res.persona_name);
      })
      .catch((err) => {
        if (err instanceof DOMException && err.name === 'AbortError') return;
        console.error('Failed to load session:', err);
      });

    // Load available models
    api
      .get<LLMModel[]>('/models', { signal: abortController.signal })
      .then((res) => setModels(res))
      .catch((err) => {
        if (err instanceof DOMException && err.name === 'AbortError') return;
      });

    // Load messages
    const loadMessages = async () => {
      try {
        const res = await api.get<{ items: Array<{ id: number; role: string; content: string; emotion_signal?: Record<string, unknown>; is_edited?: boolean }>; total: number }>(
          `/chat/sessions/${sessionId}/messages`,
          { signal: abortController.signal },
        );
        setMessages(
          (res.items ?? []).map((m) => ({
            id: m.id,
            role: m.role as 'user' | 'assistant',
            content: m.content,
            emotionSignal: m.emotion_signal as { label: string; intensity: number; confidence: number } | undefined,
            isEdited: m.is_edited,
          })),
        );
      } catch (err) {
        if (err instanceof DOMException && err.name === 'AbortError') return;
        console.error('Failed to load messages:', err);
      }
    };

    loadMessages();

    return () => {
      abortController.abort();
    };
  }, [sessionId]);

  // 드롭다운 외부 클릭 시 닫기
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setModelDropdownOpen(false);
      }
    };
    if (modelDropdownOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [modelDropdownOpen]);

  const handleModelChange = useCallback(
    async (modelId: string) => {
      if (modelId === currentModelId || modelSwitching) return;
      setModelSwitching(true);
      setModelDropdownOpen(false);
      try {
        await api.patch(`/chat/sessions/${sessionId}`, { llm_model_id: modelId });
        setCurrentModelId(modelId);
      } catch {
        // Error handled by API wrapper
      } finally {
        setModelSwitching(false);
      }
    },
    [sessionId, currentModelId, modelSwitching],
  );

  const currentModel = models.find((m) => m.id === currentModelId);

  const handleSend = useCallback(
    async (text: string) => {
      addMessage({ role: 'user', content: text });
      setStreaming(true);

      addMessage({ role: 'assistant', content: '' });

      const disconnect = connectSSE(
        `/api/chat/sessions/${sessionId}/messages/stream`,
        { content: text },
        {
          onMessage: (data) => {
            try {
              const parsed = JSON.parse(data);
              if (parsed.content) {
                appendToLastMessage(parsed.content);
              }
            } catch {
              appendToLastMessage(data);
            }
          },
          onError: () => setStreaming(false),
          onClose: () => setStreaming(false),
        },
      );

      return () => disconnect();
    },
    [sessionId, addMessage, appendToLastMessage, setStreaming],
  );

  const handleRegenerate = useCallback(
    async (messageId: number) => {
      setStreaming(true);
      addMessage({ role: 'assistant', content: '' });

      const disconnect = connectSSE(
        `/api/chat/sessions/${sessionId}/messages/${messageId}/regenerate`,
        {},
        {
          onMessage: (data) => {
            try {
              const parsed = JSON.parse(data);
              if (parsed.content) {
                appendToLastMessage(parsed.content);
              }
            } catch {
              appendToLastMessage(data);
            }
          },
          onError: () => setStreaming(false),
          onClose: () => setStreaming(false),
        },
      );

      return () => disconnect();
    },
    [sessionId, addMessage, appendToLastMessage, setStreaming],
  );

  const handleEdit = useCallback(
    async (messageId: number, newContent: string) => {
      try {
        await api.patch(`/chat/sessions/${sessionId}/messages/${messageId}`, {
          content: newContent,
        });
        updateMessage(messageId, newContent);
      } catch {
        // Error handled by API wrapper
      }
    },
    [sessionId, updateMessage],
  );

  return (
    <div className="relative h-screen flex flex-col overflow-hidden">
      {/* 상단 컨트롤 */}
      <div className="absolute top-4 left-4 z-[2] flex items-center gap-2">
        <Link href="/sessions" className="w-10 h-10 rounded-full bg-black/40 flex items-center justify-center text-white hover:bg-black/60 transition-colors no-underline">
          ←
        </Link>
        {personaId && (
          <button
            onClick={() => setReportOpen(true)}
            className="w-10 h-10 rounded-full bg-black/40 flex items-center justify-center text-white hover:bg-black/60 transition-colors border-none cursor-pointer"
            title="신고"
          >
            <Flag size={16} />
          </button>
        )}
      </div>

      {personaId && (
        <div className="absolute top-4 right-4 z-[2]">
          <RelationshipBar personaId={personaId} />
        </div>
      )}
      <Live2DController sessionId={sessionId} />
      <div className="absolute inset-0 z-0">
        <BackgroundLayer imageUrl="/assets/backgrounds/default.jpg" />
        {modelPath && <Live2DCanvas modelPath={modelPath} emotion={currentEmotion} />}
      </div>

      <div className="relative z-[1] flex flex-col h-full bg-[linear-gradient(transparent_0%,rgba(26,26,46,0.85)_40%)]">
        <ChatWindow sessionId={sessionId} personaName={personaName} onRegenerate={handleRegenerate} onEdit={handleEdit} />
        <MessageInput
          onSend={handleSend}
          disabled={isStreaming}
          modelSelector={
            models.length > 0 ? (
              <div ref={dropdownRef} className="relative shrink-0">
                <button
                  type="button"
                  onClick={() => setModelDropdownOpen((prev) => !prev)}
                  disabled={modelSwitching || isStreaming}
                  className={`flex items-center gap-1.5 h-[42px] px-3 rounded-full bg-bg-hover border border-border text-text text-xs hover:bg-bg-hover/80 transition-colors cursor-pointer ${
                    modelSwitching || isStreaming ? 'opacity-50 pointer-events-none' : ''
                  }`}
                >
                  <span className="max-w-[100px] truncate">
                    {currentModel?.display_name ?? '모델 선택'}
                  </span>
                  <ChevronDown size={12} className={`transition-transform ${modelDropdownOpen ? 'rotate-180' : ''}`} />
                </button>

                {modelDropdownOpen && (
                  <div className="absolute bottom-full mb-1 left-0 min-w-[220px] bg-bg-surface border border-border rounded-xl shadow-lg overflow-hidden z-10">
                    {models.map((m) => (
                      <button
                        type="button"
                        key={m.id}
                        onClick={() => handleModelChange(m.id)}
                        className={`w-full text-left px-4 py-2.5 text-sm border-none cursor-pointer transition-colors ${
                          m.id === currentModelId
                            ? 'bg-primary/20 text-primary font-semibold'
                            : 'bg-transparent text-text hover:bg-bg-hover'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-medium">{m.display_name}</span>
                          <span className="flex items-center gap-0.5 text-[11px] text-text-muted">
                            <Gem size={10} />
                            {m.credit_per_1k_tokens}석/1K
                          </span>
                        </div>
                        <div className="text-[11px] text-text-muted">{m.provider}</div>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ) : undefined
          }
        />
      </div>

      {reportOpen && personaId && (
        <ReportModal
          personaId={personaId}
          personaName={personaName || '페르소나'}
          onClose={() => setReportOpen(false)}
        />
      )}
    </div>
  );
}
