'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useDebateAgentStore } from '@/stores/debateAgentStore';
import type { CreateAgentPayload } from '@/stores/debateAgentStore';
import { useToastStore } from '@/stores/toastStore';

type Props = {
  initialData?: Partial<CreateAgentPayload> & { id?: string };
  isEdit?: boolean;
};

const PROVIDERS = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'google', label: 'Google' },
  { value: 'runpod', label: 'RunPod' },
  { value: 'local', label: '로컬 에이전트' },
];

export function AgentForm({ initialData, isEdit }: Props) {
  const router = useRouter();
  const { createAgent, updateAgent } = useDebateAgentStore();
  const addToast = useToastStore((s) => s.addToast);
  const [submitting, setSubmitting] = useState(false);

  const [form, setForm] = useState({
    name: initialData?.name || '',
    description: initialData?.description || '',
    provider: initialData?.provider || 'openai',
    model_id: initialData?.model_id || '',
    api_key: '',
    system_prompt: initialData?.system_prompt || '',
    version_tag: '',
  });

  const isLocal = form.provider === 'local';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name || !form.system_prompt) return;
    if (!isLocal && !form.model_id) return;
    if (!isEdit && !isLocal && !form.api_key) return;

    setSubmitting(true);
    try {
      const payload: Record<string, unknown> = { ...form };
      if (!form.api_key || isLocal) delete payload.api_key;
      if (isLocal && !form.model_id) payload.model_id = 'custom';

      if (isEdit && initialData?.id) {
        await updateAgent(initialData.id, payload);
        addToast('에이전트가 수정되었습니다.', 'success');
      } else {
        await createAgent(payload as CreateAgentPayload);
        addToast('에이전트가 생성되었습니다.', 'success');
      }
      router.push('/debate/agents');
    } catch {
      addToast('에이전트 저장에 실패했습니다.', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4 max-w-[600px]">
      <div>
        <label className="text-sm font-semibold text-text block mb-1">에이전트 이름 *</label>
        <input
          type="text"
          value={form.name}
          onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
          className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm text-text"
          placeholder="My Debate Agent"
          maxLength={100}
          required
        />
      </div>

      <div>
        <label className="text-sm font-semibold text-text block mb-1">설명</label>
        <input
          type="text"
          value={form.description}
          onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
          className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm text-text"
          placeholder="에이전트 설명"
        />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-sm font-semibold text-text block mb-1">LLM Provider *</label>
          <select
            value={form.provider}
            onChange={(e) => {
              const provider = e.target.value;
              setForm((f) => ({
                ...f,
                provider,
                model_id: provider === 'local' ? f.model_id || 'custom' : f.model_id,
                api_key: provider === 'local' ? '' : f.api_key,
              }));
            }}
            className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm text-text"
          >
            {PROVIDERS.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-sm font-semibold text-text block mb-1">
            Model ID {isLocal ? '' : '*'}
          </label>
          <input
            type="text"
            value={form.model_id}
            onChange={(e) => setForm((f) => ({ ...f, model_id: e.target.value }))}
            className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm text-text"
            placeholder={isLocal ? 'custom' : 'gpt-4o'}
            required={!isLocal}
          />
        </div>
      </div>

      {isLocal ? (
        <div className="rounded-lg border border-primary/20 bg-primary/5 p-3">
          <p className="text-sm font-semibold text-text mb-1">WebSocket 연결 안내</p>
          <p className="text-xs text-text-muted">
            로컬 에이전트는 API 키가 필요 없습니다. 에이전트 생성 후, WebSocket으로 플랫폼에 접속하여
            턴 요청에 응답하세요. 연결 방법은 에이전트 상세 페이지에서 확인할 수 있습니다.
          </p>
        </div>
      ) : (
        <div>
          <label className="text-sm font-semibold text-text block mb-1">
            API Key {isEdit ? '(변경 시에만 입력)' : '*'}
          </label>
          <input
            type="password"
            value={form.api_key}
            onChange={(e) => setForm((f) => ({ ...f, api_key: e.target.value }))}
            className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm text-text"
            placeholder="sk-..."
            required={!isEdit}
          />
          <p className="text-[11px] text-text-muted mt-1">
            API 키는 서버에 암호화되어 저장됩니다. 토론 시에만 복호화하여 사용합니다.
          </p>
        </div>
      )}

      <div>
        <label className="text-sm font-semibold text-text block mb-1">시스템 프롬프트 *</label>
        <textarea
          value={form.system_prompt}
          onChange={(e) => setForm((f) => ({ ...f, system_prompt: e.target.value }))}
          className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm text-text min-h-[200px] resize-y font-mono"
          placeholder="에이전트의 토론 전략과 성격을 정의하세요..."
          required
        />
      </div>

      <div>
        <label className="text-sm font-semibold text-text block mb-1">버전 태그</label>
        <input
          type="text"
          value={form.version_tag}
          onChange={(e) => setForm((f) => ({ ...f, version_tag: e.target.value }))}
          className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm text-text"
          placeholder="v1.0"
          maxLength={50}
        />
      </div>

      <button
        type="submit"
        disabled={submitting}
        className="mt-2 px-6 py-2.5 bg-primary text-white font-semibold rounded-lg text-sm
          hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {submitting ? '저장 중...' : isEdit ? '에이전트 수정' : '에이전트 생성'}
      </button>
    </form>
  );
}
