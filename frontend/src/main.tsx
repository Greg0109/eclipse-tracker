import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

// No StrictMode: its dev-mode double-invoke of effects (mount -> cleanup -> mount) tears down
// and recreates the MapLibre WebGL context back-to-back on the same canvas, which reliably
// triggers a real "WebGL context was lost" and leaves the map blank.
createRoot(document.getElementById('root')!).render(<App />)
