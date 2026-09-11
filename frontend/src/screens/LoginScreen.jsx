import { useState } from 'react'
import axios from 'axios'

// Pre-fills the email box during development so the demo is easy to try.
// Read from frontend/.env, which is never committed. Blank when unset, which
// is what production wants.
const DEMO_EMAIL = import.meta.env.VITE_DEMO_EMAIL ?? ''

// One way in: a link sent to the inbox. There is no password box, on
// purpose. The server's password sign-in is switched off too
// (PASSWORD_SIGN_IN in backend/app/core/config.py), kept but dormant.
export default function LoginScreen() {
  const [email, setEmail] = useState(DEMO_EMAIL)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  // Once a link has been asked for: what the server said, and to which address.
  const [linkSent, setLinkSent] = useState(null)

  async function requestLink(event) {
    event.preventDefault()
    const address = email.trim()
    if (!address.includes('@')) {
      setError('Enter your email address, then press Sign in with email link.')
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
        {/* The heading already says it; the server's sentence starts the same way. */}
        <p className="lead">{linkSent.detail.replace(/^Check your email\.\s*/, '')}</p>
        <p className="login-hint login-hint--left">
          Sent to <strong>{linkSent.email}</strong>. Nothing there after a
          minute or two? Look in your spam folder, or go back and check the
          address.
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

      <form onSubmit={requestLink} noValidate>
        <label className="field">
          <span>Email</span>
          <input
            type="email"
            value={email}
            autoComplete="email"
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>

        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}

        <button type="submit" className="button" disabled={busy}>
          {busy ? 'Sending…' : 'Sign in with email link'}
        </button>
      </form>
      <p className="login-hint">
        We will email you a link that signs you in. No password needed. It
        works once, for 15 minutes.
      </p>

      {DEMO_EMAIL && <p className="demo-note">Demo account — pre-filled above.</p>}
    </div>
  )
}
