import coreWebVitals from 'eslint-config-next/core-web-vitals'
import typescript from 'eslint-config-next/typescript'

const config = [
  // `ima/` is a separate app staged here until it gets its own repo; it carries
  // its own eslint config and is linted from inside that directory.
  { ignores: ['.next/**', 'node_modules/**', 'next-env.d.ts', 'ima/**'] },
  ...coreWebVitals,
  ...typescript,
]

export default config
