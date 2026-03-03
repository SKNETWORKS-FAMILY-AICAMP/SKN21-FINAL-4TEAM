'use client';

import { useEffect, useRef } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, Swords } from 'lucide-react';
import { useDebateStore } from '@/stores/debateStore';
import { DebateViewer } from '@/components/debate/DebateViewer';
import { FightingHPBar } from '@/components/debate/FightingHPBar';
import { Scorecard } from '@/components/debate/Scorecard';
import { ShareButton } from '@/components/debate/ShareButton';
import { SummaryReport } from '@/components/debate/SummaryReport';
import { PredictionPanel } from '@/components/debate/PredictionPanel';
import { SkeletonCard } from '@/components/ui/Skeleton';

const STATUS_LABELS: Record<string, string> = {
  pending: '대기',
  in_progress: '진행 중',
  completed: '종료',
  error: '오류',
  waiting_agent: '에이전트 대기',
  forfeit: '몰수패',
};

const STATUS_CLASSES: Record<string, string> = {
  pending: 'bg-gray-500/20 text-gray-400',
  in_progress: 'bg-yellow-500/20 text-yellow-400',
  completed: 'bg-green-500/20 text-green-400',
  error: 'bg-red-500/20 text-red-400',
  waiting_agent: 'bg-blue-500/20 text-blue-400',
  forfeit: 'bg-red-500/20 text-red-400',
};

export default function MatchPage() {
  const { id } = useParams<{ id: string }>();
  const { currentMatch, turns, fetchMatch, replayMode } = useDebateStore();
  const scorecardRef = useRef<HTMLDivElement>(null);
  const prevStatusRef = useRef<string | undefined>(undefined);

  useEffect(() => {
    fetchMatch(id);
  }, [id, fetchMatch]);

  // pending/waiting_agent 상태일 때 폴링 — in_progress 전환을 감지해 SSE를 자동 연결
  useEffect(() => {
    if (!currentMatch) return;
    if (!['pending', 'waiting_agent'].includes(currentMatch.status)) return;

    const interval = setInterval(() => fetchMatch(id), 3000);
    return () => clearInterval(interval);
  }, [currentMatch?.status, id, fetchMatch]);

  // 토론 완료 시 스코어카드로 스크롤 (in_progress → completed 전환 감지)
  useEffect(() => {
    if (prevStatusRef.current === 'in_progress' && currentMatch?.status === 'completed') {
      setTimeout(() => {
        scorecardRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 600);
    }
    prevStatusRef.current = currentMatch?.status;
  }, [currentMatch?.status]);

  if (!currentMatch) {
    return (
      <div className="max-w-[700px] mx-auto py-6 px-4">
        <SkeletonCard />
        <SkeletonCard />
      </div>
    );
  }

  const isCompleted = currentMatch.status === 'completed';
  const isForfeit = currentMatch.status === 'forfeit';

  // ELO 필드 접근을 위한 타입 확장
  const match = currentMatch as typeof currentMatch & {
    elo_a_before?: number | null;
    elo_b_before?: number | null;
    elo_a_after?: number | null;
    elo_b_after?: number | null;
  };

  // HP 계산: 진행 중엔 패널티+턴 진행도 기반, 완료 시엔 최종 점수 사용
  const penaltiesA = turns
    .filter((t) => t.speaker === 'agent_a')
    .reduce((s, t) => s + t.penalty_total, 0);
  const penaltiesB = turns
    .filter((t) => t.speaker === 'agent_b')
    .reduce((s, t) => s + t.penalty_total, 0);
  const attrition = turns.length; // 완료된 턴당 1 HP 자연 감소 (긴장감 연출)

  const hpA = isCompleted
    ? currentMatch.score_a
    : Math.max(20, 100 - attrition - penaltiesA);
  const hpB = isCompleted
    ? currentMatch.score_b
    : Math.max(20, 100 - attrition - penaltiesB);

  const isWinnerA = (isCompleted || isForfeit) && currentMatch.winner_id === currentMatch.agent_a.id;
  const isWinnerB = (isCompleted || isForfeit) && currentMatch.winner_id === currentMatch.agent_b.id;

  // 종료 배너 결정
  const showBanner = isCompleted || isForfeit;
  let bannerText = '';
  let bannerClass = '';
  if (showBanner) {
    if (isForfeit) {
      const winnerName = isWinnerA ? currentMatch.agent_a.name : currentMatch.agent_b.name;
      bannerText = `토론 종료 — ${winnerName} 부전승`;
      bannerClass = 'bg-red-500/20 border-b border-red-500/30';
    } else if (currentMatch.winner_id === currentMatch.agent_a.id) {
      bannerText = `토론 종료 — ${currentMatch.agent_a.name} 승리!`;
      bannerClass = 'bg-yellow-500/20 border-b border-yellow-500/30';
    } else if (currentMatch.winner_id === currentMatch.agent_b.id) {
      bannerText = `토론 종료 — ${currentMatch.agent_b.name} 승리!`;
      bannerClass = 'bg-yellow-500/20 border-b border-yellow-500/30';
    } else {
      bannerText = '토론 종료 — 무승부';
      bannerClass = 'bg-gray-500/20 border-b border-gray-500/30';
    }
  }

  // ELO 변동 계산
  const eloDeltaA =
    match.elo_a_after != null && match.elo_a_before != null
      ? match.elo_a_after - match.elo_a_before
      : null;
  const eloDeltaB =
    match.elo_b_after != null && match.elo_b_before != null
      ? match.elo_b_after - match.elo_b_before
      : null;

  return (
    // -m-4 md:-m-6: main의 padding을 상쇄해 sticky 헤더가 화면 최상단에 정확히 고정되도록 함
    <div className="-m-4 md:-m-6">
      {/* 종료 배너 — 최상단 고정 (배틀 헤더보다 위) */}
      {showBanner && (
        <div className={`sticky top-0 z-40 px-4 py-2 text-center text-sm font-semibold ${bannerClass}`}>
          <span>{bannerText}</span>
          {match.elo_a_after != null && (
            <span className="ml-4 inline-flex items-center gap-3 text-xs font-mono">
              <span>
                {currentMatch.agent_a.name}{' '}
                {eloDeltaA != null && (
                  <span className={eloDeltaA >= 0 ? 'text-green-400' : 'text-red-400'}>
                    {eloDeltaA >= 0 ? '+' : ''}
                    {eloDeltaA}
                  </span>
                )}
              </span>
              <span className="text-gray-500">|</span>
              <span>
                {currentMatch.agent_b.name}{' '}
                {eloDeltaB != null && (
                  <span className={eloDeltaB >= 0 ? 'text-green-400' : 'text-red-400'}>
                    {eloDeltaB >= 0 ? '+' : ''}
                    {eloDeltaB}
                  </span>
                )}
              </span>
            </span>
          )}
        </div>
      )}

      {/* 배틀 헤더 — 항상 화면 상단 고정 (sticky top-0) */}
      <div
        className="sticky top-0 z-30 bg-gradient-to-b from-gray-900 via-gray-800 to-gray-900
          border-b border-gray-700/50 shadow-lg shadow-black/40"
      >
        <div className="max-w-[700px] mx-auto px-5 pt-4 pb-4">
          {/* HP 게이지 영역 */}
          <div className="flex items-start gap-3">
            <FightingHPBar
              agentId={currentMatch.agent_a.id}
              agentName={currentMatch.agent_a.name}
              provider={currentMatch.agent_a.provider}
              hp={hpA}
              side="left"
              isWinner={isWinnerA}
              isCompleted={isCompleted || isForfeit}
              agentImageUrl={currentMatch.agent_a.image_url}
            />

            {/* 중앙: 아이콘 + 상태 + 점수 */}
            <div className="flex flex-col items-center gap-1.5 shrink-0 pt-1">
              <Swords size={18} className="text-primary" />
              <span
                className={`text-[11px] px-2 py-0.5 rounded-full font-semibold whitespace-nowrap
                  ${STATUS_CLASSES[currentMatch.status] ?? 'bg-gray-500/20 text-gray-400'}`}
              >
                {STATUS_LABELS[currentMatch.status] ?? currentMatch.status}
              </span>
              {isCompleted && (
                <span className="text-sm font-mono font-bold text-gray-100 mt-0.5">
                  {hpA} <span className="text-gray-600 font-normal">:</span> {hpB}
                </span>
              )}
              {!isCompleted && turns.length > 0 && (
                <span className="text-[11px] font-mono text-gray-500">{turns.length}턴</span>
              )}
            </div>

            <FightingHPBar
              agentId={currentMatch.agent_b.id}
              agentName={currentMatch.agent_b.name}
              provider={currentMatch.agent_b.provider}
              hp={hpB}
              side="right"
              isWinner={isWinnerB}
              isCompleted={isCompleted || isForfeit}
              agentImageUrl={currentMatch.agent_b.image_url}
            />
          </div>

          {/* 토론 주제 */}
          <div className="mt-3 pt-3 border-t border-gray-700/50 text-center">
            <p className="text-[10px] text-gray-500 uppercase tracking-widest mb-1">토론 주제</p>
            <h1 className="text-sm font-bold text-white leading-snug">
              「{currentMatch.topic_title}」
            </h1>
          </div>
        </div>
      </div>

      {/* 스크롤 콘텐츠 영역 */}
      <div className="max-w-[700px] mx-auto px-4 pt-4 pb-6">
        {/* 뒤로가기 — 스크롤 시 사라지는 내비게이션 */}
        <Link
          href="/debate"
          className="flex items-center gap-1 text-sm text-text-muted no-underline hover:text-text mb-4"
        >
          <ArrowLeft size={14} />
          토론 목록
        </Link>

        {/* 토론 뷰어 */}
        <div className="mb-4">
          <DebateViewer match={currentMatch} />
        </div>

        {/* 진행 중 매치: 예측 투표 */}
        {currentMatch.status === 'in_progress' && (
          <PredictionPanel
            matchId={currentMatch.id}
            agentAName={currentMatch.agent_a.name}
            agentBName={currentMatch.agent_b.name}
            turnCount={turns.length}
          />
        )}

        {/* 완료된 매치: 공유 버튼 (리플레이 시작은 DebateViewer 내부에 위치) */}
        {currentMatch.status === 'completed' && (
          <div className="flex items-center gap-2 mb-4">
            <ShareButton
              url={`${typeof window !== 'undefined' ? window.location.origin : ''}/debate/matches/${currentMatch.id}`}
              title={`AI 토론 결과: ${currentMatch.topic_title ?? 'AI 토론'}`}
            />
          </div>
        )}

        {/* 스코어카드 (완료된 매치, 리플레이 중 숨김) */}
        {currentMatch.status === 'completed' && !replayMode && (
          <div ref={scorecardRef}>
            <Scorecard
              matchId={currentMatch.id}
              agentA={currentMatch.agent_a}
              agentB={currentMatch.agent_b}
              penaltyA={currentMatch.penalty_a}
              penaltyB={currentMatch.penalty_b}
            />
            <SummaryReport matchId={currentMatch.id} />
          </div>
        )}
      </div>
    </div>
  );
}
