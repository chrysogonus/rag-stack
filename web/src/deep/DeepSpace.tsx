import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { useEffect, useMemo, useSyncExternalStore, type RefObject } from 'react'
import type { PerspectiveCamera } from 'three'
import type { SkyRenderer } from '../sky/renderer'
import { DeepField, Glow } from './scene'

const stillQuery = '(prefers-reduced-motion: reduce)'
const darkQuery = '(prefers-color-scheme: dark)'

/** The galaxy's distance; it sits off to the upper left, clear of the reading column on wide screens. */
const GALAXY_DISTANCE = 640

function useMedia(query: string) {
  return useSyncExternalStore(
    (onChange) => {
      const media = matchMedia(query)
      media.addEventListener('change', onChange)
      return () => media.removeEventListener('change', onChange)
    },
    () => matchMedia(query).matches,
  )
}

function Space({ rendererRef, still, dark }: { rendererRef: RefObject<SkyRenderer | null>; still: boolean; dark: boolean }) {
  const { gl, scene, camera, size, viewport, invalidate } = useThree()
  const perspective = camera as PerspectiveCamera
  const field = useMemo(() => new DeepField(still), [still])
  useEffect(() => () => field.dispose(), [field])
  const glow = useMemo(() => new Glow(gl, scene, perspective), [gl, scene, perspective])
  useEffect(() => () => glow.dispose(), [glow])
  useEffect(() => glow.setSize(size.width, size.height, viewport.dpr), [glow, size, viewport.dpr])

  // The palette lives in CSS: read it again whenever the colour scheme flips.
  useEffect(() => {
    const style = getComputedStyle(document.documentElement)
    const read = (name: string) => style.getPropertyValue(name).trim()
    glow.setSky(read('--sky'))
    field.setPalette({ star: read('--star'), glint: read('--glint'), ember: read('--ember') }, dark)
    invalidate()
  }, [dark, field, glow, invalidate])

  useEffect(() => {
    if (still) return
    const onMove = (e: PointerEvent) => field.point((e.clientX / innerWidth) * 2 - 1, (e.clientY / innerHeight) * 2 - 1)
    const onScroll = () => field.scroll(scrollY)
    window.addEventListener('pointermove', onMove, { passive: true })
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('scroll', onScroll)
    }
  }, [field, still])

  useFrame((_, delta) => {
    field.step(delta, rendererRef.current?.activity(), perspective, size.height * viewport.dpr)
  })
  // Priority 1: the glow pass draws the frame instead of the default render.
  useFrame((_, delta) => glow.render(field.bloom, delta), 1)

  const halfHeight = GALAXY_DISTANCE * Math.tan(Math.PI / 6)
  const halfWidth = halfHeight * (size.width / size.height)

  return (
    <>
      <mesh material={field.nebulaMaterial} frustumCulled={false} renderOrder={0}>
        <sphereGeometry args={[900, 48, 24]} />
      </mesh>
      <group position={[-Math.min(halfWidth * 0.58, 430), halfHeight * 0.34, -GALAXY_DISTANCE]} rotation={[1.15, 0, 0.35]}>
        <points geometry={field.galaxy} material={field.galaxyMaterial} frustumCulled={false} renderOrder={1} />
      </group>
      {/* The shaders move the stars, so their bounds on the CPU mean nothing: never cull them. */}
      <lineSegments geometry={field.streaks} material={field.streakMaterial} frustumCulled={false} renderOrder={2} />
      <points geometry={field.stars} material={field.starMaterial} frustumCulled={false} renderOrder={3} />
      <lineSegments geometry={field.meteors} material={field.meteorMaterial} frustumCulled={false} renderOrder={4} />
    </>
  )
}

/**
 * The deep field beneath the star atlas: a nebula, a distant galaxy and a field of stars to fly through.
 * It follows the atlas above it, warping while a question is searched and flaring when the answer's sources light.
 */
export default function DeepSpace({ rendererRef }: { rendererRef: RefObject<SkyRenderer | null> }) {
  const still = useMedia(stillQuery)
  const dark = useMedia(darkQuery)
  return (
    <div className="deep" aria-hidden="true">
      <Canvas
        flat
        dpr={[1, 1.5]}
        frameloop={still ? 'demand' : 'always'}
        camera={{ fov: 60, near: 1, far: 2000, position: [0, 0, 0], rotation: [0, 0, 0] }}
        gl={{ antialias: false, powerPreference: 'high-performance' }}
        fallback={null}
      >
        <Space rendererRef={rendererRef} still={still} dark={dark} />
      </Canvas>
    </div>
  )
}
