import { themeVars, type Theme } from './themes'

/** Push a theme onto <html>. Mirrors what the inline bootstrap does at launch. */
export function applyTheme(theme: Theme): void {
  if (typeof document === 'undefined') return
  const root = document.documentElement
  const vars = themeVars(theme)
  for (const [key, value] of Object.entries(vars)) root.style.setProperty(key, value)
  root.setAttribute('data-theme', theme.id)
  root.setAttribute('data-texture', theme.texture)

  let meta = document.querySelector('meta[name="theme-color"]')
  if (!meta) {
    meta = document.createElement('meta')
    meta.setAttribute('name', 'theme-color')
    document.head.appendChild(meta)
  }
  meta.setAttribute('content', theme.colors.ground)
}
