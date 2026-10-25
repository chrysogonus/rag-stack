import { backgroundStars, CONSTELLATIONS, fitSky, passagePoint, type Point, type Sky } from './layout'

export interface LitSource {
  id: string
  source: string
  used: boolean
}

type Rgb = [number, number, number]

interface Lit {
  at: Point
  source: string
  used: boolean
  start: number
  cooling?: number
}

interface Particle {
  from: Point
  to: Point
  /** The horizontal span of the text it flows into: its trail stays faint over the words. */
  column: { left: number; right: number }
  bend: number
  start: number
}

const INTRO = 2400
const PULSE = 2400
const IGNITE = 700
const CONSIDERED = 1600
const COOL = 600
const FLIGHT = 950
const EMIT_EVERY = 33
export const LABEL_FONT = "italic 400 15px 'Source Serif 4 Variable', Georgia, serif"

const clamp = (t: number) => Math.min(1, Math.max(0, t))
const easeOut = (t: number) => 1 - (1 - t) ** 3
const easeInOut = (t: number) => (t < 0.5 ? 4 * t ** 3 : 1 - (-2 * t + 2) ** 3 / 2)

function hexToRgb(hex: string): Rgb {
  const n = parseInt(hex.trim().replace('#', ''), 16)
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255]
}

const rgba = ([r, g, b]: Rgb, a: number) => `rgba(${r},${g},${b},${clamp(a)})`

/**
 * Draws the knowledge base as a night sky. The animation loop runs only while something moves:
 * the entrance, a search pulse, passages lighting up, light flowing into the answer.
 */
export class SkyRenderer {
  private readonly ctx: CanvasRenderingContext2D
  /** Above the reading panel: light that travels to the page (pulses, particles, tethers). */
  private readonly fx: CanvasRenderingContext2D
  private readonly cache = document.createElement('canvas')
  private readonly stars = backgroundStars(900)
  private width = 0
  private height = 0
  private dpr = 1
  private sky: Sky = fitSky(1, 1)
  private colors = { star: [0, 0, 0] as Rgb, ember: [0, 0, 0] as Rgb, glint: [0, 0, 0] as Rgb }
  private introStart = -Infinity
  private pulses: { origin: Point; start: number }[] = []
  private searchingFrom: Point | null = null
  private lit = new Map<string, Lit>()
  private particles: Particle[] = []
  private nextFeeder = 0
  private lastEmit = 0
  private tetherFrom: Element | null = null
  private tetherTo: { source: string; id: string } | null = null
  private highlighted: string | null = null
  private lift = new Map<string, number>()
  private frame = 0
  private lastFrame = 0

  private readonly canvas: HTMLCanvasElement
  private readonly overlay: HTMLCanvasElement
  still: boolean

  constructor(canvas: HTMLCanvasElement, overlay: HTMLCanvasElement, still: boolean) {
    this.canvas = canvas
    this.overlay = overlay
    this.still = still
    this.ctx = canvas.getContext('2d')!
    this.fx = overlay.getContext('2d')!
    this.refreshColors()
    this.resize()
  }

  /** Re-reads the palette from CSS custom properties, e.g. after the colour scheme changes. */
  refreshColors() {
    const style = getComputedStyle(this.canvas)
    const read = (name: string) => hexToRgb(style.getPropertyValue(name))
    this.colors = { star: read('--star'), ember: read('--ember'), glint: read('--glint') }
    this.paintCache()
    this.kick()
  }

  resize() {
    this.dpr = Math.min(window.devicePixelRatio || 1, 2)
    this.width = window.innerWidth
    this.height = window.innerHeight
    for (const c of [this.canvas, this.overlay, this.cache]) {
      c.width = Math.round(this.width * this.dpr)
      c.height = Math.round(this.height * this.dpr)
    }
    this.sky = fitSky(this.width, this.height)
    for (const [key, lit] of this.lit) {
      const [source, ...id] = key.split('\u0000')
      lit.at = passagePoint(this.sky, this.width, this.height, source, id.join('\u0000'))
    }
    this.paintCache()
    this.kick()
  }

  intro() {
    this.introStart = this.still ? -Infinity : performance.now()
    this.kick()
  }

  /** A ring of light from the composer while the question is being searched; it repeats until `ignite`. */
  search(origin: Point) {
    this.searchingFrom = origin
    if (!this.still) this.pulses.push({ origin, start: performance.now() })
    this.kick()
  }

  stopSearching() {
    this.searchingFrom = null
  }

  /** Lights the retrieved passages: the ones answered from glow, the others flicker and fade. */
  ignite(sources: LitSource[]) {
    this.searchingFrom = null
    const now = performance.now()
    const keys = new Set(sources.map((s) => key(s.source, s.id)))
    for (const [k, lit] of this.lit) if (!keys.has(k) && lit.cooling === undefined) lit.cooling = now
    let used = 0
    sources.forEach((s, i) => {
      const k = key(s.source, s.id)
      const at = passagePoint(this.sky, this.width, this.height, s.source, s.id)
      const delay = this.still ? -Infinity : (s.used ? used++ : i) * 90
      this.lit.set(k, { at, source: s.source, used: s.used, start: now + delay })
    })
    this.nextFeeder = 0
    this.kick()
  }

  /** Sends a particle of light from the next glowing passage to `target`, at most one per 33ms. */
  emit(target: Point, column: { left: number; right: number }) {
    if (this.still) return
    const feeders = [...this.lit.values()].filter((l) => l.used && l.cooling === undefined)
    if (!feeders.length) return
    const now = performance.now()
    if (now - this.lastEmit < EMIT_EVERY) return
    this.lastEmit = now
    const from = feeders[this.nextFeeder++ % feeders.length].at
    this.particles.push({ from, to: target, column, bend: (Math.random() - 0.5) * 0.6, start: now })
    this.kick()
  }

  /** Draws a line from a citation (`from`) to its passage, or clears it with null. */
  tether(source: string | null, id: string | null, from: Element | null) {
    this.tetherTo = source && id ? { source, id } : null
    this.tetherFrom = this.tetherTo ? from : null
    this.kick()
  }

  /** Follows a change to the reduced-motion preference: anything in motion jumps to its end state. */
  setStill(still: boolean) {
    this.still = still
    if (still) {
      this.introStart = -Infinity
      this.pulses = []
      this.particles = []
      for (const [k, lit] of this.lit) {
        if (!lit.used || lit.cooling !== undefined) this.lit.delete(k)
        else lit.start = -Infinity
      }
    }
    this.kick()
  }

  /** Brightens one constellation, or none. */
  highlight(source: string | null) {
    this.highlighted = source
    this.kick()
  }

  /** Cools every lit passage back to rest, for a new conversation. */
  reset() {
    const now = performance.now()
    this.searchingFrom = null
    this.particles = []
    for (const lit of this.lit.values()) lit.cooling ??= now
    this.kick()
  }

  destroy() {
    cancelAnimationFrame(this.frame)
    this.frame = 0
  }

  /** Schedules a frame; the loop keeps going only while `draw` reports motion. */
  kick() {
    if (this.frame || document.hidden) return
    this.frame = requestAnimationFrame((now) => {
      this.frame = 0
      if (this.draw(now)) this.kick()
    })
  }

  private paintCache() {
    const c = this.cache.getContext('2d')!
    const { width: w, height: h } = this
    c.setTransform(this.dpr, 0, 0, this.dpr, 0, 0)
    c.clearRect(0, 0, w, h)
    const star = this.colors.star

    // A faint graticule, as on a printed star chart, centred on a pole above the screen.
    const pole = { x: w * 0.5, y: -h * 0.65 }
    c.strokeStyle = rgba(star, 0.06)
    c.lineWidth = 0.6
    const reach = Math.hypot(w, h) * 1.7
    for (let r = h * 0.75; r < reach; r += Math.max(110, h * 0.17)) {
      c.beginPath()
      c.arc(pole.x, pole.y, r, 0, Math.PI * 2)
      c.stroke()
    }
    for (let deg = 30; deg <= 150; deg += 10) {
      const a = (deg * Math.PI) / 180
      c.beginPath()
      c.moveTo(pole.x + Math.cos(a) * h * 0.75, pole.y + Math.sin(a) * h * 0.75)
      c.lineTo(pole.x + Math.cos(a) * reach, pole.y + Math.sin(a) * reach)
      c.stroke()
    }

    // The dust of a galactic band, crossing the sky on a diagonal.
    c.save()
    c.translate(w * 0.5, h * 0.55)
    c.rotate(-0.42)
    const band = Math.max(w, h) * 0.16
    const dust = c.createLinearGradient(0, -band, 0, band)
    dust.addColorStop(0, rgba(star, 0))
    dust.addColorStop(0.5, rgba(star, 0.045))
    dust.addColorStop(1, rgba(star, 0))
    c.fillStyle = dust
    c.fillRect(-w * 1.5, -band, w * 3, band * 2)
    c.restore()

    for (const s of this.stars) {
      c.fillStyle = rgba(star, s.alpha)
      c.beginPath()
      c.arc(s.x * w, s.y * h, s.size, 0, Math.PI * 2)
      c.fill()
    }
  }

  /** Paints one frame and reports whether anything is still moving. */
  private draw(now: number): boolean {
    const { ctx, fx, width: w, height: h } = this
    const { star, ember, glint } = this.colors
    const dt = Math.min(64, now - (this.lastFrame || now))
    this.lastFrame = now
    let moving = false

    for (const c of [ctx, fx]) {
      c.setTransform(this.dpr, 0, 0, this.dpr, 0, 0)
      c.clearRect(0, 0, w, h)
    }

    // Entrance: the sky is uncovered by a sweep from the pole, then the figures draw themselves.
    const intro = clamp((now - this.introStart) / INTRO)
    if (intro < 1) moving = true
    ctx.drawImage(this.cache, 0, 0, w, h)
    if (intro < 1) {
      const r = easeInOut(clamp(intro / 0.7)) * Math.hypot(w, h) * 1.25
      const mask = ctx.createRadialGradient(w / 2, -h * 0.15, Math.max(0, r - 260), w / 2, -h * 0.15, r + 1)
      mask.addColorStop(0, 'rgba(0,0,0,1)')
      mask.addColorStop(1, 'rgba(0,0,0,0)')
      ctx.globalCompositeOperation = 'destination-in'
      ctx.fillStyle = mask
      ctx.fillRect(0, 0, w, h)
      ctx.globalCompositeOperation = 'source-over'
    }

    // Constellations: brighter when highlighted or when one of their passages glows.
    const glowing = new Set([...this.lit.values()].filter((l) => l.used && l.cooling === undefined).map((l) => l.source))
    ctx.font = LABEL_FONT
    ctx.textAlign = 'center'
    ctx.textBaseline = 'top'
    CONSTELLATIONS.forEach((figure, i) => {
      const region = this.sky.regions.get(figure.source)!
      const target = this.highlighted === figure.source ? 1 : glowing.has(figure.source) ? 0.6 : 0
      const current = this.lift.get(figure.source) ?? 0
      const lift = this.still ? target : current + (target - current) * (1 - Math.exp(-dt / 140))
      if (Math.abs(target - lift) > 0.005) moving = true
      this.lift.set(figure.source, Math.abs(target - lift) > 0.005 ? lift : target)

      const appear = clamp((intro - 0.3 - i * 0.05) / 0.4)
      const drawn = easeInOut(appear)
      const at = (p: Point) => ({ x: region.centre.x + p.x * region.radius, y: region.centre.y + p.y * region.radius })

      ctx.strokeStyle = rgba(star, (0.22 + lift * 0.4) * Math.min(1, drawn * 1.5))
      ctx.lineWidth = 0.9
      ctx.beginPath()
      for (const [a, b] of figure.edges) {
        const p = at(figure.stars[a])
        const q = at(figure.stars[b])
        ctx.moveTo(p.x, p.y)
        ctx.lineTo(p.x + (q.x - p.x) * drawn, p.y + (q.y - p.y) * drawn)
      }
      ctx.stroke()

      for (const s of figure.stars) {
        const p = at(s)
        ctx.fillStyle = rgba(star, (0.75 + lift * 0.25) * clamp(appear * 2))
        ctx.beginPath()
        ctx.arc(p.x, p.y, s.size * (1 + lift * 0.25), 0, Math.PI * 2)
        ctx.fill()
      }

      ctx.fillStyle = rgba(star, (0.5 + lift * 0.5) * clamp((intro - 0.6) / 0.3))
      const label = this.sky.wide ? figure.label : figure.short
      ctx.fillText(label, region.centre.x, region.centre.y + region.radius + (this.sky.wide ? 14 : 8))
    })

    // Search pulses: rings of light spreading from the composer.
    const last = this.pulses.at(-1)
    if (this.searchingFrom && !this.still && (!last || now - last.start > PULSE)) {
      this.pulses.push({ origin: this.searchingFrom, start: now })
    }
    this.pulses = this.pulses.filter((p) => now - p.start < PULSE)
    for (const pulse of this.pulses) {
      // rAF's frame time can precede a start taken with performance.now() in the same frame.
      const t = clamp((now - pulse.start) / PULSE)
      const r = (1 - (1 - t) ** 2) * Math.hypot(w, h)
      const width = 80 + t * 160
      const ring = fx.createRadialGradient(pulse.origin.x, pulse.origin.y, Math.max(0, r - width), pulse.origin.x, pulse.origin.y, r)
      ring.addColorStop(0, rgba(ember, 0))
      ring.addColorStop(0.85, rgba(ember, 0.09 * (1 - t)))
      ring.addColorStop(1, rgba(ember, 0))
      fx.fillStyle = ring
      fx.fillRect(0, 0, w, h)
      fx.strokeStyle = rgba(ember, 0.35 * (1 - t))
      fx.lineWidth = 1
      fx.beginPath()
      fx.arc(pulse.origin.x, pulse.origin.y, r, 0, Math.PI * 2)
      fx.stroke()
      moving = true
    }
    if (this.searchingFrom && !this.still) moving = true

    // Retrieved passages.
    for (const [k, lit] of this.lit) {
      const age = now - lit.start
      const cooled = lit.cooling === undefined ? 1 : 1 - clamp((now - lit.cooling) / COOL)
      if (cooled <= 0 || (!lit.used && age > CONSIDERED)) {
        this.lit.delete(k)
        continue
      }
      if (age < 0) {
        moving = true
        continue
      }
      if (lit.used) {
        const t = clamp(age / IGNITE)
        if (t < 1 || cooled < 1) moving = true
        // Overshoot, then settle: the bloom flares as the passage is found.
        const flare = this.still ? 1 : easeOut(t) * (1 + 0.8 * Math.sin(Math.PI * t))
        const strength = flare * cooled
        const glow = 3 + 9 * strength
        const bloom = ctx.createRadialGradient(lit.at.x, lit.at.y, 0, lit.at.x, lit.at.y, glow)
        bloom.addColorStop(0, rgba(ember, 0.55 * strength))
        bloom.addColorStop(1, rgba(ember, 0))
        ctx.fillStyle = bloom
        ctx.beginPath()
        ctx.arc(lit.at.x, lit.at.y, glow, 0, Math.PI * 2)
        ctx.fill()
        // A four-point star, the same glyph that marks the passage in the source list.
        ctx.fillStyle = rgba(ember, Math.min(1, strength + 0.3) * cooled)
        sparkle(ctx, lit.at, 2.6 + 3.4 * Math.min(strength, 1.4))
      } else {
        const t = age / CONSIDERED
        moving = true
        const flicker = (1 - t) * (0.55 + 0.45 * Math.sin(t * 34 + lit.at.x))
        ctx.fillStyle = rgba(glint, flicker * cooled)
        ctx.beginPath()
        ctx.arc(lit.at.x, lit.at.y, 1.8, 0, Math.PI * 2)
        ctx.fill()
      }
    }

    // Light flowing from the passages into the answer.
    this.particles = this.particles.filter((p) => now - p.start < FLIGHT)
    for (const p of this.particles) {
      moving = true
      const t = easeInOut(clamp((now - p.start) / FLIGHT))
      const dx = p.to.x - p.from.x
      const dy = p.to.y - p.from.y
      const control = { x: p.from.x + dx * 0.5 - dy * p.bend, y: p.from.y + dy * 0.5 + dx * p.bend }
      const along = (s: number) => ({
        x: (1 - s) ** 2 * p.from.x + 2 * (1 - s) * s * control.x + s ** 2 * p.to.x,
        y: (1 - s) ** 2 * p.from.y + 2 * (1 - s) * s * control.y + s ** 2 * p.to.y,
      })
      fx.lineCap = 'round'
      for (let i = 0; i < 10; i++) {
        const a = along(Math.max(0, t - i * 0.018))
        const b = along(Math.max(0, t - (i + 1) * 0.018))
        const overText = a.x > p.column.left && a.x < p.column.right
        fx.strokeStyle = rgba(ember, (overText ? 0.18 : 0.7) * (1 - i / 10) * (1 - t * 0.4))
        fx.lineWidth = 2.2 * (1 - i / 10)
        fx.beginPath()
        fx.moveTo(a.x, a.y)
        fx.lineTo(b.x, b.y)
        fx.stroke()
      }
      const head = along(t)
      fx.fillStyle = rgba(ember, 0.9 * (1 - t * 0.5))
      fx.beginPath()
      fx.arc(head.x, head.y, 1.6, 0, Math.PI * 2)
      fx.fill()
    }

    // A citation's tether to its passage.
    // Earlier answers' passages may have cooled since, so the position comes from the citation itself.
    if (this.tetherTo && this.tetherFrom?.isConnected) {
      const rect = this.tetherFrom.getBoundingClientRect()
      const from = { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 }
      const to = passagePoint(this.sky, w, h, this.tetherTo.source, this.tetherTo.id)
      if (!this.lit.has(key(this.tetherTo.source, this.tetherTo.id))) {
        fx.fillStyle = rgba(ember, 0.9)
        sparkle(fx, to, 4)
      }
      fx.strokeStyle = rgba(ember, 0.7)
      fx.lineWidth = 1
      fx.setLineDash([2, 4])
      fx.beginPath()
      fx.moveTo(from.x, from.y)
      fx.quadraticCurveTo((from.x + to.x) / 2, to.y, to.x, to.y)
      fx.stroke()
      fx.setLineDash([])
      fx.beginPath()
      fx.arc(to.x, to.y, 9, 0, Math.PI * 2)
      fx.stroke()
    }

    if (!moving) this.lastFrame = 0
    return moving
  }
}

function sparkle(ctx: CanvasRenderingContext2D, { x, y }: Point, r: number) {
  const waist = r * 0.22
  ctx.beginPath()
  ctx.moveTo(x, y - r)
  ctx.quadraticCurveTo(x + waist, y - waist, x + r, y)
  ctx.quadraticCurveTo(x + waist, y + waist, x, y + r)
  ctx.quadraticCurveTo(x - waist, y + waist, x - r, y)
  ctx.quadraticCurveTo(x - waist, y - waist, x, y - r)
  ctx.fill()
}

const key = (source: string, id: string) => `${source}\u0000${id}`
