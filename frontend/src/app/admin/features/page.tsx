'use client';

import { useEffect, useState } from 'react';
import { RotateCcw } from 'lucide-react';
import { api } from '@/lib/api';
import { toast } from '@/stores/toastStore';

type ScreenFlag = {
  key: string;
  label: string;
  description: string;
  category: string;
  enabled: boolean;
};

function ToggleSwitch({
  enabled,
  onChange,
  loading,
}: {
  enabled: boolean;
  onChange: (v: boolean) => void;
  loading: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={enabled}
      disabled={loading}
      onClick={() => onChange(!enabled)}
      className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent
        transition-colors duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary
        disabled:cursor-not-allowed disabled:opacity-50
        ${enabled ? 'bg-primary' : 'bg-bg-muted'}`}
    >
      <span
        className={`pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow-sm
          ring-0 transition-transform duration-200
          ${enabled ? 'translate-x-5' : 'translate-x-0'}`}
      />
    </button>
  );
}

function FlagRow({
  flag,
  onToggle,
  toggling,
}: {
  flag: ScreenFlag;
  onToggle: (key: string, enabled: boolean) => void;
  toggling: boolean;
}) {
  return (
    <div className="flex items-center justify-between py-3 px-4 rounded-lg hover:bg-bg-hover transition-colors">
      <div className="flex flex-col gap-0.5 min-w-0 mr-4">
        <span className="text-sm font-medium text-text">{flag.label}</span>
        <span className="text-[12px] text-text-muted">{flag.description}</span>
      </div>
      <div className="flex items-center gap-3 shrink-0">
        <span
          className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${
            flag.enabled
              ? 'bg-success/15 text-success'
              : 'bg-danger/15 text-danger'
          }`}
        >
          {flag.enabled ? '활성' : '비활성'}
        </span>
        <ToggleSwitch
          enabled={flag.enabled}
          onChange={(v) => onToggle(flag.key, v)}
          loading={toggling}
        />
      </div>
    </div>
  );
}

export default function AdminFeaturesPage() {
  const [flags, setFlags] = useState<ScreenFlag[]>([]);
  const [loading, setLoading] = useState(true);
  const [togglingKey, setTogglingKey] = useState<string | null>(null);
  const [resetting, setResetting] = useState(false);

  const userFlags = flags.filter((f) => f.category === 'user');
  const adminFlags = flags.filter((f) => f.category === 'admin');

  useEffect(() => {
    api
      .get<ScreenFlag[]>('/admin/features')
      .then(setFlags)
      .catch(() => toast.error('화면 목록을 불러오지 못했습니다'))
      .finally(() => setLoading(false));
  }, []);

  const handleToggle = async (key: string, enabled: boolean) => {
    setTogglingKey(key);
    try {
      const updated = await api.patch<ScreenFlag>(`/admin/features/${key}`, { enabled });
      setFlags((prev) => prev.map((f) => (f.key === key ? updated : f)));
      toast.success(`${updated.label} ${enabled ? '활성화' : '비활성화'}되었습니다`);
    } catch {
      toast.error('변경에 실패했습니다');
    } finally {
      setTogglingKey(null);
    }
  };

  const handleReset = async () => {
    if (!confirm('모든 화면을 활성화 상태로 초기화하시겠습니까?')) return;
    setResetting(true);
    try {
      await api.post('/admin/features/reset');
      // 서버에서 다시 조회
      const fresh = await api.get<ScreenFlag[]>('/admin/features');
      setFlags(fresh);
      toast.success('모든 화면이 초기화되었습니다');
    } catch {
      toast.error('초기화에 실패했습니다');
    } finally {
      setResetting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <span className="inline-block w-6 h-6 border-2 border-text-muted border-t-primary rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="page-title mb-1">화면 관리</h1>
          <p className="text-text-secondary text-sm">
            각 화면을 활성화/비활성화합니다. 비활성화된 화면은 사용자에게 점검 중으로 표시됩니다.
          </p>
        </div>
        <button
          onClick={handleReset}
          disabled={resetting}
          className="flex items-center gap-1.5 text-sm text-text-secondary hover:text-text
            border border-border rounded-lg px-3 py-1.5 transition-colors disabled:opacity-50"
        >
          <RotateCcw size={14} className={resetting ? 'animate-spin' : ''} />
          전체 초기화
        </button>
      </div>

      {/* 사용자 화면 */}
      <div className="card mb-4">
        <div className="flex items-center gap-2 mb-4">
          <h2 className="section-title mb-0">사용자 화면</h2>
          <span className="text-[11px] text-text-muted bg-bg-surface border border-border rounded-full px-2 py-0.5">
            {userFlags.length}개
          </span>
          <span className="text-[11px] text-success bg-success/10 rounded-full px-2 py-0.5">
            활성 {userFlags.filter((f) => f.enabled).length}
          </span>
          {userFlags.some((f) => !f.enabled) && (
            <span className="text-[11px] text-danger bg-danger/10 rounded-full px-2 py-0.5">
              비활성 {userFlags.filter((f) => !f.enabled).length}
            </span>
          )}
        </div>
        <div className="flex flex-col divide-y divide-border">
          {userFlags.map((flag) => (
            <FlagRow
              key={flag.key}
              flag={flag}
              onToggle={handleToggle}
              toggling={togglingKey === flag.key}
            />
          ))}
        </div>
      </div>

      {/* 관리자 화면 */}
      {adminFlags.length > 0 && (
        <div className="card">
          <div className="flex items-center gap-2 mb-4">
            <h2 className="section-title mb-0">관리자 화면</h2>
            <span className="text-[11px] text-text-muted bg-bg-surface border border-border rounded-full px-2 py-0.5">
              {adminFlags.length}개
            </span>
          </div>
          <div className="flex flex-col divide-y divide-border">
            {adminFlags.map((flag) => (
              <FlagRow
                key={flag.key}
                flag={flag}
                onToggle={handleToggle}
                toggling={togglingKey === flag.key}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
