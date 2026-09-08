import { useEffect, useState } from 'react'
import axios from 'axios'

export default function App() {
  // 'loading' -> 'ok' | 'error'
  const [state, setState] = useState('loading')
  const [payload, setPayload] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false

    axios
      .get('/api/health')
      .then((res) => {
        if (cancelled) return
        setPayload(res.data)
        setState('ok')
      })
      .catch((err) => {
        if (cancelled) return
        setError(err.message)
        setState('error')
      })

    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className="page">
      <header className="header">
        <div className="brand">
          <span className="mark">AI</span>
          <div>
            <h1>Alok Ingots</h1>
            <p>Customer Portal</p>
          </div>
        </div>
      </header>

      <main className="main">
        <section className="card">
          <h2>Backend connection</h2>
          <p className="lead">
            This page calls <code>GET /api/health</code> on load to confirm the
            React frontend can reach the FastAPI backend.
          </p>

          {state === 'loading' && (
            <div className="status status--pending">Checking backend…</div>
          )}

          {state === 'ok' && (
            <>
              <div className="status status--ok">
                Connected — backend responded
              </div>
              <pre className="payload">{JSON.stringify(payload, null, 2)}</pre>
            </>
          )}

          {state === 'error' && (
            <>
              <div className="status status--bad">
                Could not reach the backend
              </div>
              <pre className="payload">{error}</pre>
              <p className="hint">
                Is uvicorn running on <code>127.0.0.1:8000</code>?
              </p>
            </>
          )}
        </section>
      </main>

      <footer className="footer">
        Stainless steel bright bars · Mumbai, India
      </footer>
    </div>
  )
}
