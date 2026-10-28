import { useEffect, useState } from 'react'
import { useStill } from './motion'
import { PHRASES, scramble } from './musing'

const STEPS = 12 // ~0.5s at TICK to decrypt a phrase
const TICK = 40
const EVERY = 2600

/** The status line while an answer is written: a quip every few seconds, decrypting into place. */
export function Musing() {
  const [index, setIndex] = useState(() => Math.floor(Math.random() * PHRASES.length))
  const [revealed, setRevealed] = useState(0)
  const text = PHRASES[index]
  const still = useStill()
  const done = revealed >= text.length || still

  useEffect(() => {
    const timer = setInterval(() => {
      setIndex((i) => (i + 1) % PHRASES.length)
      setRevealed(0)
    }, EVERY)
    return () => clearInterval(timer)
  }, [])

  useEffect(() => {
    if (done) return
    const timer = setTimeout(() => setRevealed((r) => r + Math.ceil(text.length / STEPS)), TICK)
    return () => clearTimeout(timer)
  }, [done, revealed, text])

  return (
    <span className="musing" aria-hidden="true">
      <span className="spark" />
      {done ? text : scramble(text, revealed)}…
    </span>
  )
}
