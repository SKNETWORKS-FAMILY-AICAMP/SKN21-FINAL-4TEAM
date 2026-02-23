'use client';

import { useState } from 'react';
import { Copy, Check, Wifi, WifiOff } from 'lucide-react';

type Props = {
  agentId: string;
  isConnected: boolean;
};

export function AgentConnectionGuide({ agentId, isConnected }: Props) {
  const [copied, setCopied] = useState<string | null>(null);

  const token = typeof window !== 'undefined' ? localStorage.getItem('token') ?? '' : '';
  const wsProtocol = typeof window !== 'undefined' && location.protocol === 'https:' ? 'wss' : 'ws';
  const host = typeof window !== 'undefined' ? location.host : 'localhost:8000';
  const wsUrl = `${wsProtocol}://${host}/ws/agent/${agentId}?token=${token}`;

  const handleCopy = async (text: string, label: string) => {
    await navigator.clipboard.writeText(text);
    setCopied(label);
    setTimeout(() => setCopied(null), 2000);
  };

  const pythonExample = `import asyncio
import json
import websockets

async def main():
    uri = "${wsUrl}"
    async with websockets.connect(uri) as ws:
        print("Connected!")
        while True:
            msg = json.loads(await ws.recv())
            if msg["type"] == "ping":
                await ws.send(json.dumps({"type": "pong"}))
            elif msg["type"] == "turn_request":
                response = {
                    "type": "turn_response",
                    "match_id": msg["match_id"],
                    "action": "argue",
                    "claim": "Your argument here",
                    "evidence": None,
                }
                await ws.send(json.dumps(response))

asyncio.run(main())`;

  return (
    <div className="rounded-xl border border-border bg-bg-surface p-4">
      <div className="flex items-center gap-2 mb-3">
        {isConnected ? (
          <Wifi size={16} className="text-green-500" />
        ) : (
          <WifiOff size={16} className="text-gray-400" />
        )}
        <span className="text-sm font-semibold text-text">
          WebSocket 연결 {isConnected ? '활성' : '대기 중'}
        </span>
        <span
          className={`inline-block w-2 h-2 rounded-full ${
            isConnected ? 'bg-green-500 animate-pulse' : 'bg-gray-400'
          }`}
        />
      </div>

      <div className="mb-3">
        <label className="text-xs font-semibold text-text-muted block mb-1">엔드포인트 URL</label>
        <div className="flex items-center gap-2">
          <code className="flex-1 text-xs bg-bg px-2 py-1.5 rounded border border-border break-all">
            {`${wsProtocol}://${host}/ws/agent/${agentId}?token=<JWT>`}
          </code>
          <button
            onClick={() =>
              handleCopy(`${wsProtocol}://${host}/ws/agent/${agentId}?token=<YOUR_JWT_TOKEN>`, 'url')
            }
            className="p-1.5 text-text-muted hover:text-primary transition-colors"
            title="URL 복사"
          >
            {copied === 'url' ? <Check size={14} /> : <Copy size={14} />}
          </button>
        </div>
      </div>

      <div className="mb-3">
        <label className="text-xs font-semibold text-text-muted block mb-1">JWT 토큰</label>
        <div className="flex items-center gap-2">
          <code className="flex-1 text-xs bg-bg px-2 py-1.5 rounded border border-border truncate">
            {token ? `${token.slice(0, 20)}...` : '(로그인 필요)'}
          </code>
          <button
            onClick={() => handleCopy(token, 'token')}
            className="p-1.5 text-text-muted hover:text-primary transition-colors"
            title="토큰 복사"
            disabled={!token}
          >
            {copied === 'token' ? <Check size={14} /> : <Copy size={14} />}
          </button>
        </div>
      </div>

      <details className="text-xs">
        <summary className="text-text-muted cursor-pointer hover:text-text transition-colors">
          Python 연결 예시 코드
        </summary>
        <div className="mt-2 relative">
          <pre className="bg-bg p-3 rounded border border-border overflow-x-auto text-[11px] leading-relaxed">
            {pythonExample}
          </pre>
          <button
            onClick={() => handleCopy(pythonExample, 'code')}
            className="absolute top-2 right-2 p-1 text-text-muted hover:text-primary transition-colors"
            title="코드 복사"
          >
            {copied === 'code' ? <Check size={12} /> : <Copy size={12} />}
          </button>
        </div>
      </details>
    </div>
  );
}
