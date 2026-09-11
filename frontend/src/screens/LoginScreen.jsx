import { useEffect, useState } from 'react'
import axios from 'axios'
import { applyToken } from '../lib/session'

// Pre-fills the form during development so the demo is easy to try. Read
// from frontend/.env, which is never committed. Blank when unset, which is
// what production wants.
const DEMO_EMAIL = import.meta.env.VITE_DEMO_EMAIL ?? ''
const DEMO_PASSWORD = import.meta.env.VITE_DEMO_PASSWORD ?? ''

// Normally one way in: a link sent to the inbox.
//
// The password box comes back only while the server's PASSWORD_SIGN_IN
// switch is on -- the way back in if email ever fails. The screen asks the
// server every time it loads, so turning the switch on or off needs no new
// build of the website. If the question cannot be answered, the screen stays
// link-only: the normal state is the safe one to fall back to.
export default function LoginScreen({ onSignedIn }) {
  const [email, setEmail] = useState(DEMO_EMAIL)
  const [password, setPassword] = useState(DEMO_PASSWORD)
  const [passwordSignIn, setPasswordSignIn] = useState(false)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  // Once a link has been asked for: what the server said, and to which address.
  const [linkSent, setLinkSent] = useState(null)

  useEffect(() => {
    let cancelled = false
    axios
      .get('/api/sign-in-options')
      .then((res) => {
        if (!cancelled) setPasswordSignIn(res.data?.password_sign_in === true)
      })
      .catch(() => {
        // Stay link-only.
      })
    return () => {
      cancelled = true
    }
  }, [])

  async function signInWithPassword(event) {
    event.preventDefault()
    setBusy(true)
    setError(null)

    try {
      const res = await axios.post('/api/login', { email, password })
      // Every later request carries the token, which is how the server knows
      // who is asking. Kept for the tab, so a refresh does not sign them out.
      applyToken(res.data.token)
      onSignedIn(res.data)
    } catch (err) {
      const detail = err.response?.data?.detail
      if ([401, 403, 429].includes(err.response?.status) && typeof detail === 'string') {
        setError(detail)
      } else {
        setError('Could not reach the server. Please try again.')
      }
      setBusy(false)
    }
  }

  async function requestLink(event) {
    event?.preventDefault()
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

  const emailField = (
    <label className="field">
      <span>Email</span>
      <input
        type="email"
        value={email}
        autoComplete={passwordSignIn ? 'username' : 'email'}
        onChange={(e) => setEmail(e.target.value)}
      />
    </label>
  )

  const errorLine = error && (
    <p className="error" role="alert">
      {error}
    </p>
  )

  const hint = (
    <p className="login-hint">
      We will email you a link that signs you in. No password needed. It works
      once, for 15 minutes.
    </p>
  )

  return (
    <div className="card card--login">
      <h2>Sign in</h2>
      <p className="lead">Access your orders, shipments and documents.</p>

      {passwordSignIn ? (
        <>
          <form onSubmit={signInWithPassword} noValidate>
            {emailField}
            <label className="field">
              <span>Password</span>
              <input
                type="password"
                value={password}
                autoComplete="current-password"
                onChange={(e) => setPassword(e.target.value)}
              />
            </label>
            {errorLine}
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
          {hint}
        </>
      ) : (
        <>
          <form onSubmit={requestLink} noValidate>
            {emailField}
            {errorLine}
            <button type="submit" className="button" disabled={busy}>
              {busy ? 'Sending…' : 'Sign in with email link'}
            </button>
          </form>
          {hint}
        </>
      )}

      {DEMO_EMAIL && <p className="demo-note">Demo account — pre-filled above.</p>}
    </div>
  )
}
