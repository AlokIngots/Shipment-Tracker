import { useState } from 'react'
import axios from 'axios'
import { applyToken } from '../lib/session'

// Pre-fills the login form during development so the demo is easy to try.
// Read from frontend/.env, which is never committed, so no credentials live
// in the repository. Blank when unset, which is what production wants.
const DEMO_EMAIL = import.meta.env.VITE_DEMO_EMAIL ?? ''
const DEMO_PASSWORD = import.meta.env.VITE_DEMO_PASSWORD ?? ''

export default function LoginScreen({ onSignedIn }) {
  const [email, setEmail] = useState(DEMO_EMAIL)
  const [password, setPassword] = useState(DEMO_PASSWORD)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    setBusy(true)
    setError(null)

    try {
      const res = await axios.post('/api/login', { email, password })
      // Every later request carries the token, which is how the server
      // knows which customer is asking. Kept for the tab, so a refresh does
      // not throw the customer back to this screen.
      applyToken(res.data.token)
      onSignedIn(res.data)
    } catch (err) {
      if (err.response?.status === 401) {
        setError(err.response.data?.detail ?? 'Email or password is incorrect.')
      } else {
        setError('Could not reach the server. Please try again.')
      }
      setBusy(false)
    }
  }

  return (
    <div className="card card--login">
      <h2>Sign in</h2>
      <p className="lead">Access your orders, shipments and documents.</p>

      <form onSubmit={handleSubmit} noValidate>
        <label className="field">
          <span>Email</span>
          <input
            type="email"
            value={email}
            autoComplete="username"
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>

        <label className="field">
          <span>Password</span>
          <input
            type="password"
            value={password}
            autoComplete="current-password"
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>

        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}

        <button type="submit" className="button" disabled={busy}>
          {busy ? 'Signing in…' : 'Sign in'}
        </button>
      </form>

      {DEMO_EMAIL && <p className="demo-note">Demo account — pre-filled above.</p>}
    </div>
  )
}
