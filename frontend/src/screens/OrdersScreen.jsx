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
      <Toolbar
        title="Your orders"
        subtitle={`${session.customer?.name} · signed in as ${session.email}`}
      >
        <button type="button" className="button button--ghost" onClick={onChangePassword}>
          Change password
        </button>
        <button type="button" className="button button--ghost" onClick={onSignOut}>
          Sign out
        </button>
      </Toolbar>

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
            {/* The roles repeat what the elements already are. On a narrow
                screen the CSS draws each row as a card, and a table drawn as
                blocks stops being a table to a screen reader in some
                browsers unless the roles are stated. data-label is the
                caption each card shows above its grade and quantity. */}
            <table className="table" role="table">
              <thead role="rowgroup">
                <tr role="row">
                  <th role="columnheader">Sales Order</th>
                  <th role="columnheader">Grade</th>
                  <th role="columnheader">Description</th>
                  <th role="columnheader" className="num">Ordered quantity</th>
                  <th role="columnheader">Status</th>
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
                    <td role="cell" className="num mono cell-qty" data-label="Ordered">
                      {order.ordered_qty} {order.unit}
                    </td>
                    <td role="cell" className="cell-status">
                      <StatusPill status={order.status} />
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
