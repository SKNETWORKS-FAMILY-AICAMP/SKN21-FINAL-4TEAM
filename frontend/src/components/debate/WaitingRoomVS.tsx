'use client';

import { AgentProfilePanel } from './AgentProfilePanel';
import { CountUpTimer } from './CountUpTimer';

type Agent = {
  id: string;
  name: string;
  provider: string;
  model_id: string;
  elo_rating: number;
  wins: number;
  losses: number;
  draws: number;
};

type Props = {
  topicTitle: string;
  myAgent: Agent;
  opponent: Agent | null;
  startedAt: Date;
  isMatched: boolean;
  isAutoMatched: boolean;
  isRevealing: boolean;
  onCancel: () => void;
  cancelling: boolean;
};

export function WaitingRoomVS({
  topicTitle,
  myAgent,
  opponent,
  startedAt,
  isMatched,
  isAutoMatched,
  isRevealing,
  onCancel,
  cancelling,
}: Props) {
  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-900 via-gray-800 to-gray-900 flex flex-col items-center justify-center px-4 py-8">
      {/* 토픽 제목 */}
      <div className="mb-8 text-center max-w-[600px]">
        <p className="text-xs text-gray-500 uppercase tracking-widest mb-1">토론 주제</p>
        <h1 className="text-lg font-bold text-white">「{topicTitle}」</h1>
      </div>

      {/* VS 레이아웃 */}
      <div className="flex items-center justify-center gap-6 md:gap-12 w-full max-w-[700px]">
        {/* 내 에이전트 (좌) */}
        <div className="flex-1 flex justify-end">
          <AgentProfilePanel agent={myAgent} side="left" />
        </div>

        {/* 중앙 영역 */}
        <div className="flex flex-col items-center gap-4 flex-shrink-0">
          {isMatched ? (
            <div className="flex flex-col items-center gap-2">
              <span
                className="text-5xl font-black text-green-400 drop-shadow-[0_0_20px_rgba(74,222,128,0.8)]
                  animate-bounce"
              >
                MATCH!
              </span>
              {isAutoMatched && (
                <span className="text-xs px-3 py-1 rounded-full bg-yellow-500/20 text-yellow-400 font-semibold border border-yellow-500/30">
                  자동 매칭
                </span>
              )}
              <p className="text-sm text-gray-400">잠시 후 이동합니다...</p>
            </div>
          ) : (
            <>
              <span
                className="text-5xl font-black text-red-500
                  drop-shadow-[0_0_20px_rgba(239,68,68,0.6)]"
              >
                VS
              </span>
              <CountUpTimer startedAt={startedAt} maxSeconds={120} />
              <p className="text-xs text-gray-500">대기 중...</p>
            </>
          )}
        </div>

        {/* 상대 에이전트 (우) */}
        <div className="flex-1 flex justify-start">
          <AgentProfilePanel agent={opponent} side="right" isRevealing={isRevealing} />
        </div>
      </div>

      {/* 취소 버튼 */}
      {!isMatched && (
        <button
          onClick={onCancel}
          disabled={cancelling}
          className="mt-12 px-6 py-2 rounded-lg border border-gray-600 text-sm text-gray-400
            hover:border-red-500/50 hover:text-red-400 transition-colors disabled:opacity-50
            disabled:cursor-not-allowed"
        >
          {cancelling ? '취소 중...' : '대기 취소'}
        </button>
      )}
    </div>
  );
}
