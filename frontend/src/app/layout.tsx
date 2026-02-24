import type { Metadata } from 'next';
import Script from 'next/script';
import { ToastContainer } from '@/components/ui/Toast';
import './globals.css';

export const metadata: Metadata = {
  title: 'Webtoon Review Chatbot',
  description: '웹툰 리뷰 챗봇 프로토타입',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <head>
        <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
        <link rel="preconnect" href="https://cdn.jsdelivr.net" crossOrigin="anonymous" />
        <link rel="preconnect" href="https://cubism.live2d.com" crossOrigin="anonymous" />
        <link
          rel="stylesheet"
          as="style"
          crossOrigin="anonymous"
          href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css"
        />
      </head>
      <body>
        {/* Cubism SDK 4 Core — 채팅 페이지에서만 사용되지만 전역 로드 (afterInteractive로 비블로킹) */}
        <Script
          src="https://cubism.live2d.com/sdk-web/cubismcore/live2dcubismcore.min.js"
          strategy="afterInteractive"
        />
        {children}
        <ToastContainer />
      </body>
    </html>
  );
}
