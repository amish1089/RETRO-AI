import { NextRequest, NextResponse } from 'next/server'

const backend = process.env.RETRO_API_URL ?? 'http://localhost:8000'

async function forward(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params
  const target = `${backend.replace(/\/$/, '')}/${path.join('/')}`
  const body = request.method === 'GET' || request.method === 'HEAD' ? undefined : await request.text()
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 15_000)
  try {
    const response = await fetch(target, { method: request.method, headers: { 'content-type': 'application/json' }, body, signal: controller.signal, cache: 'no-store' })
    const text = await response.text()
    return new NextResponse(text, { status: response.status, headers: { 'content-type': response.headers.get('content-type') ?? 'application/json' } })
  } catch (error) {
    const message = error instanceof DOMException && error.name === 'AbortError' ? 'Retro backend timed out.' : 'Retro backend is offline.'
    return NextResponse.json({ detail: message }, { status: 503 })
  } finally { clearTimeout(timeout) }
}

export const GET = forward
export const POST = forward
