import { describe, expect, it } from 'vitest'
import { CITE, groupEntries, linkCitations, splitFooter, splitNotes } from './answer'

const FOOTER =
  '\n\n---\n**Sources**\n\n' +
  '- [AML.T0051](https://atlas.mitre.org/techniques/AML.T0051) LLM Prompt Injection. MITRE ATLAS™, Apache-2.0\n' +
  '- [AI Act Art. 50(1)](https://eur-lex.europa.eu/x) Transparency obligations. © European Union\n\n' +
  'Source versions: MITRE ATLAS 2026.09\n\n' +
  '*AI-generated answer (EU AI Act Art. 50(1)). Check the cited sources.*'

describe('splitFooter', () => {
  it('separates the answer from its source entries and notes', () => {
    const { body, footer } = splitFooter('Injection is bad [AML.T0051].' + FOOTER)

    expect(body).toBe('Injection is bad [AML.T0051].')
    expect(footer?.heading).toBe('Sources')
    expect(footer?.entries).toEqual([
      {
        id: 'AML.T0051',
        url: 'https://atlas.mitre.org/techniques/AML.T0051',
        text: 'LLM Prompt Injection. MITRE ATLAS™, Apache-2.0',
      },
      { id: 'AI Act Art. 50(1)', url: 'https://eur-lex.europa.eu/x', text: 'Transparency obligations. © European Union' },
    ])
    expect(footer?.notes).toBe(
      'Source versions: MITRE ATLAS 2026.09\n\n*AI-generated answer (EU AI Act Art. 50(1)). Check the cited sources.*',
    )
  })

  it('leaves answers without a source list alone', () => {
    const abstention = "I can't answer that from the indexed sources.\n\nIndexed sources:\n\n- MITRE ATLAS 2026.09"
    expect(splitFooter(abstention)).toEqual({ body: abstention, footer: null })
    expect(splitFooter('A rule\n\n---\n**bold** but no sources')).toEqual({
      body: 'A rule\n\n---\n**bold** but no sources',
      footer: null,
    })
  })

  it('uses the last footer when the answer itself contains a rule and bold text', () => {
    const { body } = splitFooter('Part one\n\n---\n**Part two**' + FOOTER)
    expect(body).toBe('Part one\n\n---\n**Part two**')
  })
})

describe('linkCitations', () => {
  const ids = new Set(['AML.T0051', 'LLM01', 'AI Act Art. 50(1)'])

  it('links bare citations, one link per known ID', () => {
    expect(linkCitations('See [AML.T0051] and [LLM01; AML.T0051].', ids)).toBe(
      `See [AML.T0051](${CITE}) and [LLM01](${CITE}); [AML.T0051](${CITE}).`,
    )
    expect(linkCitations('Per [AI Act Art. 50(1)].', ids)).toBe(`Per [AI Act Art. 50(1)](${CITE}).`)
  })

  it('leaves links, unknown brackets and code untouched', () => {
    const text = '[AML.T0051](https://x) [not a source] `[LLM01]`\n```\n[LLM01]\n```'
    expect(linkCitations(text, ids)).toBe(text)
  })
})

describe('groupEntries', () => {
  it('puts consecutive entries with the same description in one row', () => {
    const article = (n: number) => ({ id: `AI Act Art. 50(${n})`, url: 'https://eur-lex/x', text: 'Article 50 Transparency.' })
    const other = { id: 'AML.T0051', url: 'https://atlas/x', text: 'LLM Prompt Injection.' }

    expect(groupEntries([article(1), article(2), other, article(3)]).map((g) => g.map((e) => e.id))).toEqual([
      ['AI Act Art. 50(1)', 'AI Act Art. 50(2)'],
      ['AML.T0051'],
      ['AI Act Art. 50(3)'],
    ])
  })
})

describe('splitNotes', () => {
  it('separates the version line from the AI label, in either language', () => {
    expect(splitNotes('Quellenversionen: EU AI Act OJ 2024/1689\n\n*KI-generierte Antwort.*')).toEqual({
      versions: { label: 'Quellenversionen', value: 'EU AI Act OJ 2024/1689' },
      rest: '*KI-generierte Antwort.*',
    })
    expect(splitNotes('*AI-generated answer.*')).toEqual({ versions: null, rest: '*AI-generated answer.*' })
  })
})
