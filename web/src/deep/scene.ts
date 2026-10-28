import {
  AdditiveBlending,
  BackSide,
  BufferAttribute,
  BufferGeometry,
  Color,
  DynamicDrawUsage,
  NormalBlending,
  ShaderMaterial,
  Vector2,
  Vector3,
  type PerspectiveCamera,
  type Scene,
  type WebGLRenderer,
} from 'three'
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js'
import { OutputPass } from 'three/examples/jsm/postprocessing/OutputPass.js'
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js'
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js'
import { DEPTH, galaxy, starField } from './field'
import * as glsl from './shaders'

/** Travel speeds in world units per second: resting drift, while an answer streams, searching, and on arrival. */
const DRIFT = 3
const FLOW = 12
const WARP = 360
const ARRIVAL = 420

/** The 2D sky's dust band runs at this angle; the nebula gathers along the same line. */
const BAND_TILT = 0.42

const FOV = 60
/** The supernova's camera punch: how far the view widens, and how long it takes to come back. */
const PUNCH = 9
const PUNCH_TIME = 1.1
/** World units travelled per pixel scrolled. */
const SCROLL_TRAVEL = 0.15

/** A pool of shooting stars; between them, a pause of `METEOR_GAP` seconds plus up to as much again. */
const METEORS = 8
const METEOR_GAP = 2.5
const METEOR_VOLLEY = 5

/** How strongly each layer shows: light on the dark sky, a faint print on the light chart; always quieter than the atlas. */
const LOOK = {
  dark: { stars: 0.85, galaxy: 0.5, nebula: 0.55, curve: 2, streak: 0.8, bloom: 0.5 },
  light: { stars: 0.65, galaxy: 0.3, nebula: 0.2, curve: 0.9, streak: 0.5, bloom: 0 },
}

export interface Activity {
  searching: boolean
  flowing: boolean
  ignitions: number
  finishes: number
  focus: { x: number; y: number } | null
}

export interface Palette {
  star: string
  glint: string
  ember: string
}

interface Meteor {
  x: number
  y: number
  z: number
  dx: number
  dy: number
  speed: number
  length: number
  life: number
  age: number
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
 * The deep field's geometry, materials and motion. It drifts at rest with the odd shooting star, warps while a
 * question is searched, flares when an answer's sources light and goes supernova when the answer is complete.
 * It turns towards the constellation in focus and travels as the page scrolls; `still` keeps it to one frame.
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
    uCurve: { value: 1 },
    uBand: { value: new Vector3(-Math.sin(BAND_TILT), Math.cos(BAND_TILT), 0) },
    uStar: { value: new Color() },
    uGlint: { value: new Color() },
    uEmber: { value: new Color() },
  }
  /** The galaxy's own brightness; every other uniform is shared with the field. */
  private readonly galaxyBright = { value: 1 }

  readonly stars: BufferGeometry
  readonly streaks: BufferGeometry
  readonly galaxy: BufferGeometry
  readonly meteors: BufferGeometry
  readonly starMaterial: ShaderMaterial
  readonly streakMaterial: ShaderMaterial
  readonly galaxyMaterial: ShaderMaterial
  readonly nebulaMaterial: ShaderMaterial
  readonly meteorMaterial: ShaderMaterial

  /** How strongly the glow pass blooms this frame. */
  bloom = 0

  private look = LOOK.dark
  private speed: number
  private travel = 0
  private time = 0
  private flare = 0
  private punch = Infinity
  private ignitions = 0
  private finishes = 0
  private yaw = 0
  private pitch = 0
  private focused = 0
  private focus = { x: 0, y: 0 }
  private pointer = { x: 0, y: 0 }
  private scrolled = 0
  private scrollTarget = 0
  private pool: (Meteor | null)[] = Array.from({ length: METEORS }, () => null)
  private nextMeteor = METEOR_GAP
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
    this.meteors = geometry({ position: [new Float32Array(METEORS * 6), 3], aAlpha: [new Float32Array(METEORS * 2), 1] })
    for (const name of ['position', 'aAlpha']) (this.meteors.getAttribute(name) as BufferAttribute).setUsage(DynamicDrawUsage)

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
    this.meteorMaterial = new ShaderMaterial({ ...layer, vertexShader: glsl.meteorVertex, fragmentShader: glsl.meteorFragment })
  }

  /** Takes the page's colours; light adds up on the night sky, and on the paper chart it is printed ink. */
  setPalette(palette: Palette, dark: boolean) {
    this.uniforms.uStar.value.set(palette.star)
    this.uniforms.uGlint.value.set(palette.glint)
    this.uniforms.uEmber.value.set(palette.ember)
    this.look = dark ? LOOK.dark : LOOK.light
    for (const material of [this.starMaterial, this.streakMaterial, this.galaxyMaterial, this.meteorMaterial]) {
      material.blending = dark ? AdditiveBlending : NormalBlending
      material.needsUpdate = true
    }
  }

  /** Where the pointer is, from -1 to 1 on each axis: the view leans gently after it. */
  point(x: number, y: number) {
    this.pointer = { x, y }
  }

  /** How far the page is scrolled, in pixels: scrolling carries the view through the field. */
  scroll(y: number) {
    this.scrollTarget = y * SCROLL_TRAVEL
  }

  /** Advances by `delta` seconds, following the atlas's `activity`; `bufferHeight` is in device pixels. */
  step(delta: number, sky: Activity | undefined, camera: PerspectiveCamera, bufferHeight: number) {
    if (sky && sky.ignitions !== this.ignitions) {
      if (!this.still) this.flare = Math.max(this.flare, 1)
      this.ignitions = sky.ignitions
    }
    if (sky && sky.finishes !== this.finishes) {
      if (!this.still) this.supernova(camera.aspect)
      this.finishes = sky.finishes
    }
    if (!this.still && delta > 0) {
      // A hidden tab pauses the loop; don't jump a minute ahead when it comes back.
      const dt = Math.min(delta, 0.05)
      const target = sky?.searching ? WARP : sky?.flowing ? FLOW : DRIFT
      this.speed = approach(this.speed, target, target > this.speed ? 1.4 : 0.9, dt)
      this.travel = (this.travel + this.speed * dt) % DEPTH
      this.scrolled = approach(this.scrolled, this.scrollTarget, 4, dt)
      this.time += dt
      this.flare *= Math.exp(-dt * 1.1)
      this.punch += dt

      // The view leans after the pointer, and turns further towards a constellation in focus.
      if (sky?.focus) this.focus = sky.focus
      this.focused = approach(this.focused, sky?.focus ? 1 : 0, 2.5, dt)
      const lookX = -this.pointer.x * 0.05 - this.focus.x * 0.12 * this.focused
      const lookY = -this.pointer.y * 0.035 - this.focus.y * 0.08 * this.focused
      this.yaw = approach(this.yaw, lookX + Math.sin(this.time * 0.05) * 0.03, 2, dt)
      this.pitch = approach(this.pitch, lookY, 2, dt)
      camera.rotation.set(this.pitch, this.yaw, Math.sin(this.time * 0.03) * 0.04)
      const punch = this.punch < PUNCH_TIME ? Math.sin(Math.PI * (this.punch / PUNCH_TIME)) ** 2 : 0
      camera.fov = FOV + punch * PUNCH - this.focused * 5
      camera.updateProjectionMatrix()

      this.moveMeteors(dt, camera.aspect)
    }
    const warp = smoothstep(20, 220, this.speed)
    const u = this.uniforms
    u.uTime.value = this.time
    u.uTravel.value = (this.travel + this.scrolled) % DEPTH
    u.uHalfHeight.value = bufferHeight / 2
    u.uStretch.value = Math.min(this.speed * 0.3, 140)
    u.uStreak.value = warp * this.look.streak
    u.uBright.value = this.look.stars * (1 + this.flare * 0.8)
    u.uGlow.value = 1 + warp * 0.7 + this.flare * 1.6
    u.uOpacity.value = this.look.nebula
    u.uCurve.value = this.look.curve
    this.galaxyBright.value = this.look.galaxy * (1 + this.flare)
    this.bloom = this.look.bloom ? this.look.bloom + warp * 0.4 + this.flare * 0.9 : 0
  }

  /** The answer is complete: a bigger flare, the camera punches out and back, a volley of shooting stars. */
  private supernova(aspect: number) {
    this.flare = 1.8
    this.punch = 0
    for (let i = 0; i < METEOR_VOLLEY; i++) this.launch(aspect)
  }

  /** Starts a shooting star somewhere in the upper sky, falling at a slant, if a slot is free. */
  private launch(aspect: number) {
    const slot = this.pool.indexOf(null)
    if (slot < 0) return
    const z = -(140 + Math.random() * 220)
    const halfHeight = -z * Math.tan(((FOV / 2) * Math.PI) / 180)
    const halfWidth = halfHeight * aspect
    const angle = 0.3 + Math.random() * 0.5
    const side = Math.random() < 0.5 ? 1 : -1
    this.pool[slot] = {
      x: (Math.random() * 1.6 - 0.8) * halfWidth,
      y: (0.15 + Math.random() * 0.8) * halfHeight,
      z,
      dx: Math.cos(angle) * side,
      dy: -Math.sin(angle),
      speed: halfWidth * (0.9 + Math.random() * 0.8),
      length: halfWidth * (0.15 + Math.random() * 0.15),
      life: 0.7 + Math.random() * 0.7,
      age: 0,
    }
  }

  private moveMeteors(dt: number, aspect: number) {
    // Shooting stars only cross a resting sky; a warp has light enough.
    if (this.time >= this.nextMeteor) {
      if (this.speed < 40) this.launch(aspect)
      this.nextMeteor = this.time + METEOR_GAP * (1 + Math.random())
    }
    const positions = this.meteors.getAttribute('position') as BufferAttribute
    const alpha = this.meteors.getAttribute('aAlpha') as BufferAttribute
    this.pool.forEach((m, i) => {
      if (m) m.age += dt
      if (!m || m.age >= m.life) {
        this.pool[i] = null
        alpha.setX(i * 2, 0)
        alpha.setX(i * 2 + 1, 0)
        return
      }
      const p = m.age / m.life
      const head = m.speed * m.age
      // The tail grows out of the head as it starts, so it never appears at full length from nowhere.
      const tail = head - m.length * Math.min(1, p * 4)
      positions.setXYZ(i * 2, m.x + m.dx * head, m.y + m.dy * head, m.z)
      positions.setXYZ(i * 2 + 1, m.x + m.dx * tail, m.y + m.dy * tail, m.z)
      alpha.setX(i * 2, smoothstep(0, 0.12, p) * (1 - p) ** 0.7)
      alpha.setX(i * 2 + 1, 0)
    })
    positions.needsUpdate = true
    alpha.needsUpdate = true
  }

  dispose() {
    for (const part of [this.stars, this.streaks, this.galaxy, this.meteors]) part.dispose()
    for (const part of [this.starMaterial, this.streakMaterial, this.galaxyMaterial, this.nebulaMaterial, this.meteorMaterial]) {
      part.dispose()
    }
  }
}

/**
 * Renders the scene through a bloom pass, so bright light glows into its surroundings, then converts to the
 * screen's colour space. With no bloom (the light chart) the pass is skipped.
 */
export class Glow {
  private readonly scene: Scene
  private readonly composer: EffectComposer
  /** Only light brighter than the threshold glows: stars, meteors and streaks, not the nebula. */
  private readonly bloom = new UnrealBloomPass(new Vector2(1, 1), 0, 0.4, 0.35)

  constructor(gl: WebGLRenderer, scene: Scene, camera: PerspectiveCamera) {
    this.scene = scene
    this.composer = new EffectComposer(gl)
    this.composer.addPass(new RenderPass(scene, camera))
    this.composer.addPass(this.bloom)
    this.composer.addPass(new OutputPass())
  }

  /**
   * The sky colour behind everything. A scene background, not the renderer's clear colour: that is converted
   * for the screen when set, so clearing the linear render target with it would encode it twice.
   */
  setSky(colour: string) {
    this.scene.background = new Color(colour)
  }

  setSize(width: number, height: number, dpr: number) {
    this.composer.setPixelRatio(dpr)
    this.composer.setSize(width, height)
  }

  render(strength: number, delta: number) {
    this.bloom.enabled = strength > 0.01
    this.bloom.strength = strength
    this.composer.render(delta)
  }

  dispose() {
    this.bloom.dispose()
    this.composer.dispose()
  }
}
