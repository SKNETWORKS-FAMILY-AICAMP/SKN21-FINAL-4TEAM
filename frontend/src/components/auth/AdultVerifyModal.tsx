'use client';

type Props = {
  isOpen: boolean;
  onClose: () => void;
  onVerified: () => void;
};

export function AdultVerifyModal({ isOpen, onClose, onVerified }: Props) {
  if (!isOpen) return null;
  return (
    <div className="modal-overlay">
      <div className="modal-content">
        <h2>성인인증</h2>
        {/* 본인인증 방법 선택 (휴대폰/카드/SSO) */}
      </div>
    </div>
  );
}
