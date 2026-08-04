import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
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
