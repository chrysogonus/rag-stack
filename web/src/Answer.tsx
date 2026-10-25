import { createContext, use, useMemo, useState, type ComponentProps, type RefObject, type FocusEvent, type MouseEvent, type ReactNode } from 'react'
import Markdown, { type Components } from 'react-markdown'
import { CITE, linkCitations, splitFooter } from './answer'
import type { SourceRef } from './api'
import { hash } from './sky/layout'
import type { SkyRenderer } from './sky/renderer'

interface Props {
  content: string
  /** The passages retrieved for this answer; only known while the page that asked it is open. */
  sources?: SourceRef[]
  /** Distinguishes this answer's footer anchors from other answers citing the same source. */
  index: number
  live: boolean
  sky: RefObject<SkyRenderer | null>
}

const external = ({ node: _node, ...props }: { node?: unknown } & ComponentProps<'a'>) => (
  <a {...props} target="_blank" rel="noreferrer" />
)

interface Citing {
  anchor: (id: string) => string | undefined
  pointing: (id: string) => object
  /** The passage a link cites: by its text when that is a source ID, else by its URL. */
  citedBy: (text: string | null, url: string | undefined) => string | undefined
}

// Context rather than a closure: a new `a` component every render would remount links and drop focus.
const CitingContext = createContext<Citing>({
  anchor: () => undefined,
  pointing: () => ({}),
  citedBy: () => undefined,
})

const components: Components = {
  a: function Link({ node: _node, href, children, ...props }) {
    const { anchor, pointing, citedBy } = use(CitingContext)
    const text = typeof children === 'string' ? children : null
    const id = citedBy(text, href)
    if (!id) return external({ href, children, ...props })
    if (href === CITE) {
      const target = anchor(id)
      return (
        <a className="cite" href={target && `#${target}`} {...pointing(id)}>
          {id}
        </a>
      )
    }
    // Answers also cite as [AML.T0051](https://…) or [any text](https://…): keep the link, tie it to its passage.
    return (
      <a className={text === id ? 'cite' : undefined} href={href} target="_blank" rel="noreferrer" {...pointing(id)}>
        {children as ReactNode}
      </a>
    )
  },
}

// The waiting answer: a small constellation that draws itself into the caret star.
const FORMING = [
  [4, 14],
  [17, 6],
  [30, 11],
  [44, 4],
]

function Forming() {
  return (
    <svg className="forming" viewBox="0 0 60 20" aria-hidden="true">
      <polyline points={`${FORMING.join(' ')} 60,10`} />
      {FORMING.map(([x, y]) => (
        <circle key={x} cx={x} cy={y} r="1.6" />
      ))}
    </svg>
  )
}

function Star({ lit }: { lit: boolean }) {
  return (
    <svg className={lit ? 'glyph lit' : 'glyph'} viewBox="0 0 16 16" aria-hidden="true">
      <path d="M8 0c.5 4.6 2.9 7 7.5 8-4.6 1-7 3.4-7.5 8-.5-4.6-2.9-7-7.5-8C5.1 7 7.5 4.6 8 0Z" />
    </svg>
  )
}

export function Answer({ content, sources, index, live, sky }: Props) {
  const [active, setActive] = useState<string | null>(null)
  const { body, footer } = useMemo(() => splitFooter(content), [content])
  const byId = useMemo(() => new Map(sources?.map((s) => [s.id, s])), [sources])
  const ids = useMemo(
    () => new Set([...(sources?.filter((s) => s.used).map((s) => s.id) ?? []), ...(footer?.entries.map((e) => e.id) ?? [])]),
    [sources, footer],
  )
  const anchor = (id: string) => `src-${index}-${hash(id).toString(36)}`

  // Pointing at a citation or a catalogue row ties it to its passage in the sky.
  const point = (id: string | null, el: Element | null) => {
    setActive(id)
    const ref = id ? byId.get(id) : undefined
    sky.current?.tether(ref?.source ?? null, id, el)
    sky.current?.highlight(ref?.source ?? null)
  }
  const pointing = (id: string) => ({
    onMouseEnter: (e: MouseEvent) => point(id, e.currentTarget),
    onMouseLeave: () => point(null, null),
    onFocus: (e: FocusEvent) => point(id, e.currentTarget),
    onBlur: () => point(null, null),
  })

  // The footer arrives with the last chunk, so a citation links to its entry once the answer is done.
  const citing: Citing = {
    anchor: (id) => (footer?.entries.some((e) => e.id === id) ? anchor(id) : undefined),
    pointing,
    citedBy: (text, url) =>
      text && ids.has(text)
        ? text
        : (footer?.entries.find((e) => e.url === url)?.id ?? sources?.find((s) => s.url === url)?.id),
  }

  return (
    <article className={live ? 'answer live' : 'answer'}>
      <div className="answer-body">
        <CitingContext value={citing}>
          <Markdown components={components}>{linkCitations(body, ids)}</Markdown>
        </CitingContext>
        {live && !content && <Forming />}
        {live && <span className="caret" aria-hidden="true" />}
      </div>
      {footer && (
        <section className="catalogue" aria-label={footer.heading}>
          <h2>{footer.heading}</h2>
          <ul>
            {footer.entries.map((entry) => (
              <li key={entry.id} id={anchor(entry.id)} className={active === entry.id ? 'active' : undefined}>
                <Star lit={byId.get(entry.id)?.used ?? true} />
                <div>
                  <a href={entry.url} target="_blank" rel="noreferrer" {...pointing(entry.id)}>
                    {entry.id}
                  </a>
                  <p>{entry.text}</p>
                </div>
              </li>
            ))}
          </ul>
          {footer.notes && (
            <div className="notes">
              <Markdown components={{ a: external }}>{footer.notes}</Markdown>
            </div>
          )}
        </section>
      )}
    </article>
  )
}
