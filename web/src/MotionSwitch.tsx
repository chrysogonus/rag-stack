import { setMotion, useStill } from './motion'

/** Turns the page's animation on or off, overriding the system's reduced-motion setting once used. */
export function MotionSwitch() {
  const still = useStill()
  return (
    <button type="button" role="switch" aria-checked={!still} className="motion" onClick={() => setMotion(still)}>
      Motion
      <span className="track" aria-hidden="true">
        <span className="knob" />
      </span>
    </button>
  )
}
