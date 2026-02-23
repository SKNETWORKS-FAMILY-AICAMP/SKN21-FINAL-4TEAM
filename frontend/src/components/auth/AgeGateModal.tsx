/** 18+ 콘텐츠 접근 차단 모달. 미인증 사용자에게 성인인증 유도. */
'use client';

type Props = {
  isOpen: boolean;
  onClose: () => void;
  onVerify: () => void;
};

export function AgeGateModal({ isOpen, onClose, onVerify }: Props) {
  if (!isOpen) return null;
  return (
    <div className="modal-overlay">
      <div className="modal-content">
        <h2>18+ 콘텐츠</h2>
        <p className="text-text-secondary mb-6">이 콘텐츠를 이용하려면 성인인증이 필요합니다.</p>
        <div className="flex gap-3 justify-center">
          <button className="btn-primary" onClick={onVerify}>성인인증 하기</button>
          <button className="btn-secondary" onClick={onClose}>닫기</button>
        </div>
      </div>
    </div>
  );
}
