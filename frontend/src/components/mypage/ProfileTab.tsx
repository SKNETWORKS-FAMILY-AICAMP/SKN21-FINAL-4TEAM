/** 마이페이지 프로필 탭. 닉네임 인라인 편집, 비밀번호 변경, 역할/인증 상태 표시. */
'use client';

import { useEffect, useState } from 'react';
import { User, Pencil, Lock, Calendar, Shield, Check, X, Gem } from 'lucide-react';
import { api } from '@/lib/api';
import { useUserStore } from '@/stores/userStore';
import { useCreditStore } from '@/stores/creditStore';
import { toast } from '@/stores/toastStore';

type ProfileData = {
  id: string;
  nickname: string;
  role: string;
  age_group: string;
  adult_verified_at: string | null;
  preferred_llm_model_id: string | null;
  created_at: string;
};

const AGE_GROUP_LABELS: Record<string, { label: string; color: string }> = {
  unverified: { label: '미인증', color: 'bg-text-muted' },
  minor_safe: { label: '청소년', color: 'bg-warning' },
  adult_verified: { label: '성인인증', color: 'bg-success' },
};

const ROLE_LABELS: Record<string, string> = {
  user: '일반 사용자',
  admin: '관리자',
  superadmin: '슈퍼관리자',
};

export function ProfileTab() {
  const { user, setUser } = useUserStore();
  const { balance: creditBalance, fetchBalance } = useCreditStore();
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [loading, setLoading] = useState(true);

  const [editingNickname, setEditingNickname] = useState(false);
  const [newNickname, setNewNickname] = useState('');
  const [savingNickname, setSavingNickname] = useState(false);

  const [showPasswordForm, setShowPasswordForm] = useState(false);
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [savingPassword, setSavingPassword] = useState(false);

  useEffect(() => {
    fetchBalance();
    api
      .get<ProfileData>('/auth/me')
      .then((data) => {
        setProfile(data);
        setNewNickname(data.nickname);
      })
      .catch(() => toast.error('프로필을 불러올 수 없습니다'))
      .finally(() => setLoading(false));
  }, [fetchBalance]);

  const handleSaveNickname = async () => {
    if (!newNickname.trim() || newNickname === profile?.nickname) {
      setEditingNickname(false);
      return;
    }
    setSavingNickname(true);
    try {
      const updated = await api.put<ProfileData>('/auth/me', { nickname: newNickname.trim() });
      setProfile(updated);
      if (user) {
        setUser({ ...user, nickname: updated.nickname });
      }
      setEditingNickname(false);
      toast.success('닉네임이 변경되었습니다');
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '닉네임 변경에 실패했습니다';
      toast.error(message);
    } finally {
      setSavingNickname(false);
    }
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      toast.error('새 비밀번호가 일치하지 않습니다');
      return;
    }
    if (newPassword.length < 4) {
      toast.error('비밀번호는 4자 이상이어야 합니다');
      return;
    }
    setSavingPassword(true);
    try {
      await api.put('/auth/me/password', {
        current_password: currentPassword,
        new_password: newPassword,
      });
      toast.success('비밀번호가 변경되었습니다');
      setShowPasswordForm(false);
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '비밀번호 변경에 실패했습니다';
      toast.error(message);
    } finally {
      setSavingPassword(false);
    }
  };

  if (loading) {
    return (
      <div className="animate-pulse">
        <div className="card p-6">
          <div className="flex items-center gap-4 mb-6">
            <div className="w-16 h-16 rounded-full bg-bg-hover" />
            <div className="flex-1">
              <div className="h-5 w-24 bg-bg-hover rounded mb-2" />
              <div className="h-3 w-16 bg-bg-hover rounded" />
            </div>
          </div>
          <div className="h-4 w-full bg-bg-hover rounded mb-3" />
          <div className="h-4 w-3/4 bg-bg-hover rounded" />
        </div>
      </div>
    );
  }

  if (!profile) return null;

  const ageInfo = AGE_GROUP_LABELS[profile.age_group] ?? { label: profile.age_group, color: 'bg-text-muted' };

  return (
    <>
      {/* Profile header */}
      <div className="card p-6 mb-5">
        <div className="flex items-center gap-4 mb-6">
          <div className="w-16 h-16 rounded-full bg-primary/20 flex items-center justify-center text-primary text-2xl font-bold">
            {profile.nickname.charAt(0).toUpperCase()}
          </div>
          <div className="flex-1 min-w-0">
            {editingNickname ? (
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={newNickname}
                  onChange={(e) => setNewNickname(e.target.value)}
                  className="input py-1.5 px-3 text-base flex-1"
                  maxLength={50}
                  autoFocus
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleSaveNickname();
                    if (e.key === 'Escape') {
                      setEditingNickname(false);
                      setNewNickname(profile.nickname);
                    }
                  }}
                />
                <button
                  onClick={handleSaveNickname}
                  disabled={savingNickname}
                  className="p-1.5 rounded-lg bg-success text-white border-none cursor-pointer"
                >
                  <Check size={16} />
                </button>
                <button
                  onClick={() => {
                    setEditingNickname(false);
                    setNewNickname(profile.nickname);
                  }}
                  className="p-1.5 rounded-lg bg-bg-hover text-text-muted border-none cursor-pointer"
                >
                  <X size={16} />
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <h2 className="m-0 text-xl text-text">{profile.nickname}</h2>
                <button
                  onClick={() => setEditingNickname(true)}
                  className="p-1 rounded bg-transparent border-none cursor-pointer text-text-muted hover:text-primary"
                >
                  <Pencil size={14} />
                </button>
              </div>
            )}
            <div className="flex items-center gap-2 mt-1">
              <span className="text-xs text-text-muted uppercase font-semibold">
                {profile.role}
              </span>
              <span className={`badge ${ageInfo.color}`}>{ageInfo.label}</span>
            </div>
          </div>
        </div>

        <div className="flex flex-col gap-3 border-t border-border pt-4">
          <div className="flex items-center gap-3">
            <User size={16} className="text-text-muted shrink-0" />
            <span className="text-sm text-text-muted w-20">닉네임</span>
            <span className="text-sm text-text">{profile.nickname}</span>
          </div>
          <div className="flex items-center gap-3">
            <Shield size={16} className="text-text-muted shrink-0" />
            <span className="text-sm text-text-muted w-20">역할</span>
            <span className="text-sm text-text">{ROLE_LABELS[profile.role] ?? profile.role}</span>
          </div>
          <div className="flex items-center gap-3">
            <Shield size={16} className="text-text-muted shrink-0" />
            <span className="text-sm text-text-muted w-20">연령 상태</span>
            <span className="text-sm text-text">{ageInfo.label}</span>
            {profile.adult_verified_at && (
              <span className="text-xs text-text-muted">
                ({new Date(profile.adult_verified_at).toLocaleDateString('ko-KR')} 인증)
              </span>
            )}
          </div>
          <div className="flex items-center gap-3">
            <Gem size={16} className="text-primary shrink-0" />
            <span className="text-sm text-text-muted w-20">대화석</span>
            {creditBalance ? (
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-semibold text-primary">
                  {creditBalance.balance.toLocaleString()}석
                </span>
                <span className="text-xs text-text-muted">
                  (일일 {creditBalance.daily_credits}석 ·{' '}
                  {creditBalance.granted_today ? '오늘 지급됨' : '오늘 미지급'})
                </span>
              </div>
            ) : (
              <span className="text-sm text-text-muted">불러오는 중...</span>
            )}
          </div>
          <div className="flex items-center gap-3">
            <Calendar size={16} className="text-text-muted shrink-0" />
            <span className="text-sm text-text-muted w-20">가입일</span>
            <span className="text-sm text-text">
              {new Date(profile.created_at).toLocaleDateString('ko-KR', {
                year: 'numeric',
                month: 'long',
                day: 'numeric',
              })}
            </span>
          </div>
        </div>
      </div>

      {/* Password change */}
      <div className="card p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="section-title flex items-center gap-2 m-0">
            <Lock size={18} className="text-text-muted" />
            비밀번호 변경
          </h2>
          {!showPasswordForm && (
            <button onClick={() => setShowPasswordForm(true)} className="btn-secondary text-sm">
              변경하기
            </button>
          )}
        </div>

        {showPasswordForm ? (
          <form onSubmit={handleChangePassword} className="flex flex-col gap-3">
            <div className="flex flex-col gap-1">
              <label className="text-[13px] font-semibold text-text-label">현재 비밀번호</label>
              <input
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                required
                className="input py-2.5 px-3"
                placeholder="현재 비밀번호 입력"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[13px] font-semibold text-text-label">새 비밀번호</label>
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                minLength={4}
                className="input py-2.5 px-3"
                placeholder="새 비밀번호 입력"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[13px] font-semibold text-text-label">새 비밀번호 확인</label>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                minLength={4}
                className="input py-2.5 px-3"
                placeholder="새 비밀번호 다시 입력"
              />
              {confirmPassword && newPassword !== confirmPassword && (
                <span className="text-danger-text text-xs">비밀번호가 일치하지 않습니다</span>
              )}
            </div>
            <div className="flex gap-2 mt-2">
              <button type="submit" disabled={savingPassword} className="btn-primary">
                {savingPassword ? '변경 중...' : '비밀번호 변경'}
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowPasswordForm(false);
                  setCurrentPassword('');
                  setNewPassword('');
                  setConfirmPassword('');
                }}
                className="btn-secondary"
              >
                취소
              </button>
            </div>
          </form>
        ) : (
          <p className="text-sm text-text-muted m-0">
            보안을 위해 주기적으로 비밀번호를 변경하세요.
          </p>
        )}
      </div>
    </>
  );
}
