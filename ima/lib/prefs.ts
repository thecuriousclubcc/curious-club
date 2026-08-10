// A tiny external store over localStorage.
//
// Preferences are read during render through useSyncExternalStore rather than
// copied into state inside an effect: the theme has to be resolvable on the
// very first render, and effect-then-setState would both flash the wrong skin
// and cascade renders.

type Listener = () => void

const listeners = new Set<Listener>()

export function subscribePrefs(listener: Listener): () => void {
  listeners.add(listener)
  window.addEventListener('storage', listener)
  return () => {
    listeners.delete(listener)
    window.removeEventListener('storage', listener)
  }
}

export function readPref(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

export function writePref(key: string, value: string | null): void {
  try {
    if (value === null) localStorage.removeItem(key)
    else localStorage.setItem(key, value)
  } catch {
    // Storage can be unavailable in private mode. Losing a preference is
    // survivable; blocking the app over it is not.
  }
  for (const listener of listeners) listener()
}

export const PREF_KEYS = {
  locale: 'ima.locale',
  pin: 'ima.pin',
  shuffle: 'ima.shuffle',
  seen: 'ima.seenTheme',
} as const
