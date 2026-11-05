import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import App from './App'

// The motion store has no server snapshot, and these render on the server.
vi.mock('./motion', async (original) => ({ ...(await original<typeof import('./motion')>()), useStill: () => true }))

const CONFIG = {
  title: 'Team notes',
  heading: 'What about the notes?',
  intro: 'Each constellation is one source.',
  placeholder: 'Ask about the notes',
  max_input_chars: 123,
  sources: [{ id: 'notes', label: 'The notes', short: 'Notes' }],
  starters: [{ question: 'What is in the notes?', source: 'notes' }],
  musings: ['Turning the pages'],
}

describe('App', () => {
  it('takes its name, placeholder and input limit from the config', () => {
    const html = renderToStaticMarkup(<App config={CONFIG} />)

    expect(html).toContain('<span class="wordmark">Team notes</span>')
    expect(html).toContain('placeholder="Ask about the notes"')
    expect(html).toContain('maxLength="123"')
    expect(html).not.toContain('cybersecurity')
  })
})
