/**
 * 백엔드 프록시 — 모든 /api/** 요청을 FastAPI로 전달.
 * Next.js rewrites()는 SSE 스트리밍을 버퍼링하므로 App Router API Route로 대체.
 */
import { type NextRequest } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

async function proxy(req: NextRequest): Promise<Response> {
  const { pathname, search } = req.nextUrl;
  const targetUrl = `${BACKEND_URL}${pathname}${search}`;

  // 요청 헤더 복사 (host 제외)
  const headers = new Headers();
  req.headers.forEach((value, key) => {
    if (key.toLowerCase() !== 'host') {
      headers.set(key, value);
    }
  });

  // 요청 바디 읽기 (스트리밍 없이 버퍼로)
  let body: ArrayBuffer | undefined;
  if (req.method !== 'GET' && req.method !== 'HEAD') {
    body = await req.arrayBuffer();
  }

  const upstream = await fetch(targetUrl, {
    method: req.method,
    headers,
    body: body && body.byteLength > 0 ? body : undefined,
  });

  // 응답 헤더 복사
  const responseHeaders = new Headers(upstream.headers);

  // SSE 등 스트리밍 응답: body를 그대로 파이핑
  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  });
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
export const OPTIONS = proxy;
