/** 성인인증 모달. 본인확인 방법(휴대폰/카드/SSO)을 선택하여 인증 요청. */
'use client';

import { useState, useRef, useEffect } from 'react';
import { api } from '@/lib/api';

type Props = {
  isOpen: boolean;
  onClose: () => void;
  onVerified: () => void;
};

type VerifyMethod = 'self_declare' | 'phone' | 'card' | 'sso';

const METHOD_LABELS: Record<VerifyMethod, string> = {
  self_declare: '자가선언',
  phone: '휴대폰',
  card: '카드',
  sso: 'SSO',
};

export function AdultVerifyModal({ isOpen, onClose, onVerified }: Props) {
  const [method, setMethod] = useState<VerifyMethod>('self_declare');
  const [birthYear, setBirthYear] = useState('');
  const [phoneNumber, setPhoneNumber] = useState('');
  const [code, setCode] = useState('');
  const [cardLast4, setCardLast4] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const modalRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    const modal = modalRef.current;
    if (!modal) return;

    const focusableEls = modal.querySelectorAll<HTMLElement>(
      'button, input, select, textarea, [tabindex]:not([tabindex="-1"])',
    );
    const firstEl = focusableEls[0];
    const lastEl = focusableEls[focusableEls.length - 1];

    firstEl?.focus();

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
        return;
      }
      if (e.key !== 'Tab') return;
      if (e.shiftKey && document.activeElement === firstEl) {
        e.preventDefault();
        lastEl?.focus();
      } else if (!e.shiftKey && document.activeElement === lastEl) {
        e.preventDefault();
        firstEl?.focus();
      }
    };

    modal.addEventListener('keydown', handleKeyDown);
    return () => modal.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const resetForm = () => {
    setBirthYear('');
    setPhoneNumber('');
    setCode('');
    setCardLast4('');
    setError('');
  };

  const handleMethodChange = (m: VerifyMethod) => {
    setMethod(m);
    resetForm();
  };

  const handleSubmit = async () => {
    setError('');
    setLoading(true);

    const body: Record<string, unknown> = { method };

    if (method === 'self_declare' || method === 'sso' || method === 'card') {
      if (!birthYear) {
        setError('생년을 입력하세요');
        setLoading(false);
        return;
      }
      body.birth_year = parseInt(birthYear, 10);
    }

    if (method === 'phone') {
      if (!phoneNumber) {
        setError('전화번호를 입력하세요');
        setLoading(false);
        return;
      }
      if (!code) {
        setError('인증코드를 입력하세요');
        setLoading(false);
        return;
      }
      body.phone_number = phoneNumber;
      body.code = code;
    }

    if (method === 'card') {
      if (!cardLast4) {
        setError('카드 마지막 4자리를 입력하세요');
        setLoading(false);
        return;
      }
      body.card_last4 = cardLast4;
    }

    try {
      await api.post('/auth/adult-verify', body);
      onVerified();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '인증에 실패했습니다';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        ref={modalRef}
        className="modal-content max-w-[480px] w-full mx-4"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="성인인증"
      >
        <div className="flex justify-between items-center mb-5">
          <h2 className="text-lg font-bold">성인인증</h2>
          <button
            onClick={onClose}
            className="text-text-muted hover:text-text-primary text-xl bg-transparent border-none cursor-pointer"
          >
            ✕
          </button>
        </div>

        <p className="text-sm text-text-secondary mb-4">
          18+ 콘텐츠 이용을 위해 성인인증이 필요합니다.
          <br />
          <span className="text-xs text-text-muted">
            (테스트 모드: 자가선언/SSO/카드는 만 19세 이상 생년, 휴대폰은 인증코드 123456)
          </span>
        </p>

        {/* 방법 선택 탭 */}
        <div className="flex gap-1 mb-5 p-1 bg-bg-surface rounded-lg">
          {(Object.keys(METHOD_LABELS) as VerifyMethod[]).map((m) => (
            <button
              key={m}
              onClick={() => handleMethodChange(m)}
              className={`flex-1 py-2 px-2 rounded-md text-sm font-medium border-none cursor-pointer transition-colors ${
                method === m
                  ? 'bg-primary text-white'
                  : 'bg-transparent text-text-secondary hover:bg-bg-hover'
              }`}
            >
              {METHOD_LABELS[m]}
            </button>
          ))}
        </div>

        {/* 입력 폼 */}
        <div className="flex flex-col gap-3 mb-5">
          {(method === 'self_declare' || method === 'sso' || method === 'card') && (
            <div>
              <label className="block text-sm font-medium mb-1">생년 (4자리)</label>
              <input
                type="number"
                placeholder="예: 1995"
                value={birthYear}
                onChange={(e) => setBirthYear(e.target.value)}
                className="input w-full"
                min={1900}
                max={new Date().getFullYear()}
              />
            </div>
          )}

          {method === 'phone' && (
            <>
              <div>
                <label className="block text-sm font-medium mb-1">전화번호</label>
                <input
                  type="tel"
                  placeholder="01012345678"
                  value={phoneNumber}
                  onChange={(e) => setPhoneNumber(e.target.value)}
                  className="input w-full"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">인증코드</label>
                <input
                  type="text"
                  placeholder="테스트: 123456"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  className="input w-full"
                  maxLength={6}
                />
              </div>
            </>
          )}

          {method === 'card' && (
            <div>
              <label className="block text-sm font-medium mb-1">카드 마지막 4자리</label>
              <input
                type="text"
                placeholder="1234"
                value={cardLast4}
                onChange={(e) => setCardLast4(e.target.value)}
                className="input w-full"
                maxLength={4}
              />
            </div>
          )}
        </div>

        {error && (
          <div className="text-danger text-sm mb-4 p-3 bg-danger/10 rounded-lg">
            {error}
          </div>
        )}

        <div className="flex gap-3 justify-end">
          <button
            onClick={onClose}
            className="btn-secondary py-2.5 px-5"
          >
            취소
          </button>
          <button
            onClick={handleSubmit}
            disabled={loading}
            className="btn-primary py-2.5 px-5"
          >
            {loading ? '인증 중...' : '인증하기'}
          </button>
        </div>
      </div>
    </div>
  );
}
