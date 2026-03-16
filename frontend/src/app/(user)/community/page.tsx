import React from 'react';
import { Users } from 'lucide-react';

export default function CommunityPage() {
  return (
    <div className="max-w-[800px] mx-auto py-10 px-4">
      <div className="flex flex-col items-center justify-center text-center py-20 bg-bg-surface border border-border rounded-3xl">
        <div className="w-16 h-16 rounded-2xl bg-nemo/10 flex items-center justify-center mb-6">
          <Users size={32} className="text-nemo" />
        </div>
        <h1 className="text-3xl font-bold text-text mb-4">커뮤니티</h1>
        <p className="text-text-muted max-w-md mx-auto leading-relaxed">
          자유롭게 사용자들과 소통할 수 있는 커뮤니티 공간입니다.<br />
          (현재 준비 중인 하드코딩된 페이지입니다)
        </p>
      </div>
    </div>
  );
}
