'use client';

type Props = {
  onSend: (message: string) => void;
  disabled?: boolean;
};

export function MessageInput({ onSend, disabled = false }: Props) {
  return (
    <form>
      {/* 텍스트 입력 + 전송 버튼 */}
    </form>
  );
}
