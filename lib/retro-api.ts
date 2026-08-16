export type RetroMessage = { role: 'user' | 'retro'; text: string; time: string; tags?: string[] }
export type RetroSystem = { os?: string; model?: string; cwd?: string; safe_modes?: string[]; brightness: number; volume: number }
export type RetroQueueItem = { label: string; type: string; payload?: Record<string, unknown>; status?: string; created_at?: string }

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/retro/${path}`, { ...init, headers: { 'content-type': 'application/json', ...init?.headers }, cache: 'no-store' })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(data.detail || 'Retro could not complete that request.')
  return data as T
}

export const retroApi = {
  chat: (message: string, context: number[] | null) => request<{ reply: string; context: number[] | null; model: string }>('api/chat', { method: 'POST', body: JSON.stringify({ message, context }) }),
  system: () => request<RetroSystem>('api/system'),
  queue: () => request<{ items: RetroQueueItem[] }>('api/queue'),
  setBrightness: (value: number) => request('api/brightness', { method: 'POST', body: JSON.stringify({ value }) }),
  setVolume: (value: number) => request('api/volume', { method: 'POST', body: JSON.stringify({ value }) }),
  addQueue: (label: string, type = 'task') => request('api/queue', { method: 'POST', body: JSON.stringify({ label, type }) }),
  runQueue: () => request<{ result: string }>('api/queue/run', { method: 'POST' }),
  clearQueue: () => request('api/queue/clear', { method: 'POST' }),
}
