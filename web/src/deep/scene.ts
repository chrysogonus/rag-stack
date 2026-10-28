import {
  AdditiveBlending,
  BackSide,
  BufferAttribute,
  BufferGeometry,
  Color,
  NormalBlending,
  ShaderMaterial,
  SRGBColorSpace,
  Vector3,
  type Camera,
} from 'three'
import { DEPTH, galaxy, starField } from './field'
import * as glsl from './shaders'

/** Travel speeds in world units per second: resting drift, while an answer streams, searching, and on arrival. */
const DRIFT = 3
const FLOW = 12
const WARP = 360
const ARRIVAL = 420

/** The 2D sky's dust band runs at this angle; the nebula gathers along the same line. */
const BAND_TILT = 0.42

/** How strongly each layer shows: light on the dark sky, a faint print on the light chart; always quieter than the atlas. */
const LOOK = {
  dark: { stars: 0.85, galaxy: 0.4, nebula: 0.55, streak: 0.8 },
  light: { stars: 0.5, galaxy: 0.25, nebula: 0.16, streak: 0.45 },
}

export interface Activity {
  searching: boolean
  flowing: boolean
  ignitions: number
}

export interface Palette {
  star: string
  glint: string
  ember: string
}

const smoothstep = (a: number, b: number, x: number) => {
  const t = Math.min(1, Math.max(0, (x - a) / (b - a)))
  return t * t * (3 - 2 * t)
}

/** Eases `from` towards `to` at `rate` per second, the same whatever the frame rate. */
const approach = (from: number, to: number, rate: number, dt: number) => from + (to - from) * (1 - Math.exp(-dt * rate))

function geometry(attributes: Record<string, [Float32Array, number]>) {
  const g = new BufferGeometry()
  for (const [name, [array, size]] of Object.entries(attributes)) g.setAttribute(name, new BufferAttribute(array, size))
  return g
}

/** Each star twice, as the head and tail of a line. */
function streaks(positions: Float32Array, tints: Float32Array) {
  const count = tints.length
  const doubled = new Float32Array(count * 6)
  const end = new Float32Array(count * 2)
  const tint = new Float32Array(count * 2)
  for (let i = 0; i < count; i++) {
    const star = positions.subarray(i * 3, i * 3 + 3)
    doubled.set(star, i * 6)
    doubled.set(star, i * 6 + 3)
    end[i * 2 + 1] = 1
    tint[i * 2] = tint[i * 2 + 1] = tints[i]
  }
  return geometry({ position: [doubled, 3], aEnd: [end, 1], aTint: [tint, 1] })
}

/**
 * The deep field's geometry, materials and motion. It drifts at rest, warps while a question is searched,
 * and flares when an answer's sources light; `still` keeps it to a single resting frame.
 */
export class DeepField {
  private readonly uniforms = {
    uTime: { value: 0 },
    uTravel: { value: 0 },
    uDepth: { value: DEPTH },
    uHalfHeight: { value: 1 },
    uBright: { value: 1 },
    uStretch: { value: 0 },
    uStreak: { value: 0 },
    uGlow: { value: 1 },
    uOpacity: { value: 1 },
    uBand: { value: new Vector3(-Math.sin(BAND_TILT), Math.cos(BAND_TILT), 0) },
    uStar: { value: new Vector3() },
    uGlint: { value: new Vector3() },
    uEmber: { value: new Vector3() },
  }
  /** The galaxy's own brightness; every other uniform is shared with the field. */
  private readonly galaxyBright = { value: 1 }

  readonly stars: BufferGeometry
  readonly streaks: BufferGeometry
  readonly galaxy: BufferGeometry
  readonly starMaterial: ShaderMaterial
  readonly streakMaterial: ShaderMaterial
  readonly galaxyMaterial: ShaderMaterial
  readonly nebulaMaterial: ShaderMaterial

  private look = LOOK.dark
  private speed: number
  private travel = 0
  private time = 0
  private flare = 0
  private ignitions = 0
  private yaw = 0
  private pitch = 0
  private pointer = { x: 0, y: 0 }
  private readonly still: boolean

  constructor(still: boolean) {
    this.still = still
    this.speed = still ? 0 : ARRIVAL
    const field = starField(7000, 420)
    const spiral = galaxy(14000, 170)
    this.stars = geometry({
      position: [field.positions, 3],
      aSize: [field.sizes, 1],
      aPhase: [field.phases, 1],
      aTint: [field.tints, 1],
    })
    this.streaks = streaks(field.positions, field.tints)
    this.galaxy = geometry({ position: [spiral.positions, 3], aSize: [spiral.sizes, 1], aReach: [spiral.reach, 1] })

    const uniforms = this.uniforms
    const layer = { uniforms, transparent: true, depthWrite: false }
    this.starMaterial = new ShaderMaterial({ ...layer, vertexShader: glsl.starVertex, fragmentShader: glsl.starFragment })
    this.streakMaterial = new ShaderMaterial({ ...layer, vertexShader: glsl.streakVertex, fragmentShader: glsl.streakFragment })
    this.galaxyMaterial = new ShaderMaterial({
      ...layer,
      uniforms: { ...uniforms, uBright: this.galaxyBright },
      vertexShader: glsl.galaxyVertex,
      fragmentShader: glsl.starFragment,
    })
    this.nebulaMaterial = new ShaderMaterial({
      ...layer,
      side: BackSide,
      vertexShader: glsl.nebulaVertex,
      fragmentShader: glsl.nebulaFragment,
    })
  }

  /** Takes the page's colours; light adds up on the night sky, and on the paper chart it is printed ink. */
  setPalette(palette: Palette, dark: boolean) {
    const rgb = { r: 0, g: 0, b: 0 }
    for (const [uniform, colour] of [
      [this.uniforms.uStar, palette.star],
      [this.uniforms.uGlint, palette.glint],
      [this.uniforms.uEmber, palette.ember],
    ] as const) {
      new Color(colour).getRGB(rgb, SRGBColorSpace)
      uniform.value.set(rgb.r, rgb.g, rgb.b)
    }
    this.look = dark ? LOOK.dark : LOOK.light
    for (const material of [this.starMaterial, this.streakMaterial, this.galaxyMaterial]) {
      material.blending = dark ? AdditiveBlending : NormalBlending
      material.needsUpdate = true
    }
  }

  /** Where the pointer is, from -1 to 1 on each axis: the view leans gently after it. */
  point(x: number, y: number) {
    this.pointer = { x, y }
  }

  /** Advances by `delta` seconds, following the atlas's `activity`; `bufferHeight` is in device pixels. */
  step(delta: number, sky: Activity | undefined, camera: Camera | undefined, bufferHeight: number) {
    if (sky && sky.ignitions !== this.ignitions) {
      if (!this.still) this.flare = 1
      this.ignitions = sky.ignitions
    }
    if (!this.still && delta > 0) {
      // A hidden tab pauses the loop; don't jump a minute ahead when it comes back.
      const dt = Math.min(delta, 0.05)
      const target = sky?.searching ? WARP : sky?.flowing ? FLOW : DRIFT
      this.speed = approach(this.speed, target, target > this.speed ? 1.4 : 0.9, dt)
      this.travel = (this.travel + this.speed * dt) % DEPTH
      this.time += dt
      this.flare *= Math.exp(-dt * 1.1)
      this.yaw = approach(this.yaw, -this.pointer.x * 0.05 + Math.sin(this.time * 0.05) * 0.03, 2, dt)
      this.pitch = approach(this.pitch, -this.pointer.y * 0.035, 2, dt)
      camera?.rotation.set(this.pitch, this.yaw, Math.sin(this.time * 0.03) * 0.04)
    }
    const warp = smoothstep(20, 220, this.speed)
    const u = this.uniforms
    u.uTime.value = this.time
    u.uTravel.value = this.travel
    u.uHalfHeight.value = bufferHeight / 2
    u.uStretch.value = Math.min(this.speed * 0.3, 140)
    u.uStreak.value = warp * this.look.streak
    u.uBright.value = this.look.stars * (1 + this.flare * 0.8)
    u.uGlow.value = 1 + warp * 0.7 + this.flare * 1.6
    u.uOpacity.value = this.look.nebula
    this.galaxyBright.value = this.look.galaxy * (1 + this.flare)
  }

  dispose() {
    for (const part of [this.stars, this.streaks, this.galaxy]) part.dispose()
    for (const part of [this.starMaterial, this.streakMaterial, this.galaxyMaterial, this.nebulaMaterial]) part.dispose()
  }
}
