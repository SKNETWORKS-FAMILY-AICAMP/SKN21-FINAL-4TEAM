'use client';

import { memo, useCallback, useEffect, useRef, useState } from 'react';
import { RefreshCw, Copy, Pencil, ChevronLeft, ChevronRight, Volume2, Square, ChevronDown } from 'lucide-react';
import { toast } from '@/stores/toastStore';
import { api } from '@/lib/api';

type TTSVoice = { voice_id: string; name: string; language: string | null };

const TTS_VOICE_KEY = 'tts_selected_voice';

type Props = {
  messageId: number;
  role: 'user' | 'assistant' | 'system';
  content: string;
  siblingCount?: number;
  siblingIndex?: number;
  isStreaming?: boolean;
  onRegenerate?: (messageId: number) => void;
  onEdit?: (messageId: number) => void;
  onNavigateSibling?: (messageId: number, direction: 'prev' | 'next') => void;
};

export const MessageActions = memo(function MessageActions({
  messageId,
  role,
  content,
  siblingCount = 1,
  siblingIndex = 0,
  isStreaming,
  onRegenerate,
  onEdit,
  onNavigateSibling,
}: Props) {
  const [ttsLoading, setTtsLoading] = useState(false);
  const [ttsPlaying, setTtsPlaying] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [voices, setVoices] = useState<TTSVoice[]>([]);
  const [selectedVoice, setSelectedVoice] = useState<string>(() =>
    typeof window !== 'undefined' ? (localStorage.getItem(TTS_VOICE_KEY) ?? '') : '',
  );
  const [showVoiceMenu, setShowVoiceMenu] = useState(false);
  const voiceMenuRef = useRef<HTMLDivElement | null>(null);

  // 음성 메뉴 외부 클릭 시 닫기
  useEffect(() => {
    if (!showVoiceMenu) return;
    const handler = (e: MouseEvent) => {
      if (voiceMenuRef.current && !voiceMenuRef.current.contains(e.target as Node)) {
        setShowVoiceMenu(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showVoiceMenu]);

  const openVoiceMenu = async () => {
    if (voices.length === 0) {
      try {
        const res = await api.get<{ voices: TTSVoice[] }>('/tts/voices');
        setVoices(res.voices);
      } catch {
        toast.error('음성 목록을 불러오지 못했습니다');
        return;
      }
    }
    setShowVoiceMenu((v) => !v);
  };

  const selectVoice = (voiceId: string) => {
    setSelectedVoice(voiceId);
    localStorage.setItem(TTS_VOICE_KEY, voiceId);
    setShowVoiceMenu(false);
  };

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content);
      toast.success('복사됨');
    } catch {
      toast.error('복사 실패');
    }
  };

  const handleTTS = useCallback(async () => {
    // 재생 중이면 정지
    if (ttsPlaying && audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      setTtsPlaying(false);
      return;
    }

    setTtsLoading(true);
    try {
      const result = await api.post<{ audio_url: string }>('/tts/synthesize-message', {
        message_id: messageId,
        ...(selectedVoice ? { voice: selectedVoice } : {}),
      });

      const audio = new Audio(result.audio_url);
      audioRef.current = audio;

      audio.onended = () => setTtsPlaying(false);
      audio.onerror = () => {
        setTtsPlaying(false);
        toast.error('오디오 재생 실패');
      };

      await audio.play();
      setTtsPlaying(true);
    } catch {
      toast.error('TTS 합성 실패');
    } finally {
      setTtsLoading(false);
    }
  }, [messageId, ttsPlaying]);

  return (
    <div className="flex items-center gap-1 mt-1 opacity-0 group-hover:opacity-100 transition-opacity">
      {role === 'assistant' && onRegenerate && !isStreaming && (
        <button
          onClick={() => onRegenerate(messageId)}
          className="p-1 rounded hover:bg-bg-hover text-text-muted hover:text-text transition-colors"
          title="재생성"
          aria-label="메시지 재생성"
        >
          <RefreshCw size={13} />
        </button>
      )}
      {role === 'user' && onEdit && !isStreaming && (
        <button
          onClick={() => onEdit(messageId)}
          className="p-1 rounded hover:bg-bg-hover text-text-muted hover:text-text transition-colors"
          title="수정"
          aria-label="메시지 수정"
        >
          <Pencil size={13} />
        </button>
      )}
      <button
        onClick={handleCopy}
        className="p-1 rounded hover:bg-bg-hover text-text-muted hover:text-text transition-colors"
        title="복사"
        aria-label="메시지 복사"
      >
        <Copy size={13} />
      </button>
      {role === 'assistant' && !isStreaming && (
        <div className="relative flex items-center" ref={voiceMenuRef}>
          <button
            onClick={handleTTS}
            disabled={ttsLoading}
            className={`p-1 rounded-l transition-colors ${
              ttsPlaying
                ? 'text-primary bg-primary/10'
                : ttsLoading
                  ? 'text-text-muted opacity-50 cursor-wait'
                  : 'hover:bg-bg-hover text-text-muted hover:text-text'
            }`}
            title={ttsPlaying ? 'TTS 정지' : selectedVoice ? `TTS 재생 (${selectedVoice})` : 'TTS 음성 재생'}
            aria-label={ttsPlaying ? 'TTS 음성 정지' : 'TTS 음성 재생'}
          >
            {ttsPlaying ? <Square size={13} /> : <Volume2 size={13} />}
          </button>
          <button
            onClick={openVoiceMenu}
            className="p-0.5 rounded-r hover:bg-bg-hover text-text-muted hover:text-text transition-colors"
            title="음성 선택"
            aria-label="TTS 음성 선택"
          >
            <ChevronDown size={10} />
          </button>
          {showVoiceMenu && voices.length > 0 && (
            <div className="absolute bottom-full left-0 mb-1 w-48 bg-bg-surface border border-border rounded-lg shadow-lg z-50 py-1">
              <p className="px-3 py-1 text-[10px] text-text-muted font-semibold uppercase">음성 선택</p>
              {voices.map((v) => (
                <button
                  key={v.voice_id}
                  onClick={() => selectVoice(v.voice_id)}
                  className={`w-full text-left px-3 py-1.5 text-xs transition-colors ${
                    selectedVoice === v.voice_id
                      ? 'text-primary bg-primary/5'
                      : 'text-text hover:bg-bg-hover'
                  }`}
                >
                  {v.name}
                  {v.language && <span className="text-text-muted ml-1">({v.language})</span>}
                </button>
              ))}
              {selectedVoice && (
                <button
                  onClick={() => selectVoice('')}
                  className="w-full text-left px-3 py-1.5 text-xs text-text-muted hover:bg-bg-hover border-t border-border transition-colors"
                >
                  기본값 사용
                </button>
              )}
            </div>
          )}
        </div>
      )}
      {siblingCount > 1 && (
        <div className="flex items-center gap-0.5 ml-1 text-[11px] text-text-muted">
          <button
            onClick={() => onNavigateSibling?.(messageId, 'prev')}
            disabled={siblingIndex === 0}
            className="p-0.5 rounded hover:bg-bg-hover disabled:opacity-30 transition-colors"
            aria-label="이전 응답"
          >
            <ChevronLeft size={12} />
          </button>
          <span>{siblingIndex + 1}/{siblingCount}</span>
          <button
            onClick={() => onNavigateSibling?.(messageId, 'next')}
            disabled={siblingIndex === siblingCount - 1}
            className="p-0.5 rounded hover:bg-bg-hover disabled:opacity-30 transition-colors"
            aria-label="다음 응답"
          >
            <ChevronRight size={12} />
          </button>
        </div>
      )}
    </div>
  );
});
