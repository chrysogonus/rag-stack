import { describe, expect, it } from 'vitest'
import { scramble } from './musing'

describe('scramble', () => {
  it('keeps the revealed prefix and the spaces, and replaces the rest with hex', () => {
    const out = scramble('Salting the hashes', 4, () => 0.99)
    expect(out).toBe('Saltfff fff ffffff')
  })

  it('is the plain text once fully revealed', () => {
    expect(scramble('Phishing for context', 20)).toBe('Phishing for context')
  })
})
