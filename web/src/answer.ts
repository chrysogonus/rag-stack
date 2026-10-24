// Reads the source footer the server appends to every answer (see agent/answer.py `footer`).

/** Matches `FOOTER_START` in src/rag_stack/agent/answer.py. */
const FOOTER_START = '\n\n---\n**'
const ENTRY = /^- \[([^\]\n]+)\]\((\S+?)\) ?(.*)$/

export interface FooterEntry {
  id: string
  url: string
  /** Title and attribution, as the server wrote them. */
  text: string
}

export interface Footer {
  heading: string
  entries: FooterEntry[]
  /** Everything after the entries (source versions, the AI-generated notice), as Markdown. */
  notes: string
}

/** Splits an answer into its body and source footer; the footer always comes last. */
export function splitFooter(content: string): { body: string; footer: Footer | null } {
  const start = content.lastIndexOf(FOOTER_START)
  if (start === -1) return { body: content, footer: null }
  const lines = content.slice(start + FOOTER_START.length - 2).split('\n')
  const heading = lines[0].replace(/^\*\*|\*\*$/g, '')
  const entries: FooterEntry[] = []
  const notes: string[] = []
  for (const line of lines.slice(1)) {
    const entry = ENTRY.exec(line)
    if (entry) entries.push({ id: entry[1], url: entry[2], text: entry[3] })
    else notes.push(line)
  }
  if (!entries.length) return { body: content, footer: null }
  return { body: content.slice(0, start), footer: { heading, entries, notes: notes.join('\n').trim() } }
}

/** The link target that marks a citation for the Markdown renderer. */
export const CITE = '#cite'

const CODE = /(```[\s\S]*?(?:```|$)|`[^`\n]*`)/
const BRACKETED = /(?<![\]!\\])\[([^[\]\n]{2,80})\](?![([])/g

/** Turns bare citations like `[AML.T0051]` or `[LLM01, AML.T0051]` into links, outside code. */
export function linkCitations(body: string, ids: Set<string>): string {
  return body
    .split(CODE)
    .map((part, i) =>
      i % 2
        ? part
        : part.replace(BRACKETED, (whole, inner: string) => {
            const parts = inner.split(/([,;]\s*)/)
            if (!parts.some((p) => ids.has(p.trim()))) return whole
            return parts.map((p) => (ids.has(p.trim()) ? `[${p.trim()}](${CITE})` : p)).join('')
          }),
    )
    .join('')
}
