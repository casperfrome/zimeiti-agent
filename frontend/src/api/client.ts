const BASE = '/api'

async function handle<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    const text = await resp.text().catch(() => '')
    let detail = text
    try { detail = JSON.parse(text).detail ?? text } catch {}
    throw new Error(detail || `HTTP ${resp.status}`)
  }
  if (resp.status === 204) return undefined as T
  return resp.json() as Promise<T>
}

export const api = {
  get:    <T>(p: string)              => fetch(`${BASE}${p}`).then(handle<T>),
  post:   <T>(p: string, body?: any)  => fetch(`${BASE}${p}`, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body ?? {}) }).then(handle<T>),
  put:    <T>(p: string, body?: any)  => fetch(`${BASE}${p}`, { method: 'PUT',  headers: {'Content-Type':'application/json'}, body: JSON.stringify(body ?? {}) }).then(handle<T>),
  delete: <T>(p: string)              => fetch(`${BASE}${p}`, { method: 'DELETE' }).then(handle<T>),
}

/** Stream SSE events from a POST endpoint. Calls onEvent for each {event,data} pair. */
export async function streamSSE(
  path: string,
  body: any,
  onEvent: (event: string, data: any) => void,
  signal?: AbortSignal,
) {
  const resp = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body ?? {}),
    signal,
  })
  if (!resp.ok || !resp.body) {
    const text = await resp.text().catch(() => '')
    throw new Error(text || `HTTP ${resp.status}`)
  }
  const reader = resp.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buf = ''
  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    let idx: number
    while ((idx = buf.indexOf('\n\n')) !== -1) {
      const block = buf.slice(0, idx)
      buf = buf.slice(idx + 2)
      let event = 'message'
      let data = ''
      for (const line of block.split('\n')) {
        if (line.startsWith('event:')) event = line.slice(6).trim()
        else if (line.startsWith('data:')) data += line.slice(5).trim()
      }
      let parsed: any = data
      try { parsed = JSON.parse(data) } catch {}
      onEvent(event, parsed)
    }
  }
}
