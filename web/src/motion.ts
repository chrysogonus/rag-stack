import { useSyncExternalStore } from 'react'

const REDUCE = '(prefers-reduced-motion: reduce)'
const KEY = 'motion'

const listeners = new Set<() => void>()
/** The reader's choice for this page load, for when storage is missing or blocked. */
let choice: 'on' | 'off' | null = null

function chosen(): 'on' | 'off' | null {
  if (choice) return choice
  try {
    const value = localStorage.getItem(KEY)
    return value === 'on' || value === 'off' ? value : null
  } catch {
    return null
  }
}

/** Whether the page holds still: the reader's choice from the motion switch, else the system's reduced-motion setting. */
export function isStill(): boolean {
  const made = chosen()
  return made ? made === 'off' : matchMedia(REDUCE).matches
}

/** Remembers the reader's choice; from then on it overrides the system setting. */
export function setMotion(on: boolean) {
  choice = on ? 'on' : 'off'
  try {
    localStorage.setItem(KEY, choice)
  } catch {
    // The choice still holds until the page is reloaded.
  }
  changed()
}

/** Calls `listener` whenever the switch or the system setting changes. */
export function subscribeMotion(listener: () => void) {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

function changed() {
  document.documentElement.toggleAttribute('data-still', isStill())
  for (const listener of listeners) listener()
}

/** Mirrors the setting onto <html> as `data-still`, which stops the page's CSS animations, and keeps it current. */
export function startMotion() {
  matchMedia(REDUCE).addEventListener('change', changed)
  document.documentElement.toggleAttribute('data-still', isStill())
}

/** Whether the page holds still, re-rendering when the switch or the system setting changes. */
export function useStill() {
  return useSyncExternalStore(subscribeMotion, isStill)
}
