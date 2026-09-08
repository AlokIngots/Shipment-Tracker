import { useEffect, useState } from 'react'
import axios from 'axios'

// Pre-fills the login form during development so the demo is easy to try.
// Read from frontend/.env, which is never committed, so no credentials live
// in the repository. Blank when unset, which is what production wants.
const DEMO_EMAIL = import.meta.env.VITE_DEMO_EMAIL ?? ''
const DEMO_PASSWORD = import.meta.env.VITE_DEMO_PASSWORD ?? ''

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

// Maps an order status to a pill colour. Unknown statuses fall back to grey.
const STATUS_CLASS = {
  'in transit': 'pill--transit',
  'in production': 'pill--production',
  delivered: 'pill--delivered',
  shipped: 'pill--transit',
  draft: 'pill--neutral',
  cancelled: 'pill--cancelled',
}

function StatusPill({ status }) {
  if (!status) return <span className="pill pill--neutral">—</span>

  const tone = STATUS_CLASS[status.trim().toLowerCase()] ?? 'pill--neutral'
  return <span className={`pill ${tone}`}>{status}</span>
}

function OrdersScreen({ session, onSignOut }) {
  // 'loading' -> 'ready' | 'error'
  const [state, setState] = useState('loading')
  const [orders, setOrders] = useState([])

  useEffect(() => {
    let cancelled = false

    axios
      .get('/api/orders')
      .then((res) => {
        if (cancelled) return
        setOrders(res.data)
        setState('ready')
      })
      .catch(() => {
        if (cancelled) return
        setState('error')
      })

    return () => {
      cancelled = true
    }
  }, [])

  return (
    <>
      <div className="toolbar">
        <div>
          <h2 className="toolbar-title">Your orders</h2>
          <p className="toolbar-sub">Signed in as {session.email}</p>
        </div>
        <button type="button" className="button button--ghost" onClick={onSignOut}>
          Sign out
        </button>
      </div>

      <div className="card">
        {state === 'loading' && <p className="message">Loading your orders…</p>}

        {state === 'error' && (
          <p className="message message--error" role="alert">
            Couldn&apos;t load your orders. Please try again.
          </p>
        )}

        {state === 'ready' && orders.length === 0 && (
          <p className="message">No orders to show yet.</p>
        )}

        {state === 'ready' && orders.length > 0 && (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Sales Order</th>
                  <th>Grade</th>
                  <th>Description</th>
                  <th className="num">Ordered quantity</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {orders.map((order) => (
                  <tr key={order.id}>
                    <td className="mono">{order.sales_order_no}</td>
                    <td>{order.grade}</td>
                    <td>{order.description}</td>
                    {/* Quantity is rendered exactly as the API sends it. */}
                    <td className="num mono">
                      {order.ordered_qty} {order.unit}
                    </td>
                    <td>
                      <StatusPill status={order.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  )
}

export default function App() {
  const [session, setSession] = useState(null)

  return (
    <div className="page">
      <Header />
      <main className="main">
        {session ? (
          <OrdersScreen session={session} onSignOut={() => setSession(null)} />
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
