import { hash, random } from '../sky/layout'

/** How deep the star tube runs ahead of the camera; stars that pass the camera wrap back to its far end. */
export const DEPTH = 800

export interface StarField {
  /** x, y across the tube; z is the star's resting distance in [0, DEPTH). */
  positions: Float32Array
  sizes: Float32Array
  phases: Float32Array
  /** Picks the colour in the shader: mostly starlight, some glint, a few ember. */
  tints: Float32Array
}

/** Stars filling a tube around the line of sight, clear of a narrow core so none fly through the camera. */
export function starField(count: number, radius: number): StarField {
  const next = random(hash('deep field'))
  const positions = new Float32Array(count * 3)
  const sizes = new Float32Array(count)
  const phases = new Float32Array(count)
  const tints = new Float32Array(count)
  const core = 6
  for (let i = 0; i < count; i++) {
    // Uniform over the annulus' area, so the outer field isn't sparser than the middle.
    const r = Math.sqrt(next() * (radius ** 2 - core ** 2) + core ** 2)
    const angle = next() * Math.PI * 2
    positions.set([Math.cos(angle) * r, Math.sin(angle) * r, next() * DEPTH], i * 3)
    sizes[i] = 0.9 + next() ** 8 * 5
    phases[i] = next()
    tints[i] = next()
  }
  return { positions, sizes, phases, tints }
}

export interface Galaxy {
  /** In the galaxy's own plane (y is its thickness), before tilt and placement. */
  positions: Float32Array
  sizes: Float32Array
  /** 0 at the core, 1 at the rim: colour runs from ember to glint, and inner stars orbit faster. */
  reach: Float32Array
}

/** A barred, three-armed spiral: dense warm core, cool scattered arms. */
export function galaxy(count: number, radius: number, arms = 3): Galaxy {
  const next = random(hash('galaxy'))
  const positions = new Float32Array(count * 3)
  const sizes = new Float32Array(count)
  const reach = new Float32Array(count)
  for (let i = 0; i < count; i++) {
    const t = next() ** 1.7
    const r = t * radius
    const angle = ((i % arms) / arms) * Math.PI * 2 + t * 5.5
    // Scatter grows towards the rim, and falls off sharply so the arms keep their edges.
    const scatter = () => (next() - 0.5) * next() ** 3 * radius * (0.12 + t * 0.5)
    positions.set(
      [Math.cos(angle) * r + scatter(), scatter() * (0.6 - t * 0.4), Math.sin(angle) * r + scatter()],
      i * 3,
    )
    sizes[i] = 0.8 + next() ** 4 * 2.4
    reach[i] = t
  }
  return { positions, sizes, reach }
}
