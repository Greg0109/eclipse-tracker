import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { dirname, join } from 'node:path'
import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// maplibre-gl loads its worker at runtime from `new URL('./maplibre-gl-worker.mjs', import.meta.url)`.
// Nothing statically imports that file, so the bundler never emits it, and after bundling
// `import.meta.url` is our own bundle's URL - the worker 404s. On a static host the 404 body is
// index.html, which the browser rejects: "Loading Worker ... blocked because of a disallowed MIME
// type ("text/html")".
//
// The worker in turn does `import './maplibre-gl-shared.mjs'` by exact relative name, so both files
// must land next to each other under their original, unhashed filenames - which is why this emits
// them by `fileName` rather than importing them with `?url` (that would fingerprint the worker and
// still leave its sibling missing).
const MAPLIBRE_RUNTIME_CHUNKS = ['maplibre-gl-worker.mjs', 'maplibre-gl-shared.mjs']

function maplibreWorkerAssets(): Plugin {
  return {
    name: 'maplibre-worker-assets',
    apply: 'build',
    generateBundle() {
      const distDir = dirname(createRequire(import.meta.url).resolve('maplibre-gl/dist/maplibre-gl.mjs'))
      for (const chunk of MAPLIBRE_RUNTIME_CHUNKS) {
        this.emitFile({
          type: 'asset',
          fileName: `assets/${chunk}`,
          source: readFileSync(join(distDir, chunk), 'utf8'),
        })
      }
    },
  }
}

// https://vite.dev/config/
export default defineConfig({
  // GitHub Pages serves this project site from https://<user>.github.io/eclipse-tracker/, so assets
  // must be requested from that subpath. Overridable for other hosts / local `vite preview`.
  base: process.env.VITE_BASE_PATH ?? "/eclipse-tracker/",
  plugins: [react(), tailwindcss(), maplibreWorkerAssets()],
  server: {
    port: 5173,
    // Allows access via serveo.net tunnels (e.g. `ssh -R 80:localhost:5173 serveo.net`) for ad-hoc remote testing.
    allowedHosts: [".serveousercontent.com"],
  },
  // maplibre-gl's internal worker breaks under Vite's dev-time dependency pre-bundling
  // (served with an empty MIME type, so the browser refuses to load it as a Worker script).
  optimizeDeps: {
    exclude: ["maplibre-gl"],
  },
})
