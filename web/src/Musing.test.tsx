import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import { Musing } from './Musing'

vi.mock('./motion', () => ({ useStill: () => true }))

describe('Musing', () => {
  it('says one of the phrases it is given', () => {
    expect(renderToStaticMarkup(<Musing phrases={['Turning the pages']} />)).toContain('Turning the pages…')
  })
})
