// The sky's geometry: pure and deterministic, so a passage lights up in the same place every visit.

export interface Point {
  x: number
  y: number
}

export interface Constellation {
  source: string
  label: string
  /** For narrow screens, where up to four constellations share a row. */
  short: string
  /** Bright figure stars as offsets from the centre, in units of the region radius. */
  stars: (Point & { size: number })[]
  edges: [number, number][]
}

export interface Region {
  centre: Point
  radius: number
}

export interface BackgroundStar extends Point {
  size: number
  alpha: number
}

export interface Sky {
  regions: Map<string, Region>
  wide: boolean
}

// Order matters: wide screens put the first half left of the column (attacks and weaknesses),
// the rest right (defenses, guidance and law); narrow ones fill rows of four, then three, so the
// long labels sit in the rows of three.
export const SOURCES: { id: string; label: string; short: string }[] = [
  { id: 'atlas', label: 'MITRE ATLAS', short: 'ATLAS' },
  { id: 'attack', label: 'MITRE ATT&CK', short: 'ATT&CK' },
  { id: 'capec', label: 'MITRE CAPEC', short: 'CAPEC' },
  { id: 'cwe', label: 'MITRE CWE', short: 'CWE' },
  { id: 'vulns', label: 'Vulnerabilities', short: 'CVEs' },
  { id: 'd3fend', label: 'MITRE D3FEND', short: 'D3FEND' },
  { id: 'owasp-llm-2026', label: 'OWASP LLM Top 10', short: 'OWASP LLM' },
  { id: 'owasp-agentic-2026', label: 'OWASP Agentic Top 10', short: 'OWASP Agentic' },
  { id: 'eu-ai-act', label: 'EU AI Act', short: 'AI Act' },
  { id: 'ki-mig', label: 'KI-MIG', short: 'KI-MIG' },
]

/** FNV-1a: a stable 32-bit seed from a string. */
export function hash(text: string): number {
  let h = 0x811c9dc5
  for (let i = 0; i < text.length; i++) {
    h ^= text.charCodeAt(i)
    h = Math.imul(h, 0x01000193)
  }
  return h >>> 0
}

/** mulberry32: a small seeded generator of floats in [0, 1). */
export function random(seed: number): () => number {
  let a = seed
  return () => {
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

function inDisc(next: () => number, reach: number): Point {
  const r = Math.sqrt(next()) * reach
  const angle = next() * Math.PI * 2
  return { x: Math.cos(angle) * r, y: Math.sin(angle) * r }
}

/** A figure of 6 to 9 bright stars joined by their minimum spanning tree, like a drawn constellation. */
export function constellation(source: string, label: string, short: string): Constellation {
  const next = random(hash(`figure:${source}`))
  const count = 6 + Math.floor(next() * 4)
  const stars = Array.from({ length: count }, () => ({ ...inDisc(next, 0.9), size: 1.4 + next() * 1.6 }))
  const edges: [number, number][] = []
  const joined = new Set([0])
  while (joined.size < count) {
    let best: [number, number] = [0, 0]
    let bestDistance = Infinity
    for (const a of joined)
      for (let b = 0; b < count; b++) {
        if (joined.has(b)) continue
        const d = Math.hypot(stars[a].x - stars[b].x, stars[a].y - stars[b].y)
        if (d < bestDistance) [bestDistance, best] = [d, [a, b]]
      }
    edges.push(best)
    joined.add(best[1])
  }
  return { source, label, short, stars, edges }
}

export const CONSTELLATIONS = SOURCES.map((s) => constellation(s.id, s.label, s.short))

/** Where a retrieved passage sits, as an offset from its region's centre in units of the radius. */
export function passageOffset(source: string, id: string): Point {
  return inDisc(random(hash(`passage:${source}:${id}`)), 0.95)
}

/** Background stars over the unit square: many faint, few bright. */
export function backgroundStars(count: number): BackgroundStar[] {
  const next = random(hash('background'))
  return Array.from({ length: count }, () => {
    const brightness = next() ** 3
    return { x: next(), y: next(), size: 0.35 + brightness * 1.3, alpha: 0.18 + brightness * 0.6 }
  })
}

const COLUMN = 704 // the reading column (42rem + gutters) in CSS pixels
const WIDE = 1100

/** Places the constellations around the reading column: in its margins when wide, above it when not. */
export function fitSky(width: number, height: number): Sky {
  const regions = new Map<string, Region>()
  const wide = width >= WIDE
  if (wide) {
    // Half on each side, in rows spread around the middle; the right side sits a little lower.
    const margin = (width - COLUMN) / 2
    const half = Math.ceil(SOURCES.length / 2)
    const step = 0.81 / half
    const radius = Math.min(margin * 0.36, height * (0.3 / half))
    SOURCES.forEach((s, i) => {
      const left = i < half
      const row = i % half
      const x = left ? margin * 0.5 : width - margin * 0.5
      const y = height * (0.49 - (step * (half - 1)) / 2 + row * step) + (left ? 0 : height * 0.04)
      regions.set(s.id, { centre: { x, y }, radius })
    })
  } else {
    // Keep in step with the band in index.css (min(28vh, 260px)).
    const band = Math.min(height * 0.28, 260)
    const rows = narrowRows(SOURCES.length)
    const radius = Math.min(width / (3 * rows[0]), band / (3.5 * rows.length))
    // The last row stays above the darker band behind the column (at 0.72 of the band).
    const first = 0.5 / (rows.length + 0.3)
    const step = rows.length > 1 ? (0.72 - first) / (rows.length - 1) : 0
    let i = 0
    rows.forEach((count, row) => {
      for (let col = 0; col < count; col++, i++) {
        const x = width * ((col + 0.5) / count) + (row % 2 ? width * 0.03 : 0)
        const y = 64 + band * (first + row * step)
        regions.set(SOURCES[i].id, { centre: { x, y }, radius })
      }
    })
  }
  return { regions, wide }
}

/** Rows of at most four, as even as can be and the fuller ones first: 10 -> [4, 3, 3]. */
export function narrowRows(count: number): number[] {
  const rows = Math.ceil(count / 4)
  return Array.from({ length: rows }, (_, row) => Math.floor(count / rows) + (row < count % rows ? 1 : 0))
}

/** A passage's on-screen position; unknown sources scatter over the whole sky. */
export function passagePoint(sky: Sky, width: number, height: number, source: string, id: string): Point {
  const region = sky.regions.get(source)
  if (!region) {
    const next = random(hash(`passage:${source}:${id}`))
    return { x: next() * width, y: next() * height * 0.8 }
  }
  const offset = passageOffset(source, id)
  return { x: region.centre.x + offset.x * region.radius, y: region.centre.y + offset.y * region.radius }
}
