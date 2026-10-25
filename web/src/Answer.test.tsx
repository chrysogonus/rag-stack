import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { Answer } from './Answer'

const render = (content: string) =>
  renderToStaticMarkup(<Answer content={content} index={0} live={false} sky={{ current: null }} />)

describe('Answer', () => {
  it('renders a Markdown table inside a scroll container', () => {
    const html = render('| Risk | Mitigation |\n|---|---|\n| LLM01 | Least privilege |')

    expect(html).toContain('<div class="table-scroll"><table>')
    expect(html).toContain('<td>Least privilege</td>')
  })

  it('keeps single tildes as text', () => {
    expect(render('It takes ~7 s instead of ~45 s.')).not.toContain('<del>')
  })
})
