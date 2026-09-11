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
