'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { toast } from '@/stores/toastStore';

type AgeRatingPolicy = {
  ratings: string[];
  default: string;
  adult_verification_required: string[];
  enabled: boolean;
};

export default function AdminPolicyPage() {
  const [policy, setPolicy] = useState<AgeRatingPolicy>({
    ratings: ['all', '15+', '18+'],
    default: 'all',
    adult_verification_required: ['18+'],
    enabled: true,
  });

  useEffect(() => {
    api
      .get<AgeRatingPolicy>('/admin/policy/age-rating')
      .then((data) => setPolicy(data))
      .catch(() => {});
  }, []);

  const handleSave = async () => {
    try {
      await api.put('/admin/policy/age-rating', policy);
      toast.success('저장되었습니다');
    } catch {
      toast.error('저장에 실패했습니다');
    }
  };

  return (
    <div>
      <h1 className="page-title">정책 설정</h1>

      <div className="card mb-4">
        <h2 className="section-title">연령등급 정책</h2>

        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1">
            <label className="text-[13px] font-semibold text-text-label">활성 상태</label>
            <label className="flex items-center gap-2 text-[13px]">
              <input
                type="checkbox"
                checked={policy.enabled}
                onChange={(e) => setPolicy({ ...policy, enabled: e.target.checked })}
              />
              연령등급 정책 활성화
            </label>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-[13px] font-semibold text-text-label">등급 목록</label>
            <div className="flex gap-2">
              {policy.ratings.map((r) => (
                <span key={r} className="badge bg-bg-surface">
                  {r === 'all' ? '전체' : r}
                </span>
              ))}
            </div>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-[13px] font-semibold text-text-label">기본 등급</label>
            <select
              value={policy.default}
              onChange={(e) => setPolicy({ ...policy, default: e.target.value })}
              className="py-1 px-2 rounded-md border border-border-input text-[13px] w-[120px]"
            >
              {policy.ratings.map((r) => (
                <option key={r} value={r}>
                  {r === 'all' ? '전체' : r}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-[13px] font-semibold text-text-label">성인인증 필수 등급</label>
            <div className="flex gap-2">
              {policy.adult_verification_required.map((r) => (
                <span key={r} className="badge bg-danger">
                  {r}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>

      <button onClick={handleSave} className="btn-primary py-3 px-8 text-[15px]">
        저장
      </button>
    </div>
  );
}
