'use client';

import { ArrowLeft } from 'lucide-react';
import Link from 'next/link';
import { AgentForm } from '@/components/debate/AgentForm';

export default function CreateAgentPage() {
  return (
    <div className="max-w-[700px] mx-auto py-6 px-4">
      <Link
        href="/debate/agents"
        className="flex items-center gap-1 text-sm text-text-muted no-underline hover:text-text mb-4"
      >
        <ArrowLeft size={14} />내 에이전트
      </Link>

      <h1 className="page-title mb-5">에이전트 생성</h1>
      <AgentForm />
    </div>
  );
}
