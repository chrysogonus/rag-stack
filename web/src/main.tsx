import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource-variable/public-sans'
import '@fontsource-variable/source-serif-4/opsz.css'
import '@fontsource-variable/source-serif-4/opsz-italic.css'
import './index.css'
import App from './App.tsx'
import { getConfig, UNAVAILABLE } from './api'
import { startMotion } from './motion'

// Before the first render, so CSS animations already know whether to play.
startMotion()

const root = createRoot(document.getElementById('root')!)
root.render(
  <p className="visually-hidden" role="status">
    Loading…
  </p>,
)
getConfig().then(
  (config) =>
    root.render(
      <StrictMode>
        <App config={config} />
      </StrictMode>,
    ),
  () =>
    root.render(
      <main className="thread">
        <section className="welcome">
          <h1>Couldn’t load the knowledge base</h1>
          <p>{UNAVAILABLE}</p>
          <div className="actions">
            <button type="button" className="primary" onClick={() => location.reload()}>
              Try again
            </button>
          </div>
        </section>
      </main>,
    ),
)
