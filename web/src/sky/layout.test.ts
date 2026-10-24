import { describe, expect, it } from 'vitest'
import { CONSTELLATIONS, fitSky, passageOffset, passagePoint, SOURCES } from './layout'

describe('passage positions', () => {
  it('are the same on every visit and differ between passages', () => {
    expect(passageOffset('atlas', 'AML.T0051')).toEqual(passageOffset('atlas', 'AML.T0051'))
    expect(passageOffset('atlas', 'AML.T0051')).not.toEqual(passageOffset('atlas', 'AML.T0054'))
  })

  it.each([
    [1440, 900],
    [390, 844],
  ])('stay inside their constellation at %ix%i', (width, height) => {
    const sky = fitSky(width, height)
    for (const { id } of SOURCES) {
      const region = sky.regions.get(id)!
      const p = passagePoint(sky, width, height, id, `${id}-passage`)
      expect(Math.hypot(p.x - region.centre.x, p.y - region.centre.y)).toBeLessThanOrEqual(region.radius)
    }
  })

  it('place passages of unknown sources somewhere on screen', () => {
    const p = passagePoint(fitSky(800, 600), 800, 600, 'new-source', 'X1')
    expect(p.x).toBeGreaterThanOrEqual(0)
    expect(p.x).toBeLessThan(800)
    expect(p.y).toBeGreaterThanOrEqual(0)
    expect(p.y).toBeLessThan(600)
  })
})

describe('the sky', () => {
  it('keeps constellations out of the reading column on wide screens', () => {
    const width = 1440
    const sky = fitSky(width, 900)
    expect(sky.wide).toBe(true)
    for (const region of sky.regions.values()) {
      const gap = Math.abs(region.centre.x - width / 2) - region.radius
      expect(gap).toBeGreaterThan(352) // half the 704px column
    }
  })

  it('joins every figure star into one constellation', () => {
    for (const figure of CONSTELLATIONS) {
      expect(figure.edges).toHaveLength(figure.stars.length - 1)
      const joined = new Set(figure.edges.flat())
      expect(joined.size).toBe(figure.stars.length)
    }
  })
})
