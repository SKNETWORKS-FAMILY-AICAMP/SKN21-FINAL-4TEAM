'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useDebateAgentStore } from '@/stores/debateAgentStore';
import type { AgentTemplate, CreateAgentPayload } from '@/stores/debateAgentStore';
import { useToastStore } from '@/stores/toastStore';
import { TemplateCard } from './TemplateCard';
import { TemplateCustomizer } from './TemplateCustomizer';

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

// 편집 모드에서의 단계
type EditMode = 'byok' | 'local' | 'template';

export function AgentForm({ initialData, isEdit }: Props) {
  const router = useRouter();
  const { createAgent, updateAgent, templates, fetchTemplates } = useDebateAgentStore();
  const addToast = useToastStore((s) => s.addToast);

  const [step, setStep] = useState<1 | 2>(isEdit ? 2 : 1);
  const [submitting, setSubmitting] = useState(false);

  // 선택된 템플릿 (null이면 BYOK/로컬 모드)
  const [selectedTemplate, setSelectedTemplate] = useState<AgentTemplate | null>(null);
  const [customizations, setCustomizations] = useState<Record<string, unknown>>({});
  const [enableFreeText, setEnableFreeText] = useState(false);

  // 기본 에이전트 폼 상태
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

  // 편집 모드 판단 (template_id 있으면 template 모드)
  const editMode: EditMode = isEdit
    ? initialData?.template_id
      ? 'template'
      : isLocal
        ? 'local'
        : 'byok'
    : 'byok'; // 신규 생성 시 단계1에서 결정됨

  useEffect(() => {
    fetchTemplates();
  }, [fetchTemplates]);

  // 템플릿 선택 시 해당 템플릿의 기본값으로 customizations 초기화
  const handleSelectTemplate = (template: AgentTemplate) => {
    setSelectedTemplate(template);
    setCustomizations({ ...template.default_values });
  };

  // 커스터마이징 단일 값 변경
  const handleCustomizationChange = (key: string, value: unknown) => {
    setCustomizations((prev) => ({ ...prev, [key]: value }));
  };

  // Step 1 → Step 2 진행 (템플릿 or BYOK/로컬 선택 완료)
  const handleProceedWithTemplate = () => {
    if (!selectedTemplate) return;
    setStep(2);
  };

  const handleProceedWithoutTemplate = () => {
    setSelectedTemplate(null);
    setStep(2);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name) return;

    const useTemplate = selectedTemplate !== null || (isEdit && editMode === 'template');

    // 유효성 검사
    if (!useTemplate && !isLocal) {
      if (!form.system_prompt) return;
      if (!form.model_id) return;
      if (!isEdit && !form.api_key) return;
    }

    setSubmitting(true);
    try {
      const payload: Record<string, unknown> = {
        name: form.name,
        description: form.description || undefined,
        provider: form.provider,
        model_id: form.model_id || (isLocal ? 'custom' : undefined),
        version_tag: form.version_tag || undefined,
      };

      if (useTemplate && selectedTemplate) {
        payload.template_id = selectedTemplate.id;
        payload.customizations = customizations;
        payload.enable_free_text = enableFreeText;
        if (form.api_key) payload.api_key = form.api_key;
      } else if (isLocal) {
        // 로컬 에이전트 — API 키 불필요
        if (form.system_prompt) payload.system_prompt = form.system_prompt;
      } else {
        // BYOK
        if (form.api_key) payload.api_key = form.api_key;
        payload.system_prompt = form.system_prompt;
      }

      if (isEdit && initialData?.id) {
        // 편집: template 모드면 customizations만 전달 가능
        const updatePayload = useTemplate && editMode === 'template'
          ? {
              name: form.name,
              description: form.description || undefined,
              customizations,
              enable_free_text: enableFreeText,
              version_tag: form.version_tag || undefined,
              ...(form.api_key ? { api_key: form.api_key } : {}),
            }
          : payload;
        await updateAgent(initialData.id, updatePayload);
        addToast('success', '에이전트가 수정되었습니다.');
        router.push(`/debate/agents/${initialData.id}`);
      } else {
        const created = await createAgent(payload as CreateAgentPayload);
        addToast('success', '에이전트가 생성되었습니다.');
        router.push(`/debate/agents/${created.id}`);
      }
    } catch {
      addToast('error', '에이전트 저장에 실패했습니다.');
    } finally {
      setSubmitting(false);
    }
  };

  // -------------------------------------------------------------------------
  // Step 1: 템플릿 선택 (신규 생성 전용)
  // -------------------------------------------------------------------------
  if (!isEdit && step === 1) {
    return (
      <div className="flex flex-col gap-6 max-w-[800px]">
        <div>
          <h2 className="text-base font-semibold text-text mb-1">에이전트 템플릿 선택</h2>
          <p className="text-sm text-text-muted">
            플랫폼이 제공하는 템플릿을 선택하거나, 직접 시스템 프롬프트를 작성할 수 있습니다.
          </p>
        </div>

        {/* 템플릿 카드 그리드 */}
        {templates.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {templates.map((t) => (
              <TemplateCard
                key={t.id}
                template={t}
                selected={selectedTemplate?.id === t.id}
                onSelect={handleSelectTemplate}
              />
            ))}
          </div>
        ) : (
          <p className="text-sm text-text-muted">템플릿을 불러오는 중...</p>
        )}

        <div className="flex gap-3 mt-2">
          {selectedTemplate && (
            <button
              type="button"
              onClick={handleProceedWithTemplate}
              className="px-6 py-2.5 bg-primary text-white font-semibold rounded-lg text-sm
                hover:bg-primary/90 transition-colors"
            >
              선택한 템플릿으로 계속 →
            </button>
          )}
          <button
            type="button"
            onClick={handleProceedWithoutTemplate}
            className="px-6 py-2.5 border border-border text-text font-semibold rounded-lg text-sm
              hover:bg-border/20 transition-colors"
          >
            직접 프롬프트 작성
          </button>
        </div>
      </div>
    );
  }

  // -------------------------------------------------------------------------
  // Step 2 (또는 편집 모드): 에이전트 설정 폼
  // -------------------------------------------------------------------------
  const useTemplateForm = selectedTemplate !== null || (isEdit && editMode === 'template');

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4 max-w-[600px]">
      {/* 뒤로 가기 (신규 생성 + Step 2인 경우) */}
      {!isEdit && (
        <button
          type="button"
          onClick={() => setStep(1)}
          className="self-start text-xs text-text-muted hover:text-primary flex items-center gap-1"
        >
          ← 템플릿 다시 선택
        </button>
      )}

      {/* 선택된 템플릿 표시 */}
      {useTemplateForm && selectedTemplate && (
        <div className="rounded-lg border border-primary/30 bg-primary/5 px-3 py-2">
          <p className="text-xs text-text-muted">선택한 템플릿</p>
          <p className="text-sm font-semibold text-primary">{selectedTemplate.display_name}</p>
        </div>
      )}

      {/* 기본 정보 */}
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

      {/* 템플릿 커스터마이징 */}
      {useTemplateForm && selectedTemplate && (
        <div className="rounded-lg border border-border p-4 bg-bg">
          <TemplateCustomizer
            template={selectedTemplate}
            values={customizations}
            enableFreeText={enableFreeText}
            onChange={handleCustomizationChange}
            onToggleFreeText={setEnableFreeText}
          />
        </div>
      )}

      {/* LLM 설정 */}
      <div className="mt-1">
        <p className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-3">
          LLM 설정
        </p>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-sm font-semibold text-text block mb-1">Provider *</label>
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
      </div>

      {isLocal ? (
        <div className="rounded-lg border border-primary/20 bg-primary/5 p-3">
          <p className="text-sm font-semibold text-text mb-1">로컬 에이전트 안내</p>
          <p className="text-xs text-text-muted">
            로컬 에이전트는 내 PC에서 LLM을 직접 구동합니다. API 키와 시스템 프롬프트는 로컬에서
            관리하므로 플랫폼에 입력할 필요가 없습니다. 에이전트 생성 후 상세 페이지에서 WebSocket
            연결 정보를 확인하세요.
          </p>
        </div>
      ) : (
        <>
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
              required={!isEdit && !useTemplateForm}
            />
            <p className="text-[11px] text-text-muted mt-1">
              API 키는 서버에 암호화되어 저장됩니다. 토론 시에만 복호화하여 사용합니다.
            </p>
          </div>

          {/* BYOK 모드에서만 시스템 프롬프트 직접 입력 */}
          {!useTemplateForm && (
            <div>
              <label className="text-sm font-semibold text-text block mb-1">
                시스템 프롬프트 *
              </label>
              <textarea
                value={form.system_prompt}
                onChange={(e) => setForm((f) => ({ ...f, system_prompt: e.target.value }))}
                className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm text-text min-h-[200px] resize-y font-mono"
                placeholder="에이전트의 토론 전략과 성격을 정의하세요..."
                required
              />
            </div>
          )}
        </>
      )}

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
