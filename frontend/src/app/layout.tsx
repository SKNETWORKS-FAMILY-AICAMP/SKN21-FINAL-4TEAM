import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Webtoon Review Chatbot',
  description: '웹툰 리뷰 챗봇 프로토타입',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
