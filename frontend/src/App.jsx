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
      // Every later request carries the token, which is how the server
      // knows which customer is asking.
      axios.defaults.headers.common.Authorization = `Bearer ${res.data.token}`
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
  shipped: 'pill--shipped',
  draft: 'pill--neutral',
  cancelled: 'pill--cancelled',
}

function StatusPill({ status }) {
  if (!status) return <span className="pill pill--neutral">—</span>

  const tone = STATUS_CLASS[status.trim().toLowerCase()] ?? 'pill--neutral'
  return <span className={`pill ${tone}`}>{status}</span>
}

function OrdersScreen({ session, onSignOut, onOpenOrder }) {
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
      .catch((err) => {
        if (cancelled) return
        setState(err.response?.status === 401 ? 'unauthorised' : 'error')
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
          <p className="toolbar-sub">
            {session.customer?.name} · signed in as {session.email}
          </p>
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

        {state === 'unauthorised' && (
          <p className="message message--error" role="alert">
            Your session has expired. Please sign in again.
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
                  <th />
                </tr>
              </thead>
              <tbody>
                {orders.map((order) => (
                  <tr
                    key={order.id}
                    className="row--clickable"
                    onClick={() => onOpenOrder(order.id)}
                  >
                    <td className="mono link">{order.sales_order_no}</td>
                    <td>{order.grade}</td>
                    <td>{order.description}</td>
                    {/* Quantity is rendered exactly as the API sends it. */}
                    <td className="num mono">
                      {order.ordered_qty} {order.unit}
                    </td>
                    <td>
                      <StatusPill status={order.status} />
                    </td>
                    <td className="chevron">&#8250;</td>
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


function fmtDate(value) {
  if (!value) return '\u2014'
  const [y, m, d] = value.split('-')
  return `${d}/${m}/${y}`
}

function OrderDetailScreen({ orderId, onBack, onSignOut, session }) {
  // 'loading' -> 'ready' | 'error' | 'notfound'
  const [state, setState] = useState('loading')
  const [order, setOrder] = useState(null)

  useEffect(() => {
    let cancelled = false

    axios
      .get(`/api/orders/${orderId}`)
      .then((res) => {
        if (cancelled) return
        setOrder(res.data)
        setState('ready')
      })
      .catch((err) => {
        if (cancelled) return
        setState(err.response?.status === 404 ? 'notfound' : 'error')
      })

    return () => {
      cancelled = true
    }
  }, [orderId])

  return (
    <>
      <div className="toolbar">
        <div>
          <button type="button" className="backlink" onClick={onBack}>
            &#8249; Back to orders
          </button>
          <h2 className="toolbar-title">
            {state === 'ready' ? order.sales_order_no : 'Order'}
          </h2>
          <p className="toolbar-sub">{session.customer?.name}</p>
        </div>
        <button type="button" className="button button--ghost" onClick={onSignOut}>
          Sign out
        </button>
      </div>

      {state === 'loading' && (
        <div className="card">
          <p className="message">Loading order\u2026</p>
        </div>
      )}

      {state === 'notfound' && (
        <div className="card">
          <p className="message message--error" role="alert">
            That order could not be found.
          </p>
        </div>
      )}

      {state === 'error' && (
        <div className="card">
          <p className="message message--error" role="alert">
            Couldn&apos;t load this order. Please try again.
          </p>
        </div>
      )}

      {state === 'ready' && (
        <>
          <div className="card">
            <StatusPill status={order.status} />
            <p className="detail-desc">{order.description}</p>

            <dl className="facts">
              <div>
                <dt>Your PO</dt>
                <dd className="mono">{order.customer_po || '\u2014'}</dd>
              </div>
              <div>
                <dt>Grade</dt>
                <dd>{order.grade || '\u2014'}</dd>
              </div>
            </dl>

            {/* Quantities are shown exactly as the server sends them. */}
            <div className="totals">
              <div className="total">
                <span className="total-label">Ordered</span>
                <span className="total-value">
                  {order.ordered_qty} <em>{order.unit}</em>
                </span>
              </div>
              <div className="total">
                <span className="total-label">Dispatched</span>
                <span className="total-value">
                  {order.dispatched_qty} <em>{order.unit}</em>
                </span>
              </div>
              <div className="total total--balance">
                <span className="total-label">Balance</span>
                <span className="total-value">
                  {order.balance_qty} <em>{order.unit}</em>
                </span>
              </div>
            </div>
          </div>

          <h3 className="section-title">Shipments ({order.shipments.length})</h3>

          {order.shipments.length === 0 && (
            <div className="card">
              <p className="message">Nothing has shipped against this order yet.</p>
            </div>
          )}

          {order.shipments.map((shipment) => (
            <div className="card shipment" key={shipment.id}>
              <div className="shipment-head">
                <div>
                  <span className="mono shipment-no">{shipment.shipment_no}</span>
                  <span className="shipment-qty">
                    {shipment.dispatched_qty} {shipment.unit}
                  </span>
                </div>
                <StatusPill status={shipment.status} />
              </div>

              <dl className="facts">
                <div>
                  <dt>Vessel</dt>
                  <dd>{shipment.vessel_name || '\u2014'}</dd>
                </div>
                <div>
                  <dt>IMO</dt>
                  <dd className="mono">{shipment.imo_number || '\u2014'}</dd>
                </div>
                <div>
                  <dt>ETD</dt>
                  <dd>{fmtDate(shipment.etd)}</dd>
                </div>
                <div>
                  <dt>ETA</dt>
                  <dd>{fmtDate(shipment.eta)}</dd>
                </div>
              </dl>

              <div className="docs">
                <span className="docs-label">Documents</span>
                {shipment.documents.length === 0 ? (
                  <span className="docs-none">None yet</span>
                ) : (
                  <ul className="doc-list">
                    {shipment.documents.map((doc) => (
                      <li key={doc.id} className="doc">
                        <span className="doc-name">{doc.doc_type}</span>
                        <span className="doc-state">
                          {doc.available ? 'Available' : 'Not uploaded yet'}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          ))}
        </>
      )}
    </>
  )
}

export default function App() {
  const [session, setSession] = useState(null)
  const [openOrderId, setOpenOrderId] = useState(null)

  function signOut() {
    delete axios.defaults.headers.common.Authorization
    setOpenOrderId(null)
    setSession(null)
  }

  return (
    <div className="page">
      <Header />
      <main className="main">
        {!session && <LoginScreen onSignedIn={setSession} />}

        {session && openOrderId === null && (
          <OrdersScreen
            session={session}
            onSignOut={signOut}
            onOpenOrder={setOpenOrderId}
          />
        )}

        {session && openOrderId !== null && (
          <OrderDetailScreen
            orderId={openOrderId}
            session={session}
            onBack={() => setOpenOrderId(null)}
            onSignOut={signOut}
          />
        )}
      </main>
      <footer className="footer">
        Stainless steel bright bars · Mumbai, India
      </footer>
    </div>
  )
}
