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
        <p>이 콘텐츠를 이용하려면 성인인증이 필요합니다.</p>
        <button onClick={onVerify}>성인인증 하기</button>
        <button onClick={onClose}>닫기</button>
      </div>
    </div>
  );
}
