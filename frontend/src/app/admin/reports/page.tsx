'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { DataTable } from '@/components/admin/DataTable';
import { toast } from '@/stores/toastStore';

type Report = {
  id: number;
  persona_id: string;
  persona_name: string | null;
  reporter_id: string;
  reporter_nickname: string | null;
  reason: string;
  description: string | null;
  status: string;
  admin_note: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  created_at: string;
};

type ReportStats = {
  pending: number;
  reviewed: number;
  dismissed: number;
  total: number;
};

const REASON_LABELS: Record<string, string> = {
  inappropriate: '부적절',
  sexual: '성적 콘텐츠',
  harassment: '괴롭힘',
  copyright: '저작권',
  spam: '스팸',
  other: '기타',
};

const STATUS_LABELS: Record<string, string> = {
  pending: '대기',
  reviewed: '처리됨',
  dismissed: '기각',
};

export default function AdminReportsPage() {
  const [reports, setReports] = useState<Report[]>([]);
  const [stats, setStats] = useState<ReportStats | null>(null);
  const [filter, setFilter] = useState<string>('pending');
  const [loading, setLoading] = useState(true);
  const [selectedReport, setSelectedReport] = useState<Report | null>(null);
  const [actionNote, setActionNote] = useState('');
  const [acting, setActing] = useState(false);
  const [banDays, setBanDays] = useState<number | null>(7);

  const fetchData = () => {
    setLoading(true);
    const statusParam = filter === 'all' ? '' : `?status=${filter}`;
    Promise.all([
      api.get<{ items: Report[]; total: number }>(`/admin/reports${statusParam}`),
      api.get<ReportStats>('/admin/reports/stats'),
    ])
      .then(([res, statsRes]) => {
        setReports(res.items ?? []);
        setStats(statsRes);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchData();
  }, [filter]);

  const handleAction = async (reportId: number, action: 'dismiss' | 'takedown' | 'ban_creator') => {
    setActing(true);
    try {
      await api.put(`/admin/reports/${reportId}/action`, {
        action,
        admin_note: actionNote.trim() || null,
        ...(action === 'ban_creator' ? { ban_days: banDays } : {}),
      });
      const banLabel = banDays ? `${banDays}일` : '영구';
      toast.success(
        action === 'dismiss'
          ? '신고를 기각했습니다'
          : action === 'takedown'
            ? '페르소나를 내렸습니다'
            : `생성자를 ${banLabel} 밴했습니다`,
      );
      setSelectedReport(null);
      setActionNote('');
      setBanDays(7);
      fetchData();
    } catch {
      toast.error('처리에 실패했습니다');
    } finally {
      setActing(false);
    }
  };

  const statusColor: Record<string, string> = {
    pending: 'bg-warning',
    reviewed: 'bg-success',
    dismissed: 'bg-text-muted',
  };

  const columns = [
    {
      key: 'created_at' as const,
      label: '시간',
      render: (val: unknown) => {
        const d = new Date(String(val));
        return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours()}:${String(d.getMinutes()).padStart(2, '0')}`;
      },
    },
    { key: 'persona_name' as const, label: '페르소나' },
    { key: 'reporter_nickname' as const, label: '신고자' },
    {
      key: 'reason' as const,
      label: '사유',
      render: (val: unknown) => REASON_LABELS[String(val)] ?? String(val),
    },
    {
      key: 'status' as const,
      label: '상태',
      render: (val: unknown) => (
        <span className={`badge ${statusColor[String(val)] ?? 'bg-text-muted'}`}>
          {STATUS_LABELS[String(val)] ?? String(val)}
        </span>
      ),
    },
  ];

  const filterTabs = [
    { key: 'all', label: '전체', count: stats?.total },
    { key: 'pending', label: '대기', count: stats?.pending },
    { key: 'reviewed', label: '처리됨', count: stats?.reviewed },
    { key: 'dismissed', label: '기각', count: stats?.dismissed },
  ];

  return (
    <div>
      <h1 className="page-title">신고 관리</h1>

      {/* 필터 탭 */}
      <div className="flex gap-2 mb-4">
        {filterTabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setFilter(tab.key)}
            className={`py-2 px-4 rounded-lg text-[13px] cursor-pointer transition-colors duration-200 flex items-center gap-1.5 ${
              filter === tab.key
                ? 'bg-primary text-white border border-primary'
                : 'bg-bg-surface text-text border border-border-input'
            }`}
          >
            {tab.label}
            {tab.count != null && tab.count > 0 && (
              <span
                className={`text-[11px] px-1.5 py-0.5 rounded-full ${
                  filter === tab.key ? 'bg-white/20' : 'bg-primary/10 text-primary'
                }`}
              >
                {tab.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* 테이블 */}
      <div className="card">
        <DataTable
          columns={columns}
          data={reports}
          loading={loading}
          onRowClick={(row) => setSelectedReport(row)}
        />
      </div>

      {/* 상세 모달 */}
      {selectedReport && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/50" onClick={() => { setSelectedReport(null); setActionNote(''); }} />
          <div className="relative bg-bg-surface rounded-2xl border border-border w-full max-w-[500px] mx-4 p-6 max-h-[80vh] overflow-y-auto">
            <h2 className="text-lg font-semibold text-text mb-4">신고 상세</h2>

            <div className="space-y-3 mb-5">
              <div className="flex justify-between">
                <span className="text-sm text-text-muted">페르소나</span>
                <span className="text-sm text-text font-medium">{selectedReport.persona_name ?? '-'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-text-muted">신고자</span>
                <span className="text-sm text-text">{selectedReport.reporter_nickname ?? '-'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-text-muted">사유</span>
                <span className="text-sm text-text">{REASON_LABELS[selectedReport.reason] ?? selectedReport.reason}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-text-muted">상태</span>
                <span className={`badge ${statusColor[selectedReport.status] ?? 'bg-text-muted'}`}>
                  {STATUS_LABELS[selectedReport.status] ?? selectedReport.status}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-text-muted">신고 시각</span>
                <span className="text-sm text-text">{new Date(selectedReport.created_at).toLocaleString('ko-KR')}</span>
              </div>
              {selectedReport.description && (
                <div>
                  <span className="text-sm text-text-muted block mb-1">상세 설명</span>
                  <p className="text-sm text-text bg-bg-hover p-3 rounded-lg m-0">{selectedReport.description}</p>
                </div>
              )}
              {selectedReport.admin_note && (
                <div>
                  <span className="text-sm text-text-muted block mb-1">관리자 메모</span>
                  <p className="text-sm text-text bg-bg-hover p-3 rounded-lg m-0">{selectedReport.admin_note}</p>
                </div>
              )}
            </div>

            {selectedReport.status === 'pending' && (
              <>
                <textarea
                  value={actionNote}
                  onChange={(e) => setActionNote(e.target.value)}
                  placeholder="관리자 메모 (선택)"
                  rows={2}
                  className="input w-full mb-4 resize-none text-sm"
                />

                <div className="mb-3">
                  <span className="text-sm text-text-muted block mb-1.5">밴 기간 (생성자 밴 시 적용)</span>
                  <div className="flex gap-1.5">
                    {[
                      { value: 7, label: '7일' },
                      { value: 30, label: '30일' },
                      { value: 90, label: '90일' },
                      { value: null as number | null, label: '영구' },
                    ].map((opt) => (
                      <button
                        key={opt.label}
                        type="button"
                        onClick={() => setBanDays(opt.value)}
                        className={`py-1.5 px-3 rounded-lg text-xs cursor-pointer transition-colors ${
                          banDays === opt.value
                            ? 'bg-danger text-white border border-danger'
                            : 'bg-bg-hover text-text-secondary border border-border'
                        }`}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="flex gap-2">
                  <button
                    onClick={() => handleAction(selectedReport.id, 'dismiss')}
                    disabled={acting}
                    className="flex-1 py-2 px-3 rounded-lg border border-border bg-transparent text-text-secondary text-sm cursor-pointer hover:bg-bg-hover transition-colors disabled:opacity-50"
                  >
                    기각
                  </button>
                  <button
                    onClick={() => handleAction(selectedReport.id, 'takedown')}
                    disabled={acting}
                    className="flex-1 py-2 px-3 rounded-lg border-none bg-warning text-white text-sm font-medium cursor-pointer hover:bg-warning/90 transition-colors disabled:opacity-50"
                  >
                    콘텐츠 내리기
                  </button>
                  <button
                    onClick={() => handleAction(selectedReport.id, 'ban_creator')}
                    disabled={acting}
                    className="flex-1 py-2 px-3 rounded-lg border-none bg-danger text-white text-sm font-medium cursor-pointer hover:bg-danger/90 transition-colors disabled:opacity-50"
                  >
                    생성자 밴 ({banDays ? `${banDays}일` : '영구'})
                  </button>
                </div>
              </>
            )}

            {selectedReport.status !== 'pending' && (
              <button
                onClick={() => { setSelectedReport(null); setActionNote(''); }}
                className="w-full py-2 px-4 rounded-lg border border-border bg-transparent text-text text-sm cursor-pointer hover:bg-bg-hover transition-colors"
              >
                닫기
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
