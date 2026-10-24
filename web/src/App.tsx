import { useEffect, useLayoutEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import Markdown from 'react-markdown'
import { getMessages, RefusedError, sendMessage, type Message } from './api'

const MAX_CHARS = 4000 // matches the server's MAX_INPUT_CHARS default
const THREAD_KEY = 'rag-stack:thread'

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

export default function App() {
  const [threadId, setThreadId] = useState(storedThread)
  const [messages, setMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(true)
  const [streaming, setStreaming] = useState(false)
  const [draft, setDraft] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [announcement, setAnnouncement] = useState('')
  const abortRef = useRef<AbortController | null>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const stickRef = useRef(true)

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
    if (stickRef.current) window.scrollTo({ top: document.documentElement.scrollHeight })
  }, [messages])

  function startNewChat() {
    abortRef.current?.abort()
    setThreadId(newThread())
    setMessages([])
    setError(null)
    setDraft('')
    inputRef.current?.focus()
  }

  async function send(content: string) {
    const question = content.trim()
    if (!question || streaming) return
    const controller = new AbortController()
    abortRef.current = controller
    stickRef.current = true
    setError(null)
    setDraft('')
    setStreaming(true)
    setAnnouncement('')
    setMessages((m) => [...m, { role: 'user', content: question }, { role: 'assistant', content: '' }])
    // A no-op once "New chat" has replaced the conversation this answer belonged to.
    const updateAnswer = (update: (answer: string) => string) =>
      setMessages((m) => {
        const last = m.at(-1)
        return last?.role === 'assistant' ? [...m.slice(0, -1), { role: 'assistant', content: update(last.content) }] : m
      })

    try {
      const reply = await sendMessage(threadId, question, (text) => updateAnswer((a) => a + text), controller.signal)
      updateAnswer(() => reply.content)
      setAnnouncement('Answer ready.')
    } catch (e) {
      if (controller.signal.aborted) {
        updateAnswer((a) => a || '_Stopped._')
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
    <div className="shell">
      <header className="masthead">
        <span className="wordmark">Knowledge base</span>
        <button type="button" className="quiet" onClick={startNewChat} disabled={empty && !streaming}>
          New chat
        </button>
      </header>

      <main className="thread" aria-busy={loading || streaming}>
        {empty && (
          <section className="welcome">
            <h1>What would you like to know?</h1>
            <p>
              Ask a question in your own words. Answers come from an AI model and can be wrong, so check anything
              important.
            </p>
          </section>
        )}
        {messages.map((message, i) => {
          const live = streaming && i === messages.length - 1
          return message.role === 'user' ? (
            <p key={i} className="question">
              {message.content}
            </p>
          ) : (
            <article key={i} className={live ? 'answer live' : 'answer'}>
              <Markdown
                components={{ a: ({ node: _node, ...props }) => <a {...props} target="_blank" rel="noreferrer" /> }}
              >
                {message.content}
              </Markdown>
              {live && <span className="caret" aria-hidden="true" />}
            </article>
          )
        })}
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
        <div className="field">
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
            placeholder="Ask a question"
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
