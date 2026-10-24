import { useEffect, useRef, type RefObject } from 'react'
import { LABEL_FONT, SkyRenderer } from './renderer'

const stillQuery = '(prefers-reduced-motion: reduce)'
const darkQuery = '(prefers-color-scheme: dark)'

/** The decorative sky behind the page. `rendererRef` gives the app its animation calls. */
export function Sky({ rendererRef }: { rendererRef: RefObject<SkyRenderer | null> }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const overlayRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const still = matchMedia(stillQuery)
    const dark = matchMedia(darkQuery)
    const sky = new SkyRenderer(canvasRef.current!, overlayRef.current!, still.matches)
    rendererRef.current = sky
    sky.intro()

    const onResize = () => sky.resize()
    const onMotion = () => sky.setStill(still.matches)
    const onScheme = () => sky.refreshColors()
    // Citation tethers follow the page; hidden tabs pause the loop and resume on return.
    const onRedraw = () => sky.kick()
    window.addEventListener('resize', onResize)
    window.addEventListener('scroll', onRedraw, { passive: true })
    document.addEventListener('visibilitychange', onRedraw)
    still.addEventListener('change', onMotion)
    dark.addEventListener('change', onScheme)
    // Canvas text doesn't trigger a web font load on its own.
    void document.fonts.load(LABEL_FONT).then(onRedraw)
    return () => {
      window.removeEventListener('resize', onResize)
      window.removeEventListener('scroll', onRedraw)
      document.removeEventListener('visibilitychange', onRedraw)
      still.removeEventListener('change', onMotion)
      dark.removeEventListener('change', onScheme)
      sky.destroy()
      rendererRef.current = null
    }
  }, [rendererRef])

  return (
    <>
      <canvas ref={canvasRef} className="sky" aria-hidden="true" />
      <canvas ref={overlayRef} className="sky overlay" aria-hidden="true" />
    </>
  )
}
