import { describe, expect, it } from 'vitest'
import { constellation, fitSky, narrowRows, passageOffset, passagePoint } from './layout'

const SOURCES = [
  'atlas',
  'attack',
  'capec',
  'cwe',
  'vulns',
  'd3fend',
  'owasp-llm-2026',
  'owasp-agentic-2026',
  'eu-ai-act',
  'ki-mig',
].map((id) => ({ id, label: id, short: id }))

describe('passage positions', () => {
  it('are the same on every visit and differ between passages', () => {
    expect(passageOffset('atlas', 'AML.T0051')).toEqual(passageOffset('atlas', 'AML.T0051'))
    expect(passageOffset('atlas', 'AML.T0051')).not.toEqual(passageOffset('atlas', 'AML.T0054'))
  })

  it.each([
    [1440, 900],
    [390, 844],
  ])('stay inside their constellation at %ix%i', (width, height) => {
    const sky = fitSky(SOURCES, width, height)
    for (const { id } of SOURCES) {
      const region = sky.regions.get(id)!
      const p = passagePoint(sky, width, height, id, `${id}-passage`)
      expect(Math.hypot(p.x - region.centre.x, p.y - region.centre.y)).toBeLessThanOrEqual(region.radius)
    }
  })

  it('place passages of unknown sources somewhere on screen', () => {
    const p = passagePoint(fitSky(SOURCES, 800, 600), 800, 600, 'new-source', 'X1')
    expect(p.x).toBeGreaterThanOrEqual(0)
    expect(p.x).toBeLessThan(800)
    expect(p.y).toBeGreaterThanOrEqual(0)
    expect(p.y).toBeLessThan(600)
  })
})

describe('the sky', () => {
  it('keeps constellations out of the reading column on wide screens', () => {
    const width = 1440
    const sky = fitSky(SOURCES, width, 900)
    expect(sky.wide).toBe(true)
    for (const region of sky.regions.values()) {
      const gap = Math.abs(region.centre.x - width / 2) - region.radius
      expect(gap).toBeGreaterThan(352) // half the 704px column
    }
  })

  it.each([
    [1440, 900],
    [1100, 700],
    [390, 844],
    [360, 640],
  ])('gives every source its own constellation, apart from the others, at %ix%i', (width, height) => {
    const regions = [...fitSky(SOURCES, width, height).regions.values()]
    expect(regions).toHaveLength(SOURCES.length)
    for (const [i, a] of regions.entries())
      for (const b of regions.slice(i + 1))
        expect(Math.hypot(a.centre.x - b.centre.x, a.centre.y - b.centre.y)).toBeGreaterThan(a.radius + b.radius)
  })

  it.each([1, 2, 3, 5])('fits a pack of %i sources on any screen', (count) => {
    const few = SOURCES.slice(0, count)
    for (const [width, height] of [
      [1440, 900],
      [390, 844],
    ]) {
      const regions = [...fitSky(few, width, height).regions.values()]
      expect(regions).toHaveLength(count)
      for (const { centre, radius } of regions) {
        expect(radius).toBeGreaterThan(0)
        expect(centre.x).toBeGreaterThan(0)
        expect(centre.x).toBeLessThan(width)
        expect(centre.y).toBeGreaterThan(0)
        expect(centre.y).toBeLessThan(height)
      }
      for (const [i, a] of regions.entries())
        for (const b of regions.slice(i + 1))
          expect(Math.hypot(a.centre.x - b.centre.x, a.centre.y - b.centre.y)).toBeGreaterThan(a.radius + b.radius)
    }
  })

  it('puts a constellation on the side its pack names, on wide screens', () => {
    const sided = [
      { id: 'a', label: 'a', short: 'a', side: 'right' as const },
      { id: 'b', label: 'b', short: 'b', side: 'right' as const },
      { id: 'c', label: 'c', short: 'c', side: 'right' as const },
      { id: 'd', label: 'd', short: 'd', side: 'left' as const },
    ]
    const { regions } = fitSky(sided, 1440, 900)

    expect(['a', 'b', 'c'].every((id) => regions.get(id)!.centre.x > 720)).toBe(true)
    expect(regions.get('d')!.centre.x).toBeLessThan(720)
    const [a, b, c] = ['a', 'b', 'c'].map((id) => regions.get(id)!)
    expect(b.centre.y - a.centre.y).toBeGreaterThan(a.radius * 2)
    expect(c.centre.y - b.centre.y).toBeGreaterThan(a.radius * 2)
    expect(c.centre.y + c.radius).toBeLessThan(900)
  })

  it('splits by position any source whose pack names no side', () => {
    const mixed = [
      { id: 'a', label: 'a', short: 'a' },
      { id: 'b', label: 'b', short: 'b', side: 'right' as const },
      { id: 'c', label: 'c', short: 'c', side: null },
      { id: 'd', label: 'd', short: 'd' },
    ]
    const { regions } = fitSky(mixed, 1440, 900)

    expect(regions.get('a')!.centre.x).toBeLessThan(720)
    expect(regions.get('b')!.centre.x).toBeGreaterThan(720)
    expect(regions.get('c')!.centre.x).toBeGreaterThan(720)
    expect(regions.get('d')!.centre.x).toBeGreaterThan(720)
  })

  it('fills narrow rows of at most four, fuller rows first', () => {
    expect(narrowRows(10)).toEqual([4, 3, 3])
    expect(narrowRows(6)).toEqual([3, 3])
    expect(narrowRows(4)).toEqual([4])
  })

  it('joins every figure star into one constellation', () => {
    for (const figure of SOURCES.map((s) => constellation(s.id, s.label, s.short))) {
      expect(figure.edges).toHaveLength(figure.stars.length - 1)
      const joined = new Set(figure.edges.flat())
      expect(joined.size).toBe(figure.stars.length)
    }
  })
})
