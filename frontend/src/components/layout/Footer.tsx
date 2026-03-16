'use client';

import { ChevronUp } from 'lucide-react';

export function Footer() {
  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <footer className="w-full border-t border-gray-100 bg-white py-14 px-4 md:px-8 mt-16 pb-20">
      <div className="max-w-[960px] mx-auto flex flex-col md:flex-row justify-between items-start md:items-center gap-8">
        <div className="space-y-4">
          <span className="text-2xl font-black text-black tracking-tighter leading-none">NEMo</span>
          <div className="text-[13px] text-gray-400 space-y-1 font-bold">
            <p>서울시 금천구 가산디지털1로 25</p>
            <p>010 - 1234 - 5678</p>
          </div>
        </div>
        
        <button
          onClick={scrollToTop}
          className="w-12 h-12 rounded-full brutal-border flex items-center justify-center bg-white hover:bg-gray-50 transition-all brutal-shadow-sm active:shadow-none active:translate-x-[1px] active:translate-y-[1px]"
          aria-label="맨 위로"
        >
          <ChevronUp size={24} strokeWidth={2.5} className="text-black" />
        </button>
      </div>
    </footer>
  );
}
