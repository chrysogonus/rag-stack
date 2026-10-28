import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

let systemReduces = false
let stored: Record<string, string> = {}
let attribute = false

beforeEach(() => {
  vi.resetModules()
  systemReduces = false
  stored = {}
  attribute = false
  vi.stubGlobal('matchMedia', () => ({ matches: systemReduces, addEventListener: () => {} }))
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => stored[key] ?? null,
    setItem: (key: string, value: string) => (stored[key] = value),
  })
  vi.stubGlobal('document', {
    documentElement: { toggleAttribute: (_: string, on: boolean) => (attribute = on) },
  })
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('motion', () => {
  it('follows the system setting until the switch is used', async () => {
    systemReduces = true
    const { isStill, startMotion } = await import('./motion')
    startMotion()
    expect(isStill()).toBe(true)
    expect(attribute).toBe(true)
  })

  it('lets the switch override the system, remembers it, and tells its listeners', async () => {
    systemReduces = true
    const { isStill, setMotion, subscribeMotion } = await import('./motion')
    const heard = vi.fn()
    subscribeMotion(heard)
    setMotion(true)
    expect(isStill()).toBe(false)
    expect(stored.motion).toBe('on')
    expect(attribute).toBe(false)
    expect(heard).toHaveBeenCalledOnce()

    vi.resetModules()
    systemReduces = false
    stored.motion = 'off'
    expect((await import('./motion')).isStill()).toBe(true)
  })

  it('keeps the choice for this page load when storage is blocked', async () => {
    vi.stubGlobal('localStorage', {
      getItem: () => {
        throw new Error('blocked')
      },
      setItem: () => {
        throw new Error('blocked')
      },
    })
    const { isStill, setMotion } = await import('./motion')
    expect(isStill()).toBe(false)
    setMotion(false)
    expect(isStill()).toBe(true)
  })
})
