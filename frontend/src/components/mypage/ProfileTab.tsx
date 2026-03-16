/** 마이페이지 프로필 탭. 하드코딩된 사용자 정보 + 비밀번호 변경 폼 UI. */
'use client';

import { useState } from 'react';
import { User, Lock, Calendar, Shield, Mail, IdCard, Eye, EyeOff } from 'lucide-react';

const MOCK_PROFILE = {
  id: 'user-001',
  login_id: 'nemo_user',
  nickname: '토론왕김철수',
  email: 'nemo_user@example.com',
  role: 'user' as const,
  age_group: 'adult_verified' as const,
  adult_verified_at: '2025-11-15T09:00:00Z',
  created_at: '2025-10-01T12:00:00Z',
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
  const profile = MOCK_PROFILE;
  const ageInfo = AGE_GROUP_LABELS[profile.age_group] ?? { label: profile.age_group, color: 'bg-text-muted' };

  // 비밀번호 변경 폼 상태
  const [showPasswordForm, setShowPasswordForm] = useState(false);
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [passwordChanged, setPasswordChanged] = useState(false);

  const handleChangePassword = (e: React.FormEvent) => {
    e.preventDefault();
    if (newPassword !== confirmPassword) return;
    if (newPassword.length < 6) return;
    // 하드코딩 — 실제 API 호출 없음
    setPasswordChanged(true);
    setTimeout(() => {
      setShowPasswordForm(false);
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      setPasswordChanged(false);
    }, 1500);
  };

  // 비밀번호 강도 체크
  const getStrength = (pw: string) => {
    if (pw.length < 6) return { level: 0, label: '6자 이상 필요', color: 'bg-text-muted' };
    let score = 0;
    if (pw.length >= 8) score++;
    if (/[A-Z]/.test(pw) && /[a-z]/.test(pw)) score++;
    if (/\d/.test(pw)) score++;
    if (/[^a-zA-Z0-9]/.test(pw)) score++;
    if (score <= 1) return { level: 1, label: '약함', color: 'bg-red-500' };
    if (score <= 2) return { level: 2, label: '보통', color: 'bg-yellow-500' };
    return { level: 3, label: '강함', color: 'bg-green-500' };
  };

  const strength = getStrength(newPassword);

  return (
    <>
      {/* 사용자 정보 카드 */}
      <div className="bg-white rounded-xl p-6 mb-5 brutal-border brutal-shadow-sm">
        {/* 헤더: 아바타 + 닉네임 */}
        <div className="flex items-center gap-4 mb-6">
          <div className="w-16 h-16 rounded-full bg-primary/20 flex items-center justify-center text-primary text-2xl font-black brutal-border">
            {profile.nickname.charAt(0).toUpperCase()}
          </div>
          <div className="flex-1 min-w-0">
            <h2 className="m-0 text-xl font-black text-black">{profile.nickname}</h2>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-xs text-gray-500 font-semibold uppercase">
                {ROLE_LABELS[profile.role] ?? profile.role}
              </span>
              <span className={`text-[10px] font-bold text-white px-2 py-0.5 rounded-full ${ageInfo.color}`}>
                {ageInfo.label}
              </span>
            </div>
          </div>
        </div>

        {/* 상세 정보 */}
        <div className="flex flex-col gap-3 border-t-2 border-black/10 pt-4">
          <div className="flex items-center gap-3">
            <IdCard size={16} className="text-gray-400 shrink-0" />
            <span className="text-sm text-gray-500 w-24 font-semibold">아이디</span>
            <span className="text-sm text-black font-medium">{profile.login_id}</span>
          </div>
          <div className="flex items-center gap-3">
            <User size={16} className="text-gray-400 shrink-0" />
            <span className="text-sm text-gray-500 w-24 font-semibold">닉네임</span>
            <span className="text-sm text-black font-medium">{profile.nickname}</span>
          </div>
          <div className="flex items-center gap-3">
            <Mail size={16} className="text-gray-400 shrink-0" />
            <span className="text-sm text-gray-500 w-24 font-semibold">이메일</span>
            <span className="text-sm text-black font-medium">{profile.email}</span>
          </div>
          <div className="flex items-center gap-3">
            <Shield size={16} className="text-gray-400 shrink-0" />
            <span className="text-sm text-gray-500 w-24 font-semibold">역할</span>
            <span className="text-sm text-black font-medium">{ROLE_LABELS[profile.role] ?? profile.role}</span>
          </div>
          <div className="flex items-center gap-3">
            <Shield size={16} className="text-gray-400 shrink-0" />
            <span className="text-sm text-gray-500 w-24 font-semibold">연령 상태</span>
            <span className="text-sm text-black font-medium">{ageInfo.label}</span>
            {profile.adult_verified_at && (
              <span className="text-xs text-gray-400">
                ({new Date(profile.adult_verified_at).toLocaleDateString('ko-KR')} 인증)
              </span>
            )}
          </div>
          <div className="flex items-center gap-3">
            <Calendar size={16} className="text-gray-400 shrink-0" />
            <span className="text-sm text-gray-500 w-24 font-semibold">가입일</span>
            <span className="text-sm text-black font-medium">
              {new Date(profile.created_at).toLocaleDateString('ko-KR', {
                year: 'numeric',
                month: 'long',
                day: 'numeric',
              })}
            </span>
          </div>
        </div>
      </div>

      {/* 비밀번호 변경 카드 */}
      <div className="bg-white rounded-xl p-6 brutal-border brutal-shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-black text-black flex items-center gap-2 m-0">
            <Lock size={18} className="text-gray-400" />
            비밀번호 변경
          </h2>
          {!showPasswordForm && (
            <button
              onClick={() => setShowPasswordForm(true)}
              className="px-4 py-2 bg-white text-black text-sm font-black rounded-xl brutal-border brutal-shadow-sm hover:translate-y-[-2px] transition-all cursor-pointer"
            >
              변경하기
            </button>
          )}
        </div>

        {showPasswordForm ? (
          <form onSubmit={handleChangePassword} className="flex flex-col gap-3">
            {/* 현재 비밀번호 */}
            <div className="flex flex-col gap-1">
              <label className="text-[13px] font-semibold text-gray-500">현재 비밀번호</label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  required
                  className="w-full bg-gray-50 border-2 border-black rounded-xl px-4 py-3 text-sm text-black focus:outline-none focus:border-primary"
                  placeholder="현재 비밀번호 입력"
                />
              </div>
            </div>

            {/* 새 비밀번호 */}
            <div className="flex flex-col gap-1">
              <label className="text-[13px] font-semibold text-gray-500">새 비밀번호</label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  required
                  minLength={6}
                  className="w-full bg-gray-50 border-2 border-black rounded-xl px-4 py-3 pr-10 text-sm text-black focus:outline-none focus:border-primary"
                  placeholder="6자 이상 입력"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 bg-transparent border-none cursor-pointer text-gray-400 hover:text-black p-0"
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
              {newPassword.length > 0 && (
                <div className="flex items-center gap-2 mt-1">
                  <div className="flex gap-1 flex-1">
                    {[1, 2, 3].map((level) => (
                      <div
                        key={level}
                        className={`h-1.5 flex-1 rounded-full ${
                          level <= strength.level ? strength.color : 'bg-gray-200'
                        }`}
                      />
                    ))}
                  </div>
                  <span className="text-xs text-gray-500 font-semibold">{strength.label}</span>
                </div>
              )}
            </div>

            {/* 새 비밀번호 확인 */}
            <div className="flex flex-col gap-1">
              <label className="text-[13px] font-semibold text-gray-500">새 비밀번호 확인</label>
              <input
                type={showPassword ? 'text' : 'password'}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                minLength={6}
                className={`w-full bg-gray-50 border-2 rounded-xl px-4 py-3 text-sm text-black focus:outline-none focus:border-primary ${
                  confirmPassword && newPassword !== confirmPassword ? 'border-red-500' : 'border-black'
                } ${confirmPassword && newPassword === confirmPassword && newPassword.length >= 6 ? 'border-green-500' : ''}`}
                placeholder="새 비밀번호 다시 입력"
              />
              {confirmPassword && newPassword !== confirmPassword && (
                <span className="text-red-500 text-xs font-semibold">비밀번호가 일치하지 않습니다</span>
              )}
              {confirmPassword && newPassword === confirmPassword && newPassword.length >= 6 && (
                <span className="text-green-500 text-xs font-semibold">비밀번호가 일치합니다</span>
              )}
            </div>

            {passwordChanged && (
              <div className="py-2 px-3 rounded-xl bg-green-50 border-2 border-green-500 text-green-600 text-sm font-semibold text-center">
                ✅ 비밀번호가 변경되었습니다
              </div>
            )}

            <div className="flex gap-2 mt-2">
              <button
                type="submit"
                disabled={!currentPassword || newPassword.length < 6 || newPassword !== confirmPassword || passwordChanged}
                className="flex-1 py-3 bg-primary text-white text-sm font-black rounded-xl brutal-border brutal-shadow-sm hover:translate-y-[-2px] transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:translate-y-0"
              >
                {passwordChanged ? '변경 완료!' : '비밀번호 변경'}
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowPasswordForm(false);
                  setCurrentPassword('');
                  setNewPassword('');
                  setConfirmPassword('');
                }}
                className="flex-1 py-3 bg-white text-black text-sm font-black rounded-xl brutal-border hover:bg-gray-50 transition-all cursor-pointer"
              >
                취소
              </button>
            </div>
          </form>
        ) : (
          <p className="text-sm text-gray-500 m-0">
            보안을 위해 주기적으로 비밀번호를 변경하세요.
          </p>
        )}
      </div>
    </>
  );
}
