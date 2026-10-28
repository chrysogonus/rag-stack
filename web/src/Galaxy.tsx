import { useEffect, useRef } from 'react'
import { galaxy } from './deep/field'
import { useStill } from './motion'
import { hash, random } from './sky/layout'

type Rgb = [number, number, number]

const COUNT = 1400
/** Faint stars filling the disc between the arms, thinning out from the core. */
const HAZE = 900
/** Seen a little from above: the disc is squashed and turned, as galaxies usually appear. */
const TILT = 0.58
const TURN = -0.4
/** Radians per second at the core; the rim turns slower, so the arms wind as it spins. */
const SPIN = 0.45
/** Once the passages are found, the galaxy spins this much faster and its core flares. */
const FED_SPIN = 2.4

const stars = (() => {
  const { positions, sizes, reach } = galaxy(COUNT, 1, 2)
  const arms = Array.from({ length: COUNT }, (_, i) => {
    const x = positions[i * 3]
    const z = positions[i * 3 + 2]
    return { radius: Math.hypot(x, z), angle: Math.atan2(z, x), size: sizes[i], reach: reach[i], faint: 1 }
  })
  const next = random(hash('galaxy haze'))
  const haze = Array.from({ length: HAZE }, () => {
    const reach = Math.min(1, -Math.log(1 - next() * 0.95) * 0.3)
    return { radius: reach, angle: next() * Math.PI * 2, size: 0.4 + next() * 0.8, reach, faint: 0.45 }
  })
  return [...haze, ...arms]
})()

function rgb(value: string): Rgb {
  const n = parseInt(value.trim().replace('#', ''), 16)
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255]
}

const mix = (a: Rgb, b: Rgb, t: number): Rgb => [0, 1, 2].map((i) => Math.round(a[i] + (b[i] - a[i]) * t)) as Rgb

/** A small spiral galaxy turning in place: warm at the core, cool at the rim. `fed` quickens it. */
export function Galaxy({ fed }: { fed: boolean }) {
  const still = useStill()
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const fedRef = useRef(fed)
  useEffect(() => {
    fedRef.current = fed
  }, [fed])

  useEffect(() => {
    const canvas = canvasRef.current!
    const ctx = canvas.getContext('2d')!
    const dark = matchMedia('(prefers-color-scheme: dark)').matches
    const style = getComputedStyle(canvas)
    const star = rgb(style.getPropertyValue('--star'))
    const ember = rgb(style.getPropertyValue('--ember'))
    const glint = rgb(style.getPropertyValue('--glint'))
    // Each star's colour by how far out it lies: ember at the core, starlight, then glint at the rim.
    const colours = stars.map(({ reach }) =>
      reach < 0.35 ? mix(ember, star, reach / 0.35) : mix(star, glint, Math.min(1, (reach - 0.35) / 0.5)),
    )

    let frame = 0
    let last = performance.now()
    let time = 0
    let speed = 1
    let flare = 0

    const draw = (now: number) => {
      const dt = Math.min(0.05, (now - last) / 1000)
      last = now
      speed += ((fedRef.current ? FED_SPIN : 1) - speed) * (1 - Math.exp(-dt * 1.5))
      flare += ((fedRef.current ? 1 : 0) - flare) * (1 - Math.exp(-dt * 2))
      time += dt * speed

      const dpr = Math.min(devicePixelRatio || 1, 2)
      const size = canvas.clientWidth
      if (canvas.width !== Math.round(size * dpr)) canvas.width = canvas.height = Math.round(size * dpr)
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      ctx.clearRect(0, 0, size, size)
      const centre = size / 2
      const scale = size * 0.46

      // The core's glow, breathing, brighter once fed.
      const breath = 0.85 + 0.15 * Math.sin(time * 1.6)
      const core = ctx.createRadialGradient(centre, centre, 0, centre, centre, scale * (0.42 + flare * 0.12))
      core.addColorStop(0, `rgba(${ember},${(0.55 + flare * 0.3) * breath})`)
      core.addColorStop(0.35, `rgba(${ember},${0.18 + flare * 0.12})`)
      core.addColorStop(1, `rgba(${ember},0)`)
      ctx.fillStyle = core
      ctx.fillRect(0, 0, size, size)

      ctx.globalCompositeOperation = dark ? 'lighter' : 'source-over'
      const cos = Math.cos(TURN)
      const sin = Math.sin(TURN)
      stars.forEach((s, i) => {
        const angle = s.angle + (time * SPIN) / (0.3 + s.radius)
        const x = Math.cos(angle) * s.radius
        const y = Math.sin(angle) * s.radius * TILT
        const px = centre + (x * cos - y * sin) * scale
        const py = centre + (x * sin + y * cos) * scale
        const r = (0.35 + s.size * 0.32) * (1 + flare * 0.15)
        ctx.fillStyle = `rgba(${colours[i]},${(0.95 - s.reach * 0.45) * s.faint * (dark ? 0.85 : 0.7)})`
        ctx.beginPath()
        ctx.arc(px, py, r, 0, Math.PI * 2)
        ctx.fill()
      })
      ctx.globalCompositeOperation = 'source-over'

      if (!still) frame = requestAnimationFrame(draw)
    }
    frame = requestAnimationFrame(draw)
    return () => cancelAnimationFrame(frame)
  }, [still])

  return <canvas ref={canvasRef} className="galaxy" />
}
