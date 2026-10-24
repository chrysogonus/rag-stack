import { afterEach, describe, expect, it, vi } from 'vitest'
import { createSseParser, sendMessage, type SseEvent } from './api'

function parseAll(chunks: string[]): SseEvent[] {
  const events: SseEvent[] = []
  const parse = createSseParser((e) => events.push(e))
  chunks.forEach(parse)
  return events
}

describe('createSseParser', () => {
  it('parses named events', () => {
    expect(parseAll(['event: delta\ndata: {"text":"Hi"}\n\nevent: done\ndata: {}\n\n'])).toEqual([
      { event: 'delta', data: '{"text":"Hi"}' },
      { event: 'done', data: '{}' },
    ])
  })

  it('reassembles events split across chunks, including inside the separator', () => {
    const stream = 'event: delta\ndata: {"text":"Hello"}\n\nevent: delta\ndata: {"text":" there"}\n\n'
    const chunks = [stream.slice(0, 7), stream.slice(7, 35), stream.slice(35, 36), stream.slice(36)]
    expect(parseAll(chunks)).toEqual([
      { event: 'delta', data: '{"text":"Hello"}' },
      { event: 'delta', data: '{"text":" there"}' },
    ])
  })

  it('ignores keep-alive comments and waits for a complete event', () => {
    expect(parseAll([': ping\n\n', 'event: delta\ndata: {}\n'])).toEqual([])
  })

  it('joins multi-line data and accepts CRLF line endings', () => {
    expect(parseAll(['data: a\r\ndata: b\r\n\r\n'])).toEqual([{ event: 'message', data: 'a\nb' }])
  })
})

describe('sendMessage', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('reports the retrieved sources before the answer streams', async () => {
    const source = { id: 'AML.T0051', title: 'LLM Prompt Injection', source: 'atlas', url: 'https://x', used: true }
    const body = [
      `event: sources\ndata: ${JSON.stringify({ sources: [source] })}\n\n`,
      'event: delta\ndata: {"text":"Hi"}\n\n',
      'event: done\ndata: {"message":{"role":"assistant","content":"Hi"}}\n\n',
    ].join('')
    vi.stubGlobal('fetch', async () => new Response(body, { headers: { 'Content-Type': 'text/event-stream' } }))
    const seen: unknown[] = []

    const reply = await sendMessage('t', 'Hi', {
      onSources: (sources) => seen.push(['sources', sources]),
      onDelta: (text) => seen.push(['delta', text]),
    })

    expect(seen).toEqual([
      ['sources', [source]],
      ['delta', 'Hi'],
    ])
    expect(reply).toEqual({ role: 'assistant', content: 'Hi' })
  })
})
