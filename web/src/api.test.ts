import { describe, expect, it } from 'vitest'
import { createSseParser, type SseEvent } from './api'

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
