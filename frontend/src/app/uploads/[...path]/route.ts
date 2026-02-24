import { type NextRequest } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

export async function GET(req: NextRequest): Promise<Response> {
  const { pathname, search } = req.nextUrl;
  const upstream = await fetch(`${BACKEND_URL}${pathname}${search}`);
  return new Response(upstream.body, {
    status: upstream.status,
    headers: upstream.headers,
  });
}
