/** 페르소나 생성/편집 폼. Zod 검증, Live2D 모델 선택, 연령등급 설정 포함. */
'use client';

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Upload, Link, X, Loader2 } from 'lucide-react';
import { api } from '@/lib/api';
import { useUserStore } from '@/stores/userStore';
import { TagChips } from '@/components/persona/TagChips';
import { CATEGORIES } from '@/constants/categories';

const personaSchema = z.object({
  display_name: z.string().min(1, '이름을 입력하세요').max(50),
  system_prompt: z.string().min(1, '성격/설정을 입력하세요').max(4000),
  style_rules: z.string().max(2000).optional(),
  catchphrases: z.string().max(1000).optional(),
  description: z.string().max(500).optional(),
  greeting_message: z.string().max(2000).optional(),
  scenario: z.string().max(2000).optional(),
  category: z.string().optional(),
  age_rating: z.enum(['all', '15+', '18+']),
  visibility: z.enum(['private', 'public', 'unlisted']),
  is_anonymous: z.boolean().optional(),
  live2d_model_id: z.string().optional(),
  background_image_url: z.string().optional(),
});

type PersonaFormData = z.infer<typeof personaSchema>;

type PersonaSubmitData = PersonaFormData & { tags: string[] };

type Props = {
  personaId?: string;
  onSubmit: (data: PersonaSubmitData) => void;
};

export function PersonaForm({ personaId, onSubmit }: Props) {
  const { isAdultVerified } = useUserStore();
  const [loading, setLoading] = useState(false);
  const [tags, setTags] = useState<string[]>([]);
  const [uploadMode, setUploadMode] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string>('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const {
    register,
    handleSubmit,
    reset,
    watch,
    setValue,
    formState: { errors },
  } = useForm<PersonaFormData>({
    resolver: zodResolver(personaSchema),
    defaultValues: {
      display_name: '',
      system_prompt: '',
      style_rules: '',
      catchphrases: '',
      description: '',
      greeting_message: '',
      scenario: '',
      category: '',
      age_rating: 'all',
      visibility: 'private',
      is_anonymous: false,
    },
  });

  const selectedRating = watch('age_rating');
  const systemPromptValue = watch('system_prompt');
  const backgroundImageUrl = watch('background_image_url');
  const selectedVisibility = watch('visibility');

  useEffect(() => {
    if (!personaId) return;
    setLoading(true);
    api
      .get<Record<string, unknown>>(`/personas/${personaId}`)
      .then((data) => {
        const formData = {
          ...data,
          style_rules: data.style_rules && typeof data.style_rules === 'object'
            ? (data.style_rules as { rules?: string[] }).rules?.join('\n') ?? ''
            : '',
          catchphrases: Array.isArray(data.catchphrases)
            ? (data.catchphrases as string[]).join('\n')
            : '',
          description: (data.description as string) ?? '',
          greeting_message: (data.greeting_message as string) ?? '',
          scenario: (data.scenario as string) ?? '',
          category: (data.category as string) ?? '',
        };
        if (Array.isArray(data.tags)) {
          setTags(data.tags as string[]);
        }
        // 기존 배경 이미지가 있으면 미리보기 설정
        if (data.background_image_url) {
          setPreviewUrl(data.background_image_url as string);
          setUploadMode(false);
        }
        reset(formData as PersonaFormData);
      })
      .finally(() => setLoading(false));
  }, [personaId, reset]);

  const handleFileUpload = useCallback(async (file: File) => {
    if (file.size > 5 * 1024 * 1024) {
      alert('파일 크기는 5MB 이하여야 합니다.');
      return;
    }
    if (!file.type.startsWith('image/')) {
      alert('이미지 파일만 업로드 가능합니다.');
      return;
    }
    setUploading(true);
    try {
      const result = await api.upload<{ url: string }>('/uploads/image', file);
      setValue('background_image_url', result.url);
      setPreviewUrl(result.url);
    } catch {
      alert('이미지 업로드에 실패했습니다.');
    } finally {
      setUploading(false);
    }
  }, [setValue]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) handleFileUpload(file);
  }, [handleFileUpload]);

  const handleRemoveImage = useCallback(() => {
    setValue('background_image_url', '');
    setPreviewUrl('');
    if (fileInputRef.current) fileInputRef.current.value = '';
  }, [setValue]);

  if (loading) return <div className="text-center p-10 text-text-muted">불러오는 중...</div>;

  return (
    <form onSubmit={handleSubmit((data) => onSubmit({ ...data, tags }))} className="flex flex-col gap-5">
      <div className="flex flex-col gap-1">
        <label className="text-[13px] font-semibold text-text-label">캐릭터 이름</label>
        <input
          {...register('display_name')}
          className="py-2.5 px-3 border border-border-input rounded-lg text-sm outline-none bg-bg-input text-text"
          placeholder="예: 미니"
        />
        {errors.display_name && (
          <span className="text-danger-text text-xs">{errors.display_name.message}</span>
        )}
      </div>

      <div className="flex flex-col gap-1">
        <label className="text-[13px] font-semibold text-text-label">성격 / 시스템 프롬프트</label>
        <textarea
          {...register('system_prompt')}
          className="py-2.5 px-3 border border-border-input rounded-lg text-sm outline-none font-[inherit] resize-y bg-bg-input text-text"
          rows={6}
          placeholder="캐릭터의 성격, 배경, 대화 스타일을 자유롭게 적어주세요..."
        />
        <div className="flex justify-between items-center">
          {errors.system_prompt ? (
            <span className="text-danger-text text-xs">{errors.system_prompt.message}</span>
          ) : (
            <span />
          )}
          <span className="text-xs text-text-muted">
            {(systemPromptValue ?? '').length} / 4,000
          </span>
        </div>
      </div>

      <div className="flex flex-col gap-1">
        <label className="text-[13px] font-semibold text-text-label">말투 규칙 (선택)</label>
        <textarea
          {...register('style_rules')}
          className="py-2.5 px-3 border border-border-input rounded-lg text-sm outline-none font-[inherit] resize-y bg-bg-input text-text"
          rows={3}
          placeholder="예: 반말 사용, ~냥 어미, 이모티콘 자주 사용"
        />
      </div>

      <div className="flex flex-col gap-1">
        <label className="text-[13px] font-semibold text-text-label">
          캐치프레이즈 (선택, 줄바꿈으로 구분)
        </label>
        <textarea
          {...register('catchphrases')}
          className="py-2.5 px-3 border border-border-input rounded-lg text-sm outline-none font-[inherit] resize-y bg-bg-input text-text"
          rows={2}
          placeholder="자주 쓰는 표현들을 한 줄씩 입력..."
        />
      </div>

      <div className="flex flex-col gap-1">
        <label className="text-[13px] font-semibold text-text-label">캐릭터 소개 (선택)</label>
        <textarea
          {...register('description')}
          className="py-2.5 px-3 border border-border-input rounded-lg text-sm outline-none font-[inherit] resize-y bg-bg-input text-text"
          rows={2}
          placeholder="카드에 표시될 짧은 소개글"
        />
      </div>

      <div className="flex flex-col gap-1">
        <label className="text-[13px] font-semibold text-text-label">첫 인사말 (선택)</label>
        <textarea
          {...register('greeting_message')}
          className="py-2.5 px-3 border border-border-input rounded-lg text-sm outline-none font-[inherit] resize-y bg-bg-input text-text"
          rows={3}
          placeholder="세션 시작 시 자동으로 보내는 첫 메시지"
        />
      </div>

      <div className="flex flex-col gap-1">
        <label className="text-[13px] font-semibold text-text-label">시나리오 (선택)</label>
        <textarea
          {...register('scenario')}
          className="py-2.5 px-3 border border-border-input rounded-lg text-sm outline-none font-[inherit] resize-y bg-bg-input text-text"
          rows={3}
          placeholder="대화의 배경 상황 설정"
        />
      </div>

      <div className="flex flex-col gap-1">
        <label className="text-[13px] font-semibold text-text-label">카테고리 (선택)</label>
        <select
          {...register('category')}
          className="py-2.5 px-3 border border-border-input rounded-lg text-sm outline-none bg-bg-surface text-text"
        >
          <option value="">선택 안 함</option>
          {CATEGORIES.map((c) => (
            <option key={c.id} value={c.id}>{c.label}</option>
          ))}
        </select>
      </div>

      <div className="flex flex-col gap-1">
        <label className="text-[13px] font-semibold text-text-label">태그 (선택)</label>
        <div className="py-2 px-3 border border-border-input rounded-lg bg-bg-input min-h-[36px]">
          <TagChips tags={tags} editable onChange={setTags} />
        </div>
        <span className="text-xs text-text-muted">Enter 또는 쉼표로 태그 추가 (최대 10개)</span>
      </div>

      <div className="flex flex-col sm:flex-row gap-4">
        <div className="flex flex-col gap-1 flex-1">
          <label className="text-[13px] font-semibold text-text-label">연령등급</label>
          <select
            {...register('age_rating')}
            className="py-2.5 px-3 border border-border-input rounded-lg text-sm outline-none bg-bg-surface text-text"
          >
            <option value="all">전체</option>
            <option value="15+">15+</option>
            <option value="18+" disabled={!isAdultVerified()}>
              18+ {!isAdultVerified() ? '(성인인증 필요)' : ''}
            </option>
          </select>
          {selectedRating === '18+' && !isAdultVerified() && (
            <span className="text-danger-text text-xs">
              18+ 등급은 성인인증 후 사용 가능합니다
            </span>
          )}
        </div>

        <div className="flex flex-col gap-1 flex-1">
          <label className="text-[13px] font-semibold text-text-label">공개 범위</label>
          <select
            {...register('visibility')}
            className="py-2.5 px-3 border border-border-input rounded-lg text-sm outline-none bg-bg-surface text-text"
          >
            <option value="private">비공개 (나만)</option>
            <option value="unlisted">일부 공개</option>
            <option value="public">전체 공개</option>
          </select>
        </div>
      </div>

      {selectedVisibility !== 'private' && (
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            {...register('is_anonymous')}
            className="w-4 h-4 rounded border-border accent-primary"
          />
          <span className="text-sm text-text-secondary">익명으로 공개 (닉네임 비공개)</span>
        </label>
      )}

      <div className="flex flex-col gap-1">
        <div className="flex items-center justify-between">
          <label className="text-[13px] font-semibold text-text-label">
            배경 이미지 (선택)
          </label>
          <button
            type="button"
            onClick={() => setUploadMode(!uploadMode)}
            className="flex items-center gap-1 text-xs text-text-muted hover:text-primary transition-colors"
          >
            {uploadMode ? <><Link size={12} /> URL 직접 입력</> : <><Upload size={12} /> 파일 업로드</>}
          </button>
        </div>

        {uploadMode ? (
          <div>
            <div
              onDragOver={(e) => e.preventDefault()}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className="flex flex-col items-center justify-center gap-2 py-6 px-3 border-2 border-dashed border-border-input rounded-lg cursor-pointer hover:border-primary/50 transition-colors bg-bg-input"
            >
              {uploading ? (
                <Loader2 size={24} className="text-primary animate-spin" />
              ) : (
                <Upload size={24} className="text-text-muted" />
              )}
              <span className="text-xs text-text-muted">
                {uploading ? '업로드 중...' : '클릭 또는 드래그하여 이미지 업로드 (최대 5MB)'}
              </span>
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp,image/gif"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) handleFileUpload(file);
              }}
            />
          </div>
        ) : (
          <input
            {...register('background_image_url')}
            className="py-2.5 px-3 border border-border-input rounded-lg text-sm outline-none bg-bg-input text-text"
            placeholder="https://..."
            onChange={(e) => {
              register('background_image_url').onChange(e);
              setPreviewUrl(e.target.value);
            }}
          />
        )}

        {/* 미리보기 */}
        {previewUrl && (
          <div className="relative mt-2">
            <img
              src={previewUrl}
              alt="배경 미리보기"
              className="w-full h-32 object-cover rounded-lg border border-border"
              onError={() => setPreviewUrl('')}
            />
            <button
              type="button"
              onClick={handleRemoveImage}
              className="absolute top-1.5 right-1.5 p-1 rounded-full bg-black/60 text-white hover:bg-black/80 transition-colors"
            >
              <X size={14} />
            </button>
          </div>
        )}

        {/* hidden field for form data */}
        {uploadMode && <input type="hidden" {...register('background_image_url')} />}
      </div>

      <button
        type="submit"
        className="py-3 px-3 border-none rounded-lg bg-primary text-white text-[15px] font-semibold cursor-pointer mt-2"
      >
        {personaId ? '수정하기' : '생성하기'}
      </button>
    </form>
  );
}
