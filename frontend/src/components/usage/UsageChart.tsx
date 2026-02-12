'use client';

type Props = {
  data: Array<{ date: string; cost: number; tokens: number }>;
};

export function UsageChart({ data }: Props) {
  return (
    <div className="usage-chart">
      {/* 일별/월별 사용량 차트 */}
    </div>
  );
}
