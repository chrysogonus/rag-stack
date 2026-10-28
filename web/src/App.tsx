import { useEffect, useLayoutEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { Answer } from './Answer'
import { Musing } from './Musing'
import { getMessages, RefusedError, sendFeedback, sendMessage, stopped, type Message, type SourceRef } from './api'
import { rememberChat, type Chat } from './chats'
import { SOURCES } from './sky/layout'
import type { SkyRenderer } from './sky/renderer'
import { Sky } from './sky/Sky'

const MAX_CHARS = 4000 // matches the server's MAX_INPUT_CHARS default
const THREAD_KEY = 'rag-stack:thread'
const CHATS_KEY = 'rag-stack:chats'

const STARTERS = [
  { question: 'Which D3FEND techniques counter T1110.001?', source: 'd3fend' },
  { question: 'What is AML.T0051?', source: 'atlas' },
  { question: 'What does Article 50 of the EU AI Act require?', source: 'eu-ai-act' },
]

type Turn = Message & { sources?: SourceRef[] }

function storedThread(): string {
  try {
    const id = localStorage.getItem(THREAD_KEY)
    if (id) return id
  } catch {
    // storage blocked: fall back to a thread for this page view only
  }
  return openThread()
}

/** Makes `id` the current thread, so a reload comes back to it. */
function openThread(id: string = crypto.randomUUID()): string {
  try {
    localStorage.setItem(THREAD_KEY, id)
  } catch {
    // see storedThread
  }
  return id
}

function storedChats(): Chat[] {
  try {
    const chats = JSON.parse(localStorage.getItem(CHATS_KEY) ?? '[]')
    if (Array.isArray(chats)) return chats.filter((c) => typeof c?.id === 'string' && typeof c?.title === 'string')
  } catch {
    // storage blocked or corrupt: start an empty list
  }
  return []
}

function saveChats(chats: Chat[]) {
  try {
    localStorage.setItem(CHATS_KEY, JSON.stringify(chats))
  } catch {
    // see storedThread
  }
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
  const [chats, setChats] = useState(storedChats)
  const [messages, setMessages] = useState<Turn[]>([])
  const [loading, setLoading] = useState(true)
  const [streaming, setStreaming] = useState(false)
  const [draft, setDraft] = useState('')
  const [error, setError] = useState<string | null>(null)
  // The question whose answer failed part-way, offered again next to the error.
  const [retry, setRetry] = useState<string | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [loadAttempt, setLoadAttempt] = useState(0)
  const [announcement, setAnnouncement] = useState('')
  const abortRef = useRef<AbortController | null>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const fieldRef = useRef<HTMLDivElement>(null)
  const stickRef = useRef(true)
  const skyRef = useRef<SkyRenderer | null>(null)
  const chatsRef = useRef<HTMLElement>(null)
  const mastheadRef = useRef<HTMLElement>(null)
  const composerRef = useRef<HTMLFormElement>(null)
  const newThreadRef = useRef<string | null>(null)
  // The entrance plays once per page load, not again for every new chat.
  const [intro, setIntro] = useState(true)

  useEffect(() => {
    const timer = setTimeout(() => setIntro(false), 2600)
    return () => clearTimeout(timer)
  }, [])

  useEffect(() => {
    // A chat this page just started has no history; loading [] late would erase a first question.
    if (threadId === newThreadRef.current) return setLoading(false)
    const controller = new AbortController()
    getMessages(threadId, controller.signal)
      .then((loaded) => {
        setMessages(loaded)
        // Lists a chat started before saved chats existed, without reordering known ones.
        const first = loaded.find((m) => m.role === 'user')
        if (first) setChats((c) => (c.some((chat) => chat.id === threadId) ? c : rememberChat(c, threadId, first.content)))
      })
      .catch((e: Error) => {
        if (!controller.signal.aborted) setLoadError(e.message)
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [threadId, loadAttempt])

  // Focus and anchor jumps stop clear of the sticky bars at their current height (a long draft or
  // an error makes the composer taller).
  useEffect(() => {
    const root = document.documentElement
    const observer = new ResizeObserver(() => {
      root.style.setProperty('--masthead-height', `${mastheadRef.current?.offsetHeight ?? 0}px`)
      root.style.setProperty('--composer-height', `${composerRef.current?.offsetHeight ?? 0}px`)
    })
    for (const bar of [mastheadRef.current, composerRef.current]) if (bar) observer.observe(bar)
    return () => observer.disconnect()
  }, [])

  useEffect(() => saveChats(chats), [chats])
  // Tabs and browser history tell chats apart by their first question.
  const title = chats.find((chat) => chat.id === threadId)?.title
  useEffect(() => {
    document.title = title ? `${title} · Knowledge base` : 'Knowledge base'
  }, [title])
  // Another tab saved a chat: adopt its list, so this tab's next save doesn't drop it.
  useEffect(() => {
    const onStorage = (e: StorageEvent) => e.key === CHATS_KEY && setChats(storedChats())
    window.addEventListener('storage', onStorage)
    return () => window.removeEventListener('storage', onStorage)
  }, [])

  // Follow the answer as it streams, unless the reader has scrolled up to read.
  useEffect(() => {
    const onScroll = () => (stickRef.current = nearBottom())
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])
  useLayoutEffect(() => {
    if (stickRef.current && messages.length) window.scrollTo({ top: document.documentElement.scrollHeight })
  }, [messages])

  // Escape stops the answer, unless it is closing the chats list.
  useEffect(() => {
    if (!streaming) return
    const onKeyDown = (e: globalThis.KeyboardEvent) => {
      if (e.key === 'Escape' && !document.querySelector(':popover-open')) abortRef.current?.abort()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [streaming])

  function showThread(id: string) {
    abortRef.current?.abort()
    skyRef.current?.reset()
    setThreadId(openThread(id))
    setMessages([])
    setError(null)
    setRetry(null)
    setLoadError(null)
    setDraft('')
    inputRef.current?.focus()
  }

  function retryLoad() {
    setLoadError(null)
    setLoading(true)
    setLoadAttempt((n) => n + 1)
  }

  function startNewChat() {
    newThreadRef.current = crypto.randomUUID()
    showThread(newThreadRef.current)
  }

  function switchChat(id: string) {
    chatsRef.current?.hidePopover()
    if (id === threadId) return
    newThreadRef.current = null // it has history by now, so load it
    setLoading(true)
    showThread(id)
  }

  // Each streamed chunk sends a mote of light from a retrieved passage to the writing caret.
  function feedCaret() {
    const caret = centre(document.querySelector('.answer.live .caret'))
    const column = document.querySelector('.answer.live')?.getBoundingClientRect()
    if (caret && column) skyRef.current?.emit(caret, column)
  }

  // Until the first words arrive, the lit passages keep pouring light into the waiting star.
  const last = messages.at(-1)
  const gathering = streaming && last?.role === 'assistant' && !last.content && !!last.sources
  useEffect(() => {
    if (!gathering) return
    const timer = setInterval(feedCaret, 120)
    return () => clearInterval(timer)
  }, [gathering])

  async function send(content: string) {
    const question = content.trim()
    // While a chat loads (or failed to), its history would overwrite the new turn.
    if (!question || streaming || loading || loadError) return
    const sky = skyRef.current
    const controller = new AbortController()
    abortRef.current = controller
    stickRef.current = true
    setError(null)
    setRetry(null)
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
            // The server accepted the turn, so this thread is now worth coming back to.
            setChats((c) => rememberChat(c, threadId, question))
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
        updateAnswer((a) => ({ content: stopped(a.content) }))
      } else if (e instanceof RefusedError) {
        // Nothing was saved: take the question back out and return it to the composer.
        setMessages((m) => m.slice(0, -2))
        setDraft(question)
        setError(e.message)
      } else {
        // The server kept what was streamed, marked the same way; offer the question again.
        updateAnswer((a) => ({ content: stopped(a.content) }))
        setRetry(question)
        setError(e instanceof TypeError ? 'The connection dropped before the answer was finished.' : (e as Error).message)
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
    // On a touch keyboard Enter adds a line (there is no Shift+Enter); the Send button sends.
    if (matchMedia('(pointer: coarse)').matches) return
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      void send(draft)
    }
  }

  const empty = !loading && !loadError && messages.length === 0
  const showCount = draft.length > MAX_CHARS * 0.8

  return (
    <div className={['shell', intro && 'intro', messages.length && 'chatting'].filter(Boolean).join(' ')}>
      <a className="skip" href="#question">
        Skip to question
      </a>
      <Sky rendererRef={skyRef} />
      <header className="masthead" ref={mastheadRef}>
        <span className="wordmark">Knowledge base</span>
        <div className="actions">
          {chats.length > 0 && (
            <button type="button" className="quiet" popoverTarget="chats">
              Chats
            </button>
          )}
          {(!empty || streaming) && (
            <button type="button" className="quiet" onClick={startNewChat}>
              New chat
            </button>
          )}
        </div>
        <nav id="chats" className="chats" ref={chatsRef} popover="auto" aria-label="Saved chats">
          <ul>
            {chats.map((chat) => (
              <li key={chat.id}>
                <button
                  type="button"
                  aria-current={chat.id === threadId || undefined}
                  onClick={() => switchChat(chat.id)}
                >
                  {chat.title}
                </button>
              </li>
            ))}
          </ul>
        </nav>
      </header>

      <main className="thread" aria-busy={loading || streaming}>
        {messages.length > 0 && <h1 className="visually-hidden">Conversation</h1>}
        {loadError && (
          <section className="welcome">
            <h1>Couldn’t load this chat</h1>
            <p>{loadError}</p>
            <div className="actions">
              <button type="button" className="primary" onClick={retryLoad}>
                Try again
              </button>
              <button type="button" className="quiet" onClick={startNewChat}>
                Start a new chat
              </button>
            </div>
          </section>
        )}
        {empty && (
          <section className="welcome">
            <h1>What do you want to know about cybersecurity?</h1>
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
            <h2 key={i} className="question">
              <span className="visually-hidden">You asked: </span>
              {message.content}
            </h2>
          ) : (
            <Answer
              key={i}
              index={i}
              content={message.content}
              sources={message.sources}
              live={streaming && i === messages.length - 1}
              sky={skyRef}
              onFeedback={(helpful) => sendFeedback(threadId, i, helpful)}
            />
          ),
        )}
        <div className="visually-hidden" role="status">
          {announcement}
        </div>
      </main>

      <form className="composer" ref={composerRef} onSubmit={onSubmit}>
        {error && (
          <p className="error" role="alert">
            {error}
            {retry && !streaming && (
              <button type="button" className="quiet" onClick={() => void send(retry)}>
                Try again
              </button>
            )}
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
            placeholder="Ask about cybersecurity"
            aria-describedby={showCount ? 'count' : undefined}
            autoFocus
          />
          {streaming ? (
            <button type="button" className="primary" onClick={() => abortRef.current?.abort()}>
              Stop
            </button>
          ) : (
            <button type="submit" className="primary" disabled={!draft.trim() || loading || !!loadError}>
              Send
            </button>
          )}
        </div>
        <p className="hint">
          {showCount ? (
            <span id="count">
              {draft.length.toLocaleString()} of {MAX_CHARS.toLocaleString()} characters
            </span>
          ) : streaming ? (
            <Musing />
          ) : (
            <>
              <span className="keys">Enter to send, Shift+Enter for a new line. </span>
              Don’t share personal information.
            </>
          )}
        </p>
      </form>
    </div>
  )
}
