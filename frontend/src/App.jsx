import { useEffect, useState } from 'react'
import axios from 'axios'

// Pre-fills the login form during development so the demo is easy to try.
// Read from frontend/.env, which is never committed, so no credentials live
// in the repository. Blank when unset, which is what production wants.
const DEMO_EMAIL = import.meta.env.VITE_DEMO_EMAIL ?? ''
const DEMO_PASSWORD = import.meta.env.VITE_DEMO_PASSWORD ?? ''

// Where the sign-in token is kept between page loads.
//
// sessionStorage, not localStorage, on purpose. sessionStorage survives a
// refresh and a link opened in the same tab, and is thrown away when the tab
// is closed. localStorage would survive the browser being closed and
// reopened, which is convenient on your own laptop and wrong on the shared
// machine in a shipping office.
//
// Wrapped in try/catch because a browser set to block site data throws
// rather than returning nothing, and being unable to remember a token is not
// a reason to fail to load the portal.
const TOKEN_KEY = 'alok.portal.token'

function rememberToken(token) {
  try {
    sessionStorage.setItem(TOKEN_KEY, token)
  } catch {
    // Nothing to do: the portal still works, it just forgets on refresh.
  }
}

function recallToken() {
  try {
    return sessionStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

function forgetToken() {
  try {
    sessionStorage.removeItem(TOKEN_KEY)
  } catch {
    // Nothing to do.
  }
}

function useToken(token) {
  axios.defaults.headers.common.Authorization = `Bearer ${token}`
  rememberToken(token)
}

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
      // knows which customer is asking. Kept for the tab, so a refresh does
      // not throw the customer back to this screen.
      useToken(res.data.token)
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

      {DEMO_EMAIL && (
        <p className="demo-note">
          Demo account — pre-filled above.
        </p>
      )}
    </div>
  )
}

// Shown two ways: forced, when staff have just handed over a temporary
// password and nothing else may be seen until it is replaced; and by choice,
// from the orders screen. The server enforces the forced case regardless of
// what this screen does - it will not return an order to somebody who is
// still on a temporary password.
function ChangePasswordScreen({ session, forced, onDone, onCancel, onSignOut }) {
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const longEnough = next.length >= 12

  async function handleSubmit(event) {
    event.preventDefault()
    setError(null)

    if (next !== confirm) {
      setError('The two new passwords do not match.')
      return
    }

    setBusy(true)
    try {
      const res = await axios.post('/api/change-password', {
        current_password: current,
        new_password: next,
      })
      // Changing the password signs out every token issued before it,
      // including the one that made this request. The server hands back a
      // replacement so this tab stays signed in and other places do not.
      if (res.data?.token) useToken(res.data.token)
      onDone()
    } catch (err) {
      // The server is the authority on what makes a password acceptable, so
      // show what it said rather than guessing here.
      setError(
        err.response?.data?.detail ??
          'Could not reach the server. Please try again.',
      )
      setBusy(false)
    }
  }

  return (
    <div className="card card--login">
      <h2>{forced ? 'Choose your password' : 'Change your password'}</h2>

      {forced ? (
        <p className="lead">
          You are signed in with a temporary password given to you by Alok
          Ingots. Please choose your own before continuing.
        </p>
      ) : (
        <p className="lead">
          Signed in as {session.email}.
        </p>
      )}

      <form onSubmit={handleSubmit} noValidate>
        <label className="field">
          <span>{forced ? 'Temporary password' : 'Current password'}</span>
          <input
            type="password"
            value={current}
            autoComplete="current-password"
            onChange={(e) => setCurrent(e.target.value)}
          />
        </label>

        <label className="field">
          <span>New password</span>
          <input
            type="password"
            value={next}
            autoComplete="new-password"
            onChange={(e) => setNext(e.target.value)}
          />
        </label>

        <label className="field">
          <span>New password again</span>
          <input
            type="password"
            value={confirm}
            autoComplete="new-password"
            onChange={(e) => setConfirm(e.target.value)}
          />
        </label>

        {/* Say what is needed while it is being typed, rather than refusing
            it afterwards. The server still decides; this only stops the
            rule being a surprise. */}
        <p className={longEnough ? 'hint hint--met' : 'hint'}>
          {longEnough
            ? 'Long enough.'
            : `At least 12 characters — ${next.length} so far.`}
          {' '}Longer is better than complicated.
        </p>

        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}

        <button type="submit" className="button" disabled={busy}>
          {busy ? 'Saving…' : 'Save new password'}
        </button>

        {!forced && (
          <button
            type="button"
            className="button button--ghost button--block"
            onClick={onCancel}
            disabled={busy}
          >
            Cancel
          </button>
        )}
      </form>

      {forced && (
        <p className="demo-note">
          <button type="button" className="linkish" onClick={onSignOut}>
            Sign out instead
          </button>
        </p>
      )}
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

function OrdersScreen({ session, onSignOut, onOpenOrder, onChangePassword }) {
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
        <div className="toolbar-actions">
          <button
            type="button"
            className="button button--ghost"
            onClick={onChangePassword}
          >
            Change password
          </button>
          <button type="button" className="button button--ghost" onClick={onSignOut}>
            Sign out
          </button>
        </div>
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


function DocumentRow({ doc }) {
  // 'idle' -> 'busy' | 'failed'
  const [state, setState] = useState('idle')

  async function download() {
    setState('busy')
    try {
      const res = await axios.get(`/api/documents/${doc.id}/download`, {
        responseType: 'blob',
      })
      // The request needs the sign-in token, so it cannot be a plain link.
      // Fetch it, then hand the file to the browser to save.
      const url = URL.createObjectURL(res.data)
      const link = document.createElement('a')
      link.href = url
      link.download = doc.file_name
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(url)
      setState('idle')
    } catch {
      setState('failed')
    }
  }

  return (
    <li className="doc">
      <span className="doc-name">{doc.doc_type}</span>
      {doc.available ? (
        <button
          type="button"
          className="doc-download"
          onClick={download}
          disabled={state === 'busy'}
        >
          {state === 'busy' ? 'Preparing\u2026' : state === 'failed' ? 'Try again' : 'Download'}
        </button>
      ) : (
        <span className="doc-state">Not uploaded yet</span>
      )}
    </li>
  )
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
          <p className="message">Loading order&hellip;</p>
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
                  <dd>
                    {shipment.vessel_name || '\u2014'}
                    {shipment.tracking_url && (
                      <a
                        className="track"
                        href={shipment.tracking_url}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        View live on {shipment.tracking_provider}
                      </a>
                    )}
                  </dd>
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
                      <DocumentRow key={doc.id} doc={doc} />
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
  // 'restoring' while a remembered token is being checked, so the login
  // screen does not flash up for somebody who is already signed in.
  const [restoring, setRestoring] = useState(true)
  const [session, setSession] = useState(null)
  const [openOrderId, setOpenOrderId] = useState(null)
  const [changingPassword, setChangingPassword] = useState(false)
  const [passwordChanged, setPasswordChanged] = useState(false)

  // On load, see whether this tab already holds a token and whether the
  // server still accepts it. A token can be refused for good reasons -
  // expired, password changed elsewhere, account deactivated - and all of
  // them mean the same thing here: show the login screen.
  useEffect(() => {
    const token = recallToken()
    if (!token) {
      setRestoring(false)
      return
    }

    let cancelled = false
    axios.defaults.headers.common.Authorization = `Bearer ${token}`

    axios
      .get('/api/me')
      .then((res) => {
        if (cancelled) return
        setSession({ ...res.data, token })
      })
      .catch(() => {
        if (cancelled) return
        forgetToken()
        delete axios.defaults.headers.common.Authorization
      })
      .finally(() => {
        if (!cancelled) setRestoring(false)
      })

    return () => {
      cancelled = true
    }
  }, [])

  function signOut() {
    forgetToken()
    delete axios.defaults.headers.common.Authorization
    setOpenOrderId(null)
    setChangingPassword(false)
    setPasswordChanged(false)
    setSession(null)
  }

  // Nothing but the password screen is reachable until a temporary password
  // has been replaced.
  const mustChangePassword = Boolean(session?.must_change_password)

  function passwordWasChanged() {
    setSession({ ...session, must_change_password: false })
    setChangingPassword(false)
    setPasswordChanged(true)
  }

  return (
    <div className="page">
      <Header />
      <main className="main">
        {restoring && <p className="message">Signing you in…</p>}

        {!restoring && !session && <LoginScreen onSignedIn={setSession} />}

        {session && (mustChangePassword || changingPassword) && (
          <ChangePasswordScreen
            session={session}
            forced={mustChangePassword}
            onDone={passwordWasChanged}
            onCancel={() => setChangingPassword(false)}
            onSignOut={signOut}
          />
        )}

        {session && !mustChangePassword && !changingPassword && passwordChanged && (
          <p className="banner" role="status">
            Your password has been changed.
          </p>
        )}

        {session && !mustChangePassword && !changingPassword && openOrderId === null && (
          <OrdersScreen
            session={session}
            onSignOut={signOut}
            onOpenOrder={setOpenOrderId}
            onChangePassword={() => setChangingPassword(true)}
          />
        )}

        {session && !mustChangePassword && !changingPassword && openOrderId !== null && (
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
