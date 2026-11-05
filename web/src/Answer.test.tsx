import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import { Answer } from './Answer'

// The motion store has no server snapshot, and these render on the server.
vi.mock('./motion', async (original) => ({ ...(await original<typeof import('./motion')>()), useStill: () => true }))

const render = (content: string) =>
  renderToStaticMarkup(<Answer content={content} catalog={[]} index={0} live={false} sky={{ current: null }} />)

describe('Answer', () => {
  it('names the sources it is reading by their labels in the catalog', () => {
    const passage = { id: 'n1', title: 'A note', source: 'notes', url: 'https://example.org/n1', used: true }
    const waiting = renderToStaticMarkup(
      <Answer
        content=""
        sources={[passage]}
        catalog={[{ id: 'notes', label: 'Team notes', short: 'Notes' }]}
        index={1}
        live
        sky={{ current: null }}
      />,
    )

    expect(waiting).toContain('Reading 1 passage from Team notes')
  })

  it('renders a Markdown table inside a scroll container', () => {
    const html = render('| Risk | Mitigation |\n|---|---|\n| LLM01 | Least privilege |')

    expect(html).toContain('<div class="table-scroll"><table>')
    expect(html).toContain('<td>Least privilege</td>')
  })

  it('offers a rating only for a finished answer when it can be sent', () => {
    const send = async () => {}
    const rated = (content: string, live: boolean) =>
      renderToStaticMarkup(
        <Answer content={content} catalog={[]} index={1} live={live} sky={{ current: null }} onFeedback={send} />,
      )

    expect(rated('An answer.', false)).toContain('aria-label="Rate this answer"')
    expect(rated('An answer.', true)).not.toContain('Rate this answer')
    expect(rated('Part of an answer.\n\n_Stopped._', false)).not.toContain('Rate this answer')
    expect(render('An answer.')).not.toContain('Rate this answer')
  })

  it('gives each word of a live answer its own span, but leaves links and code whole', () => {
    const live = renderToStaticMarkup(
      <Answer content={'Use `rate limits` and [MFA](https://example.org) now.'} catalog={[]} index={0} live sky={{ current: null }} />,
    )

    expect(live).toContain('<span class="w">Use</span> <code>rate limits</code>')
    expect(live).toContain('<a href="https://example.org" target="_blank" rel="noreferrer">MFA')
    expect(live).toContain('<span class="w">now.</span>')
    expect(render('Use it now.')).not.toContain('class="w"')
  })

  it('keeps single tildes as text', () => {
    expect(render('It takes ~7 s instead of ~45 s.')).not.toContain('<del>')
  })
})
