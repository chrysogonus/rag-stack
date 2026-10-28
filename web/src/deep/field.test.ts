import { describe, expect, it } from 'vitest'
import { DEPTH, galaxy, starField } from './field'

describe('the deep field', () => {
  it('is the same on every visit', () => {
    expect(starField(50, 400)).toEqual(starField(50, 400))
    expect(galaxy(50, 170)).toEqual(galaxy(50, 170))
  })

  it('keeps its stars inside the tube and clear of the camera', () => {
    const { positions } = starField(2000, 400)
    for (let i = 0; i < positions.length; i += 3) {
      const r = Math.hypot(positions[i], positions[i + 1])
      expect(r).toBeGreaterThanOrEqual(6 - 1e-4)
      expect(r).toBeLessThanOrEqual(400 + 1e-4)
      expect(positions[i + 2]).toBeGreaterThanOrEqual(0)
      expect(positions[i + 2]).toBeLessThan(DEPTH)
    }
  })

  it('runs the galaxy from core to rim', () => {
    const { reach } = galaxy(2000, 170)
    expect(Math.min(...reach)).toBeGreaterThanOrEqual(0)
    expect(Math.max(...reach)).toBeLessThanOrEqual(1)
  })
})
