import { useEffect, useState } from 'react'
import axios from 'axios'
import StatusPill from '../components/StatusPill'
import Toolbar from '../components/Toolbar'

export default function OrdersScreen({
  session,
  onSignOut,
  onOpenOrder,
  onChangePassword,
}) {
  // 'loading' -> 'ready' | 'error' | 'unauthorised'
  const [state, setState] = useState('loading')
  const [orders, setOrders] = useState([])
  // Bumped by Try again, which runs the request below once more.
  const [attempt, setAttempt] = useState(0)

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
  }, [attempt])

  function tryAgain() {
    setState('loading')
    setAttempt((n) => n + 1)
  }

  const company = session.customer?.name

  return (
    <>
      <Toolbar
        title="Your orders"
        subtitle={company ? `${company} · signed in as ${session.email}` : `Signed in as ${session.email}`}
      >
        <button type="button" className="button button--ghost" onClick={onChangePassword}>
          Change password
        </button>
        <button type="button" className="button button--ghost" onClick={onSignOut}>
          Sign out
        </button>
      </Toolbar>

      {state === 'ready' && orders.length > 0 && (
        <p className="intro">
          Choose an order to see its shipments, your documents and where your
          goods are now.
        </p>
      )}

      <div className="card">
        {state === 'loading' && <p className="message">Loading your orders…</p>}

        {state === 'error' && (
          <div className="empty" role="alert">
            <p className="empty-title">We couldn&apos;t load your orders just now</p>
            <p className="empty-text">This is usually a short connection problem.</p>
            <button type="button" className="button" onClick={tryAgain}>
              Try again
            </button>
          </div>
        )}

        {state === 'unauthorised' && (
          <div className="empty" role="alert">
            <p className="empty-title">You have been signed out</p>
            <p className="empty-text">
              For your security, the portal signs you out after a while. Please
              sign in again.
            </p>
            <button type="button" className="button" onClick={onSignOut}>
              Sign in again
            </button>
          </div>
        )}

        {state === 'ready' && orders.length === 0 && (
          <div className="empty">
            <p className="empty-title">No orders here yet</p>
            <p className="empty-text">
              When Alok Ingots adds an order for {company || 'your company'}, it
              will appear here with its status, shipments and documents. If you
              are expecting one already, please contact your Alok Ingots sales
              contact.
            </p>
          </div>
        )}

        {state === 'ready' && orders.length > 0 && (
          <div className="table-wrap">
            {/* The roles repeat what the elements already are. On a narrow
                screen the CSS draws each row as a card, and a table drawn as
                blocks stops being a table to a screen reader in some
                browsers unless the roles are stated. data-label is the
                caption each card shows above its grade and quantity. */}
            <table className="table" role="table">
              <thead role="rowgroup">
                <tr role="row">
                  <th role="columnheader">Order number</th>
                  <th role="columnheader">Grade</th>
                  <th role="columnheader">Product</th>
                  <th role="columnheader" className="num">Quantity</th>
                  <th role="columnheader">Order status</th>
                  <th role="columnheader" />
                </tr>
              </thead>
              <tbody role="rowgroup">
                {orders.map((order) => (
                  <tr
                    key={order.id}
                    role="row"
                    className="row--clickable"
                    onClick={() => onOpenOrder(order.id)}
                  >
                    <td role="cell" className="mono link cell-so">
                      {order.sales_order_no}
                    </td>
                    <td role="cell" className="cell-grade" data-label="Grade">
                      {order.grade}
                    </td>
                    <td role="cell" className="cell-desc">
                      {order.description}
                    </td>
                    {/* Quantity is rendered exactly as the API sends it. */}
                    <td role="cell" className="num mono cell-qty" data-label="Quantity">
                      {order.ordered_qty} {order.unit}
                    </td>
                    <td role="cell" className="cell-status">
                      <StatusPill status={order.status} emptyLabel="Awaiting update" />
                    </td>
                    <td role="cell" className="chevron">
                      &#8250;
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
