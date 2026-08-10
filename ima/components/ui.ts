// Shared class strings. Every visual value comes from a token, so a theme flip
// restyles all of this without any component knowing a theme exists.

export const card =
  'bg-surface border-token border-hairline rounded-token shadow-token'

export const btn =
  'min-h-tap px-4 rounded-token border-token border-hairline bg-surface text-ink ' +
  'font-display text-sm flex items-center justify-center gap-2 ' +
  'transition-colors duration-token active:opacity-80'

export const btnPrimary =
  'min-h-tap px-5 rounded-token bg-accent text-accent-ink font-display text-base ' +
  'flex items-center justify-center gap-2 border-token border-transparent ' +
  'transition-opacity duration-token active:opacity-80'

export const btnQuiet =
  'min-h-tap px-3 rounded-token text-muted font-display text-sm ' +
  'flex items-center justify-center transition-colors duration-token active:opacity-70'

export const label = 'font-display text-[0.68rem] uppercase tracking-[0.14em] text-muted'

export const input =
  'w-full min-h-tap bg-surface border-token border-hairline rounded-token px-3 py-2 ' +
  'text-ink placeholder:text-muted font-body text-base'

export const screen = 'flex flex-col gap-row px-gutter pt-5 pb-28'
