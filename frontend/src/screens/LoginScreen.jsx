import { useState } from 'react'
import axios from 'axios'
import { applyToken } from '../lib/session'

// Pre-fills the login form during development so the demo is easy to try.
// Read from frontend/.env, which is never committed, so no credentials live
// in the repository. Blank when unset, which is what production wants.
const DEMO_EMAIL = import.meta.env.VITE_DEMO_EMAIL ?? ''
const DEMO_PASSWORD = import.meta.env.VITE_DEMO_PASSWORD ?? ''

// Two ways in, on one card: a password, or a link sent to the inbox. They
// share the email box, so somebody who has forgotten their password only has
// to press the other button.
export default function LoginScreen({ onSignedIn }) {
  const [email, setEmail] = useState(DEMO_EMAIL)
  const [password, setPassword] = useState(DEMO_PASSWORD)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  // Once a link has been asked for: what the server said, and to which address.
  const [linkSent, setLinkSent] = useState(null)

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
      if (err.response?.status === 401 || err.response?.status === 429) {
        setError(err.response.data?.detail ?? 'Email or password is incorrect.')
      } else {
        setError('Could not reach the server. Please try again.')
      }
      setBusy(false)
    }
  }

  async function requestLink() {
    const address = email.trim()
    if (!address.includes('@')) {
      setError('Enter your email address above, then ask for a link.')
      return
    }

    setBusy(true)
    setError(null)
    try {
      const res = await axios.post('/api/magic-link', { email: address })
      // The server says the same thing whether or not the address has an
      // account, and so does this screen. Nothing here may hint either way.
      setLinkSent({ email: address, detail: res.data.detail })
    } catch (err) {
      const detail = err.response?.data?.detail
      setError(
        typeof detail === 'string' ? detail : 'Could not reach the server. Please try again.',
      )
    } finally {
      setBusy(false)
    }
  }

  if (linkSent) {
    return (
      <div className="card card--login" role="status">
        <h2>Check your email</h2>
        <p className="lead">{linkSent.detail}</p>
        <p className="login-hint login-hint--left">
          Sent to <strong>{linkSent.email}</strong>. Nothing there after a
          minute or two? Look in your spam folder, or sign in with your
          password instead.
        </p>
        <button
          type="button"
          className="button button--ghost"
          onClick={() => setLinkSent(null)}
        >
          Back to sign in
        </button>
      </div>
    )
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
          {busy ? 'Please wait…' : 'Sign in'}
        </button>
      </form>

      <div className="login-or" role="separator">
        or
      </div>

      <button
        type="button"
        className="button button--outline"
        onClick={requestLink}
        disabled={busy}
      >
        Sign in with email link
      </button>
      <p className="login-hint">
        No password needed. Enter your email above and we will send you a link
        that signs you in. It works once, for 15 minutes.
      </p>

      {DEMO_EMAIL && <p className="demo-note">Demo account — pre-filled above.</p>}
    </div>
  )
}
