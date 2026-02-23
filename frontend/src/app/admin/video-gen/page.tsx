'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '@/lib/api';
import { StatCard } from '@/components/admin/StatCard';
import { DataTable } from '@/components/admin/DataTable';
import { SkeletonStat } from '@/components/ui/Skeleton';
import { toast } from '@/stores/toastStore';
import {
  Video,
  Clock,
  CheckCircle,
  XCircle,
  Upload,
  X,
  Play,
  Download,
  Loader2,
  Ban,
} from 'lucide-react';

// ── Types ──

type Keyframe = {
  image_url: string;
  frame_index: number;
  strength: number;
};

type VideoGenJob = {
  id: string;
  prompt: string;
  negative_prompt: string | null;
  width: number;
  height: number;
  num_frames: number;
  frame_rate: number;
  num_inference_steps: number;
  guidance_scale: number;
  seed: number | null;
  model_variant: string;
  keyframes: Keyframe[];
  status: string;
  runpod_job_id: string | null;
  result_video_url: string | null;
  result_metadata: Record<string, unknown> | null;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
};

type VideoGenListResponse = {
  items: VideoGenJob[];
  total: number;
};

// ── Constants ──

const RESOLUTION_PRESETS = [
  { label: '768x512 (SD)', width: 768, height: 512 },
  { label: '1280x720 (HD)', width: 1280, height: 720 },
  { label: '512x768 (세로)', width: 512, height: 768 },
  { label: '720x1280 (세로HD)', width: 720, height: 1280 },
];

const DURATION_PRESETS = [
  { label: '~1초 (25f)', frames: 25 },
  { label: '~2초 (49f)', frames: 49 },
  { label: '~4초 (97f)', frames: 97 },
  { label: '~8초 (193f)', frames: 193 },
];

const VARIANT_OPTIONS = [
  { value: 'dev', label: 'Dev (고품질, 40스텝)' },
  { value: 'distilled', label: 'Distilled (빠름, 8스텝)' },
];

const STATUS_STYLES: Record<string, { bg: string; text: string }> = {
  pending: { bg: 'bg-text-muted/20', text: 'text-text-muted' },
  submitted: { bg: 'bg-blue-500/20', text: 'text-blue-400' },
  processing: { bg: 'bg-yellow-500/20', text: 'text-yellow-400' },
  completed: { bg: 'bg-green-500/20', text: 'text-green-400' },
  failed: { bg: 'bg-red-500/20', text: 'text-red-400' },
  cancelled: { bg: 'bg-text-muted/20', text: 'text-text-muted' },
};

// ── Helpers ──

function StatusBadge({ status }: { status: string }) {
  const style = STATUS_STYLES[status] ?? STATUS_STYLES.pending;
  return (
    <span className={`px-2 py-0.5 rounded-badge text-xs font-semibold ${style.bg} ${style.text}`}>
      {status}
    </span>
  );
}

function formatDate(iso: string | null) {
  if (!iso) return '-';
  return new Date(iso).toLocaleString('ko-KR', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

// ── KeyframeSlot ──

type KeyframeSlotProps = {
  index: number;
  kf: { file: File | null; url: string; frame_index: number; strength: number } | null;
  maxFrames: number;
  onUpload: (index: number, file: File) => void;
  onRemove: (index: number) => void;
  onChange: (index: number, field: 'frame_index' | 'strength', value: number) => void;
};

function KeyframeSlot({ index, kf, maxFrames, onUpload, onRemove, onChange }: KeyframeSlotProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <div className="card flex flex-col items-center gap-2 p-3 min-w-[140px]">
      {kf ? (
        <>
          <div className="relative w-full aspect-video rounded-lg overflow-hidden bg-bg">
            <img
              src={kf.url}
              alt={`키프레임 ${index + 1}`}
              className="w-full h-full object-cover"
            />
            <button
              type="button"
              onClick={() => onRemove(index)}
              className="absolute top-1 right-1 w-5 h-5 rounded-full bg-black/60 text-white flex items-center justify-center border-none cursor-pointer"
            >
              <X size={12} />
            </button>
          </div>
          <label className="text-xs text-text-muted w-full">
            프레임 위치
            <input
              type="number"
              min={0}
              max={maxFrames - 1}
              value={kf.frame_index}
              onChange={(e) => onChange(index, 'frame_index', Number(e.target.value))}
              className="input w-full mt-0.5 text-xs"
            />
          </label>
          <label className="text-xs text-text-muted w-full">
            강도 ({kf.strength.toFixed(1)})
            <input
              type="range"
              min={0}
              max={1}
              step={0.1}
              value={kf.strength}
              onChange={(e) => onChange(index, 'strength', Number(e.target.value))}
              className="w-full mt-0.5 accent-primary"
            />
          </label>
        </>
      ) : (
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="w-full aspect-video rounded-lg border-2 border-dashed border-border-input flex flex-col items-center justify-center gap-1 bg-transparent cursor-pointer text-text-muted hover:border-primary hover:text-primary transition-colors"
        >
          <Upload size={20} />
          <span className="text-xs">이미지 {index + 1}</span>
        </button>
      )}
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onUpload(index, file);
          e.target.value = '';
        }}
      />
    </div>
  );
}

// ── Detail Modal ──

function JobDetailModal({ job, onClose }: { job: VideoGenJob; onClose: () => void }) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal-content max-w-2xl w-full text-left max-h-[85vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-bold m-0">작업 상세</h3>
          <button
            onClick={onClose}
            className="bg-transparent border-none text-text-muted cursor-pointer hover:text-text"
          >
            <X size={20} />
          </button>
        </div>

        <div className="grid grid-cols-2 gap-3 text-sm mb-4">
          <div>
            <span className="text-text-muted">상태</span>
            <div className="mt-1"><StatusBadge status={job.status} /></div>
          </div>
          <div>
            <span className="text-text-muted">모델</span>
            <div className="mt-1 text-text">{job.model_variant}</div>
          </div>
          <div>
            <span className="text-text-muted">해상도</span>
            <div className="mt-1 text-text">{job.width}x{job.height}</div>
          </div>
          <div>
            <span className="text-text-muted">프레임</span>
            <div className="mt-1 text-text">{job.num_frames}f / {job.frame_rate}fps</div>
          </div>
          <div>
            <span className="text-text-muted">스텝 / 스케일</span>
            <div className="mt-1 text-text">{job.num_inference_steps} / {job.guidance_scale}</div>
          </div>
          <div>
            <span className="text-text-muted">시드</span>
            <div className="mt-1 text-text">{job.seed ?? '랜덤'}</div>
          </div>
          <div className="col-span-2">
            <span className="text-text-muted">생성일</span>
            <div className="mt-1 text-text">{new Date(job.created_at).toLocaleString('ko-KR')}</div>
          </div>
        </div>

        <div className="mb-4">
          <span className="text-text-muted text-sm">프롬프트</span>
          <p className="mt-1 text-sm text-text bg-bg-input rounded-lg p-3 whitespace-pre-wrap break-words m-0">
            {job.prompt}
          </p>
        </div>

        {job.negative_prompt && (
          <div className="mb-4">
            <span className="text-text-muted text-sm">네거티브 프롬프트</span>
            <p className="mt-1 text-sm text-text bg-bg-input rounded-lg p-3 whitespace-pre-wrap break-words m-0">
              {job.negative_prompt}
            </p>
          </div>
        )}

        {job.keyframes && job.keyframes.length > 0 && (
          <div className="mb-4">
            <span className="text-text-muted text-sm">키프레임 ({job.keyframes.length})</span>
            <div className="flex gap-2 mt-2 overflow-x-auto">
              {job.keyframes.map((kf, i) => (
                <div key={i} className="flex-shrink-0 w-24">
                  <img
                    src={kf.image_url}
                    alt={`kf-${i}`}
                    className="w-full aspect-video object-cover rounded-lg"
                  />
                  <div className="text-[10px] text-text-muted mt-1 text-center">
                    f{kf.frame_index} / s{kf.strength}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {job.status === 'completed' && job.result_video_url && (
          <div className="mb-4">
            <span className="text-text-muted text-sm">생성 결과</span>
            <video
              src={job.result_video_url}
              controls
              className="w-full rounded-lg mt-2"
              style={{ maxHeight: '300px' }}
            />
            <a
              href={job.result_video_url}
              download
              className="inline-flex items-center gap-1.5 mt-2 text-sm text-primary hover:underline"
            >
              <Download size={14} /> 다운로드
            </a>
          </div>
        )}

        {job.status === 'failed' && job.error_message && (
          <div className="mb-4 bg-red-500/10 rounded-lg p-3">
            <span className="text-red-400 text-sm font-semibold">에러</span>
            <p className="mt-1 text-sm text-red-300 m-0">{job.error_message}</p>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main Page ──

type KeyframeState = { file: File | null; url: string; frame_index: number; strength: number };

const DEFAULT_FORM = {
  prompt: '',
  negative_prompt: '',
  resolutionIdx: 0,
  durationIdx: 2,
  variantIdx: 0,
  frame_rate: 24,
  num_inference_steps: 40,
  guidance_scale: 3.0,
  seed: '',
};

export default function AdminVideoGenPage() {
  // ── Form state ──
  const [form, setForm] = useState(DEFAULT_FORM);
  const [keyframes, setKeyframes] = useState<(KeyframeState | null)[]>([
    null, null, null, null, null,
  ]);
  const [submitting, setSubmitting] = useState(false);

  // ── Job list ──
  const [jobs, setJobs] = useState<VideoGenJob[]>([]);
  const [total, setTotal] = useState(0);
  const [listLoading, setListLoading] = useState(true);

  // ── Detail modal ──
  const [selectedJob, setSelectedJob] = useState<VideoGenJob | null>(null);

  // ── Polling ──
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Fetchers ──

  const fetchJobs = useCallback(() => {
    setListLoading(true);
    api
      .get<VideoGenListResponse>('/admin/video-gen?limit=50')
      .then((res) => {
        setJobs(res.items ?? []);
        setTotal(res.total ?? 0);
      })
      .catch(() => toast.error('작업 목록을 불러올 수 없습니다'))
      .finally(() => setListLoading(false));
  }, []);

  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

  // 5초 폴링: active 작업이 있을 때만
  useEffect(() => {
    const hasActive = jobs.some((j) =>
      ['pending', 'submitted', 'processing'].includes(j.status),
    );

    if (hasActive) {
      pollRef.current = setInterval(fetchJobs, 5000);
    } else if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }

    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [jobs, fetchJobs]);

  // ── Stats ──
  const stats = {
    total,
    pending: jobs.filter((j) => ['pending', 'submitted', 'processing'].includes(j.status)).length,
    completed: jobs.filter((j) => j.status === 'completed').length,
    failed: jobs.filter((j) => j.status === 'failed').length,
  };

  // ── Form handlers ──

  const updateForm = (patch: Partial<typeof form>) => setForm((f) => ({ ...f, ...patch }));

  const handleKeyframeUpload = async (index: number, file: File) => {
    try {
      const res = await api.upload<{ url: string }>('/uploads/image', file);
      setKeyframes((prev) => {
        const next = [...prev];
        next[index] = {
          file,
          url: res.url,
          frame_index: index === 0 ? 0 : DURATION_PRESETS[form.durationIdx].frames - 1,
          strength: 1.0,
        };
        return next;
      });
    } catch {
      toast.error('이미지 업로드에 실패했습니다');
    }
  };

  const handleKeyframeRemove = (index: number) => {
    setKeyframes((prev) => {
      const next = [...prev];
      next[index] = null;
      return next;
    });
  };

  const handleKeyframeChange = (index: number, field: 'frame_index' | 'strength', value: number) => {
    setKeyframes((prev) => {
      const next = [...prev];
      if (next[index]) {
        next[index] = { ...next[index]!, [field]: value };
      }
      return next;
    });
  };

  const handleSubmit = async () => {
    if (!form.prompt.trim()) {
      toast.error('프롬프트를 입력해주세요');
      return;
    }
    setSubmitting(true);

    const resolution = RESOLUTION_PRESETS[form.resolutionIdx];
    const kfPayload = keyframes
      .filter((kf): kf is KeyframeState => kf !== null)
      .map((kf) => ({
        image_url: kf.url,
        frame_index: kf.frame_index,
        strength: kf.strength,
      }));

    try {
      await api.post('/admin/video-gen', {
        prompt: form.prompt.trim(),
        negative_prompt: form.negative_prompt.trim() || undefined,
        width: resolution.width,
        height: resolution.height,
        num_frames: DURATION_PRESETS[form.durationIdx].frames,
        frame_rate: form.frame_rate,
        num_inference_steps: form.num_inference_steps,
        guidance_scale: form.guidance_scale,
        seed: form.seed ? Number(form.seed) : undefined,
        model_variant: VARIANT_OPTIONS[form.variantIdx].value,
        keyframes: kfPayload.length > 0 ? kfPayload : undefined,
      });
      toast.success('영상 생성 작업이 제출되었습니다');
      setForm(DEFAULT_FORM);
      setKeyframes([null, null, null, null, null]);
      fetchJobs();
    } catch {
      toast.error('작업 제출에 실패했습니다');
    } finally {
      setSubmitting(false);
    }
  };

  const handleCancel = async (jobId: string) => {
    try {
      await api.post(`/admin/video-gen/${jobId}/cancel`);
      toast.success('작업이 취소되었습니다');
      fetchJobs();
    } catch {
      toast.error('작업 취소에 실패했습니다');
    }
  };

  // ── Table columns ──

  const columns = [
    {
      key: 'prompt' as const,
      label: '프롬프트',
      render: (val: unknown) => (
        <span className="block max-w-[250px] truncate" title={String(val)}>
          {String(val)}
        </span>
      ),
    },
    {
      key: 'width' as const,
      label: '해상도',
      render: (_: unknown, row: VideoGenJob) => `${row.width}x${row.height}`,
    },
    {
      key: 'num_frames' as const,
      label: '길이',
      render: (_: unknown, row: VideoGenJob) =>
        `${row.num_frames}f / ${row.frame_rate}fps`,
    },
    { key: 'model_variant' as const, label: '모델' },
    {
      key: 'status' as const,
      label: '상태',
      render: (val: unknown) => <StatusBadge status={String(val)} />,
    },
    {
      key: 'created_at' as const,
      label: '생성일',
      render: (val: unknown) => formatDate(String(val)),
    },
    {
      key: 'id' as const,
      label: '액션',
      render: (_: unknown, row: VideoGenJob) => (
        <div className="flex gap-1.5">
          {row.status === 'completed' && row.result_video_url && (
            <a
              href={row.result_video_url}
              download
              onClick={(e) => e.stopPropagation()}
              className="p-1.5 rounded-lg hover:bg-bg-hover text-green-400"
              title="다운로드"
            >
              <Download size={14} />
            </a>
          )}
          {['pending', 'submitted', 'processing'].includes(row.status) && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                handleCancel(row.id);
              }}
              className="p-1.5 rounded-lg hover:bg-bg-hover text-red-400 bg-transparent border-none cursor-pointer"
              title="취소"
            >
              <Ban size={14} />
            </button>
          )}
        </div>
      ),
    },
  ];

  // ── Render ──

  return (
    <div>
      <h1 className="page-title">영상 생성 (LTX-Video 13B)</h1>

      {/* Stat Cards */}
      {listLoading ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          {Array.from({ length: 4 }).map((_, i) => (
            <SkeletonStat key={i} />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <StatCard title="전체" value={stats.total} icon={<Video className="w-5 h-5" />} />
          <StatCard
            title="진행 중"
            value={stats.pending}
            icon={<Clock className="w-5 h-5" />}
          />
          <StatCard
            title="완료"
            value={stats.completed}
            icon={<CheckCircle className="w-5 h-5" />}
          />
          <StatCard
            title="실패"
            value={stats.failed}
            icon={<XCircle className="w-5 h-5" />}
          />
        </div>
      )}

      {/* Generation Form */}
      <section className="card mb-6">
        <h2 className="section-title flex items-center gap-2">
          <Play size={18} /> 새 영상 생성
        </h2>

        <div className="flex flex-col gap-4">
          {/* Prompt */}
          <div>
            <label className="text-sm text-text-secondary block mb-1">프롬프트</label>
            <textarea
              className="textarea w-full"
              rows={3}
              maxLength={2000}
              placeholder="생성할 영상을 설명하세요 (영어 권장)..."
              value={form.prompt}
              onChange={(e) => updateForm({ prompt: e.target.value })}
            />
          </div>

          {/* Negative Prompt */}
          <div>
            <label className="text-sm text-text-secondary block mb-1">네거티브 프롬프트</label>
            <textarea
              className="textarea w-full"
              rows={2}
              placeholder="제외할 요소 (선택사항)..."
              value={form.negative_prompt}
              onChange={(e) => updateForm({ negative_prompt: e.target.value })}
            />
          </div>

          {/* Row 1: Resolution, Duration, Variant */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="text-sm text-text-secondary block mb-1">해상도</label>
              <select
                className="input w-full"
                value={form.resolutionIdx}
                onChange={(e) => updateForm({ resolutionIdx: Number(e.target.value) })}
              >
                {RESOLUTION_PRESETS.map((p, i) => (
                  <option key={i} value={i}>
                    {p.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-sm text-text-secondary block mb-1">길이</label>
              <select
                className="input w-full"
                value={form.durationIdx}
                onChange={(e) => updateForm({ durationIdx: Number(e.target.value) })}
              >
                {DURATION_PRESETS.map((p, i) => (
                  <option key={i} value={i}>
                    {p.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-sm text-text-secondary block mb-1">모델 변형</label>
              <select
                className="input w-full"
                value={form.variantIdx}
                onChange={(e) => updateForm({ variantIdx: Number(e.target.value) })}
              >
                {VARIANT_OPTIONS.map((o, i) => (
                  <option key={i} value={i}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Row 2: FPS, Steps, Scale, Seed */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div>
              <label className="text-sm text-text-secondary block mb-1">FPS</label>
              <input
                type="number"
                className="input w-full"
                min={8}
                max={60}
                value={form.frame_rate}
                onChange={(e) => updateForm({ frame_rate: Number(e.target.value) })}
              />
            </div>
            <div>
              <label className="text-sm text-text-secondary block mb-1">스텝</label>
              <input
                type="number"
                className="input w-full"
                min={4}
                max={100}
                value={form.num_inference_steps}
                onChange={(e) => updateForm({ num_inference_steps: Number(e.target.value) })}
              />
            </div>
            <div>
              <label className="text-sm text-text-secondary block mb-1">가이던스 스케일</label>
              <input
                type="number"
                className="input w-full"
                min={1.0}
                max={10.0}
                step={0.5}
                value={form.guidance_scale}
                onChange={(e) => updateForm({ guidance_scale: Number(e.target.value) })}
              />
            </div>
            <div>
              <label className="text-sm text-text-secondary block mb-1">시드</label>
              <input
                type="number"
                className="input w-full"
                placeholder="랜덤"
                value={form.seed}
                onChange={(e) => updateForm({ seed: e.target.value })}
              />
            </div>
          </div>

          {/* Keyframes */}
          <div>
            <label className="text-sm text-text-secondary block mb-2">
              키프레임 이미지 (최대 5장, 선택사항)
            </label>
            <div className="grid grid-cols-3 sm:grid-cols-5 gap-3">
              {keyframes.map((kf, i) => (
                <KeyframeSlot
                  key={i}
                  index={i}
                  kf={kf}
                  maxFrames={DURATION_PRESETS[form.durationIdx].frames}
                  onUpload={handleKeyframeUpload}
                  onRemove={handleKeyframeRemove}
                  onChange={handleKeyframeChange}
                />
              ))}
            </div>
          </div>

          {/* Submit */}
          <div className="flex justify-end pt-2">
            <button
              className="btn-primary flex items-center gap-2"
              onClick={handleSubmit}
              disabled={submitting || !form.prompt.trim()}
            >
              {submitting ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <Play size={16} />
              )}
              {submitting ? '제출 중...' : '생성 시작'}
            </button>
          </div>
        </div>
      </section>

      {/* Job History */}
      <section>
        <h2 className="section-title">작업 내역</h2>
        <div className="card">
          <DataTable
            columns={columns}
            data={jobs}
            loading={listLoading}
            onRowClick={(row) => setSelectedJob(row as VideoGenJob)}
          />
        </div>
      </section>

      {/* Detail Modal */}
      {selectedJob && (
        <JobDetailModal job={selectedJob} onClose={() => setSelectedJob(null)} />
      )}
    </div>
  );
}
