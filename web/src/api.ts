export interface Message {
  role: 'user' | 'assistant'
  content: string
}

export interface SseEvent {
  event: string
  data: string
}

/** Thrown when the server refuses a message before answering; nothing was saved. */
export class RefusedError extends Error {}

/** Feeds text chunks in, calls `onEvent` for every complete server-sent event. */
export function createSseParser(onEvent: (event: SseEvent) => void): (chunk: string) => void {
  let buffer = ''
  return (chunk) => {
    buffer += chunk.replace(/\r\n/g, '\n')
    let end
    while ((end = buffer.indexOf('\n\n')) !== -1) {
      const block = buffer.slice(0, end)
      buffer = buffer.slice(end + 2)
      let event = 'message'
      const data: string[] = []
      for (const line of block.split('\n')) {
        if (line.startsWith(':')) continue // comment, e.g. keep-alive ping
        const colon = line.indexOf(':')
        const field = colon === -1 ? line : line.slice(0, colon)
        const value = colon === -1 ? '' : line.slice(colon + 1).replace(/^ /, '')
        if (field === 'event') event = value
        else if (field === 'data') data.push(value)
      }
      if (data.length) onEvent({ event, data: data.join('\n') })
    }
  }
}

const threadUrl = (threadId: string) => `/api/threads/${threadId}/messages`

async function refusal(response: Response): Promise<string> {
  if (response.status === 422) return 'Your message is empty or too long. Shorten it and send again.'
  try {
    const { detail } = await response.json()
    if (typeof detail === 'string') return detail
  } catch {
    // fall through to the generic message
  }
  return 'The assistant is unavailable right now. Try again in a moment.'
}

export async function getMessages(threadId: string, signal?: AbortSignal): Promise<Message[]> {
  const response = await fetch(threadUrl(threadId), { signal })
  if (!response.ok) throw new Error(await refusal(response))
  return response.json()
}

/** Sends a question and streams the answer. Resolves with the saved assistant message. */
export async function sendMessage(
  threadId: string,
  content: string,
  onDelta: (text: string) => void,
  signal?: AbortSignal,
): Promise<Message> {
  const response = await fetch(threadUrl(threadId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
    signal,
  })
  if (!response.ok || !response.body) throw new RefusedError(await refusal(response))

  let reply: Message | undefined
  let failure: string | undefined
  const parse = createSseParser(({ event, data }) => {
    const payload = JSON.parse(data)
    if (event === 'delta') onDelta(payload.text)
    else if (event === 'done') reply = payload.message
    else if (event === 'error') failure = payload.detail
  })
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    parse(value)
  }
  if (failure) throw new Error(failure)
  if (!reply) throw new Error('The answer was cut off. Ask again to get a full answer.')
  return reply
}
