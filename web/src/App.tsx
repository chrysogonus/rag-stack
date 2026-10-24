import { useEffect, useLayoutEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { Answer } from './Answer'
import { getMessages, RefusedError, sendMessage, type Message, type SourceRef } from './api'
import { SOURCES } from './sky/layout'
import type { SkyRenderer } from './sky/renderer'
import { Sky } from './sky/Sky'

const MAX_CHARS = 4000 // matches the server's MAX_INPUT_CHARS default
const THREAD_KEY = 'rag-stack:thread'

const STARTERS = [
  { question: 'What is AML.T0051?', source: 'atlas' },
  { question: 'What does Article 50 of the EU AI Act require?', source: 'eu-ai-act' },
  { question: 'Which risks does the OWASP agentic Top 10 list?', source: 'owasp-agentic-2026' },
]

type Turn = Message & { sources?: SourceRef[] }

function storedThread(): string {
  try {
    const id = localStorage.getItem(THREAD_KEY)
    if (id) return id
  } catch {
    // storage blocked: fall back to a thread for this page view only
  }
  return newThread()
}

function newThread(): string {
  const id = crypto.randomUUID()
  try {
    localStorage.setItem(THREAD_KEY, id)
  } catch {
    // see storedThread
  }
  return id
}

function nearBottom(): boolean {
  return window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 96
}

function centre(el: Element | null) {
  const rect = el?.getBoundingClientRect()
  return rect ? { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 } : null
}

export default function App() {
  const [threadId, setThreadId] = useState(storedThread)
  const [messages, setMessages] = useState<Turn[]>([])
  const [loading, setLoading] = useState(true)
  const [streaming, setStreaming] = useState(false)
  const [draft, setDraft] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [announcement, setAnnouncement] = useState('')
  const abortRef = useRef<AbortController | null>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const fieldRef = useRef<HTMLDivElement>(null)
  const stickRef = useRef(true)
  const skyRef = useRef<SkyRenderer | null>(null)
  // The entrance plays once per page load, not again for every new chat.
  const [intro, setIntro] = useState(true)

  useEffect(() => {
    const timer = setTimeout(() => setIntro(false), 2600)
    return () => clearTimeout(timer)
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    getMessages(threadId, controller.signal)
      .then(setMessages)
      .catch((e: Error) => {
        if (!controller.signal.aborted) setError(`Couldn't load this conversation. ${e.message}`)
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [threadId])

  // Follow the answer as it streams, unless the reader has scrolled up to read.
  useEffect(() => {
    const onScroll = () => (stickRef.current = nearBottom())
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])
  useLayoutEffect(() => {
    if (stickRef.current && messages.length) window.scrollTo({ top: document.documentElement.scrollHeight })
  }, [messages])

  function startNewChat() {
    abortRef.current?.abort()
    skyRef.current?.reset()
    setThreadId(newThread())
    setMessages([])
    setError(null)
    setDraft('')
    inputRef.current?.focus()
  }

  // Each streamed chunk sends a mote of light from a retrieved passage to the writing caret.
  function feedCaret() {
    const caret = centre(document.querySelector('.answer.live .caret'))
    if (caret) skyRef.current?.emit(caret)
  }

  async function send(content: string) {
    const question = content.trim()
    if (!question || streaming) return
    const sky = skyRef.current
    const controller = new AbortController()
    abortRef.current = controller
    stickRef.current = true
    setError(null)
    setDraft('')
    setStreaming(true)
    setAnnouncement('')
    sky?.highlight(null)
    const origin = centre(fieldRef.current)
    if (origin) sky?.search(origin)
    setMessages((m) => [...m, { role: 'user', content: question }, { role: 'assistant', content: '' }])
    // A no-op once "New chat" has replaced the conversation this answer belonged to.
    const updateAnswer = (update: (answer: Turn) => Partial<Turn>) =>
      setMessages((m) => {
        const last = m.at(-1)
        return last?.role === 'assistant' ? [...m.slice(0, -1), { ...last, ...update(last) }] : m
      })

    try {
      const reply = await sendMessage(
        threadId,
        question,
        {
          onSources: (sources) => {
            if (controller.signal.aborted) return
            sky?.ignite(sources)
            updateAnswer(() => ({ sources }))
          },
          onDelta: (text) => {
            updateAnswer((a) => ({ content: a.content + text }))
            feedCaret()
          },
        },
        controller.signal,
      )
      updateAnswer(() => ({ content: reply.content }))
      setAnnouncement('Answer ready.')
    } catch (e) {
      if (controller.signal.aborted) {
        updateAnswer((a) => ({ content: a.content || '_Stopped._' }))
      } else if (e instanceof RefusedError) {
        // Nothing was saved: take the question back out and return it to the composer.
        setMessages((m) => m.slice(0, -2))
        setDraft(question)
        setError(e.message)
      } else {
        setMessages((m) => (m.at(-1)?.content === '' ? m.slice(0, -1) : m))
        setError(e instanceof TypeError ? "Couldn't reach the assistant. Check your connection and try again." : (e as Error).message)
      }
    } finally {
      sky?.stopSearching()
      setStreaming(false)
      abortRef.current = null
      inputRef.current?.focus()
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    void send(draft)
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      void send(draft)
    }
  }

  const empty = !loading && messages.length === 0
  const showCount = draft.length > MAX_CHARS * 0.8

  return (
    <div className={['shell', intro && 'intro', messages.length && 'chatting'].filter(Boolean).join(' ')}>
      <Sky rendererRef={skyRef} />
      <header className="masthead">
        <span className="wordmark">Knowledge base</span>
        <button type="button" className="quiet" onClick={startNewChat} disabled={empty && !streaming}>
          New chat
        </button>
      </header>

      <main className="thread" aria-busy={loading || streaming}>
        {empty && (
          <section className="welcome">
            <h1>What do you want to know about AI security?</h1>
            <p>
              Each constellation is one source. When you ask, the passages behind the answer light up. Answers come
              from an AI model and can be wrong, so check anything important.
            </p>
            <ul className="visually-hidden" aria-label="Sources">
              {SOURCES.map((s) => (
                <li key={s.id}>{s.label}</li>
              ))}
            </ul>
            <ul className="starters" aria-label="Example questions">
              {STARTERS.map(({ question, source }) => (
                <li key={question}>
                  <button
                    type="button"
                    onClick={() => void send(question)}
                    onMouseEnter={() => skyRef.current?.highlight(source)}
                    onMouseLeave={() => skyRef.current?.highlight(null)}
                    onFocus={() => skyRef.current?.highlight(source)}
                    onBlur={() => skyRef.current?.highlight(null)}
                  >
                    {question}
                  </button>
                </li>
              ))}
            </ul>
          </section>
        )}
        {messages.map((message, i) =>
          message.role === 'user' ? (
            <p key={i} className="question">
              {message.content}
            </p>
          ) : (
            <Answer
              key={i}
              index={i}
              content={message.content}
              sources={message.sources}
              live={streaming && i === messages.length - 1}
              sky={skyRef}
            />
          ),
        )}
        <div className="visually-hidden" role="status">
          {announcement}
        </div>
      </main>

      <form className="composer" onSubmit={onSubmit}>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        <div className="field" ref={fieldRef}>
          <label htmlFor="question" className="visually-hidden">
            Your question
          </label>
          <textarea
            id="question"
            ref={inputRef}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={onKeyDown}
            maxLength={MAX_CHARS}
            rows={1}
            placeholder="Ask about AI security"
            aria-describedby={showCount ? 'count' : undefined}
            autoFocus
          />
          {streaming ? (
            <button type="button" className="primary" onClick={() => abortRef.current?.abort()}>
              Stop
            </button>
          ) : (
            <button type="submit" className="primary" disabled={!draft.trim()}>
              Send
            </button>
          )}
        </div>
        <p className="hint">
          {showCount ? (
            <span id="count">
              {draft.length.toLocaleString()} of {MAX_CHARS.toLocaleString()} characters
            </span>
          ) : (
            'Enter to send, Shift+Enter for a new line. Don’t share personal information.'
          )}
        </p>
      </form>
    </div>
  )
}
