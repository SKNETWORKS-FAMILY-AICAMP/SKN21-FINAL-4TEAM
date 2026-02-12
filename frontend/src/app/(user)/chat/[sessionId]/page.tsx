export default function ChatPage({ params }: { params: { sessionId: string } }) {
  return (
    <div>
      <h1>Chat Session: {params.sessionId}</h1>
      {/* Live2D + 배경 + 대화창 + 입력창 구성 예정 */}
    </div>
  );
}
