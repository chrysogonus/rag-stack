import { createContext, Fragment, use, useMemo, useState, type ComponentProps, type RefObject, type FocusEvent, type MouseEvent, type ReactNode } from 'react'
import Markdown, { type Components, type Options } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { CITE, groupEntries, linkCitations, splitFooter, splitNotes } from './answer'
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

const NewTab = () => <span className="visually-hidden"> (opens in new tab)</span>

const external = ({ node: _node, children, ...props }: { node?: unknown } & ComponentProps<'a'>) => (
  <a {...props} target="_blank" rel="noreferrer">
    {children}
    <NewTab />
  </a>
)

// Tables (comparisons) and other GitHub Markdown. Single tildes stay text: "~7 s" is not strikethrough.
const remarkPlugins: Options['remarkPlugins'] = [[remarkGfm, { singleTilde: false }]]

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
  // A wide table scrolls inside the answer instead of widening the page.
  table: ({ node: _node, ...props }) => (
    <div className="table-scroll">
      <table {...props} />
    </div>
  ),
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
        <NewTab />
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
  const notes = footer?.notes ? splitNotes(footer.notes) : null
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
    <article className={live ? 'answer live' : 'answer'} aria-label="Answer">
      <div className="answer-body">
        <CitingContext value={citing}>
          <Markdown remarkPlugins={remarkPlugins} components={components}>
            {linkCitations(body, ids)}
          </Markdown>
        </CitingContext>
        {live && !content && <Forming />}
        {live && <span className="caret" aria-hidden="true" />}
      </div>
      {footer && (
        <section className="catalogue" aria-label={footer.heading}>
          <h3>{footer.heading}</h3>
          <ul>
            {groupEntries(footer.entries).map((group) => (
              <li
                key={group[0].id}
                className={group.some((entry) => entry.id === active) ? 'active' : undefined}
              >
                <Star lit={group.some((entry) => byId.get(entry.id)?.used ?? true)} />
                <div>
                  {group.map((entry, i) => (
                    <Fragment key={entry.id}>
                      {i > 0 && ', '}
                      <a
                        id={anchor(entry.id)}
                        href={entry.url}
                        target="_blank"
                        rel="noreferrer"
                        {...pointing(entry.id)}
                      >
                        {entry.id}
                        <NewTab />
                      </a>
                    </Fragment>
                  ))}
                  <p>{group[0].text}</p>
                </div>
              </li>
            ))}
          </ul>
          {notes && (
            <div className="notes">
              {notes.versions && (
                <details>
                  <summary>{notes.versions.label}</summary>
                  {notes.versions.value}
                </details>
              )}
              <Markdown remarkPlugins={remarkPlugins} components={{ a: external }}>
                {notes.rest}
              </Markdown>
            </div>
          )}
        </section>
      )}
    </article>
  )
}
