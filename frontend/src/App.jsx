import { useState } from 'react'
import axios from 'axios'

// Demo credentials, pre-filled so the login is easy to try.
// Remove once real customer accounts exist.
const DEMO_EMAIL = 'procurement@wilo.com'
const DEMO_PASSWORD = 'demo1234'

function Header() {
  return (
    <header className="header">
      <div className="brand">
        <span className="mark">AI</span>
        <div>
          <h1>Alok Ingots</h1>
          <p>Customer Portal</p>
        </div>
      </div>
    </header>
  )
}

function LoginScreen({ onSignedIn }) {
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

      <p className="demo-note">
        Demo account — pre-filled above.
      </p>
    </div>
  )
}

function SignedIn({ session, onSignOut }) {
  return (
    <div className="card">
      <div className="status status--ok">Signed in</div>
      <h2 className="signed-in-heading">Welcome, {session.email}</h2>
      <p className="lead">
        Your orders will appear here. Nothing to show yet — the order list is
        the next thing we build.
      </p>
      <button type="button" className="button button--ghost" onClick={onSignOut}>
        Sign out
      </button>
    </div>
  )
}

export default function App() {
  const [session, setSession] = useState(null)

  return (
    <div className="page">
      <Header />
      <main className="main">
        {session ? (
          <SignedIn session={session} onSignOut={() => setSession(null)} />
        ) : (
          <LoginScreen onSignedIn={setSession} />
        )}
      </main>
      <footer className="footer">
        Stainless steel bright bars · Mumbai, India
      </footer>
    </div>
  )
}
