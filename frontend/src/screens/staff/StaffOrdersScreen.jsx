import { useEffect, useState } from 'react'
import axios from 'axios'
import StatusPill from '../../components/StatusPill'
import { DASH, describeError, fmtDate } from '../../lib/format'
import OrderForm from './OrderForm'
import ShipmentForm from './ShipmentForm'

function ShipmentRow({ shipment, onEdit, onRemove, busy }) {
  return (
    <div className="shiprow">
      <div className="shiprow-main">
        <span className="mono shiprow-no">{shipment.shipment_no}</span>
        <span className="shiprow-facts">
          {shipment.dispatched_qty} {shipment.unit} · {shipment.vessel_name || DASH}
          {shipment.imo_number ? ` (IMO ${shipment.imo_number})` : ''} ·{' '}
          {fmtDate(shipment.etd)} → {fmtDate(shipment.eta)}
          {shipment.document_count > 0
            ? ` · ${shipment.document_count} document(s)`
            : ''}
        </span>
      </div>
      <StatusPill status={shipment.status} />
      <div className="docrow-actions">
        <button type="button" className="minibutton" onClick={onEdit} disabled={busy}>
          Edit
        </button>
        <button
          type="button"
          className="minibutton minibutton--quiet"
          onClick={onRemove}
          disabled={busy}
        >
          Remove
        </button>
      </div>
    </div>
  )
}

function OrderCard({ order, onEdit, onRemoveOrder, onRemoveShipment, onSaved, busy }) {
  // Which form, if any, is open under this order: null, 'new', or a shipment.
  const [shipmentForm, setShipmentForm] = useState(null)

  async function saved() {
    setShipmentForm(null)
    await onSaved()
  }

  return (
    <div className="card">
      <div className="shipment-head">
        <div>
          <h3 className="shipment-no">{order.sales_order_no}</h3>
          <p className="shipment-sub">
            {order.customer_name} ({order.customer_code})
            {order.grade ? ` · ${order.grade}` : ''}
            {order.customer_po ? ` · PO ${order.customer_po}` : ''}
          </p>
        </div>
        <StatusPill status={order.status} />
      </div>

      <div className="totals totals--compact">
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

      {order.shipments.length === 0 && !shipmentForm && (
        <p className="message message--quiet">Nothing has shipped against this yet.</p>
      )}

      {order.shipments.map((shipment) =>
        shipmentForm?.id === shipment.id ? (
          <ShipmentForm
            key={shipment.id}
            shipment={shipment}
            onSaved={saved}
            onCancel={() => setShipmentForm(null)}
          />
        ) : (
          <ShipmentRow
            key={shipment.id}
            shipment={shipment}
            busy={busy}
            onEdit={() => setShipmentForm(shipment)}
            onRemove={() => onRemoveShipment(shipment)}
          />
        ),
      )}

      {shipmentForm === 'new' && (
        <ShipmentForm
          orderId={order.id}
          onSaved={saved}
          onCancel={() => setShipmentForm(null)}
        />
      )}

      <div className="card-actions">
        <button
          type="button"
          className="minibutton"
          onClick={() => setShipmentForm('new')}
          disabled={busy || shipmentForm === 'new'}
        >
          Add shipment
        </button>
        <button type="button" className="minibutton" onClick={onEdit} disabled={busy}>
          Edit order
        </button>
        <button
          type="button"
          className="minibutton minibutton--quiet"
          onClick={onRemoveOrder}
          disabled={busy}
        >
          Remove order
        </button>
      </div>
    </div>
  )
}

// The Alok Ingots orders page: every order in the portal, and the forms that
// create and change them. Before this existed an order could only arrive by
// running import_data.py on the server.
export default function StaffOrdersScreen() {
  const [state, setState] = useState('loading')
  const [orders, setOrders] = useState([])
  const [customers, setCustomers] = useState([])
  // null, 'new', or the order being edited.
  const [orderForm, setOrderForm] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)

  async function load() {
    try {
      const [ordersRes, customersRes] = await Promise.all([
        axios.get('/api/staff/orders'),
        axios.get('/api/staff/customers'),
      ])
      setOrders(ordersRes.data)
      setCustomers(customersRes.data)
      setState('ready')
    } catch (err) {
      setState(err.response?.status === 401 ? 'unauthorised' : 'error')
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function afterSave() {
    setOrderForm(null)
    setError(null)
    await load()
  }

  // The server refuses to remove anything that still has something hanging
  // off it, and says so in a sentence. Showing that sentence is the whole
  // handling this needs.
  async function removeOrder(order) {
    if (!window.confirm(`Remove ${order.sales_order_no}?`)) return
    setBusy(true)
    setError(null)
    try {
      const res = await axios.delete(`/api/staff/orders/${order.id}`)
      setNotice(res.data.detail)
      await load()
    } catch (err) {
      setError(describeError(err, 'Could not remove that order.'))
    } finally {
      setBusy(false)
    }
  }

  async function removeShipment(shipment) {
    if (!window.confirm(`Remove shipment ${shipment.shipment_no}?`)) return
    setBusy(true)
    setError(null)
    try {
      const res = await axios.delete(`/api/staff/shipments/${shipment.id}`)
      setNotice(res.data.detail)
      await load()
    } catch (err) {
      setError(describeError(err, 'Could not remove that shipment.'))
    } finally {
      setBusy(false)
    }
  }

  if (state === 'loading') {
    return (
      <div className="card">
        <p className="message">Loading orders…</p>
      </div>
    )
  }

  if (state !== 'ready') {
    return (
      <div className="card">
        <p className="message message--error" role="alert">
          {state === 'unauthorised'
            ? 'Your session has expired. Please sign in again.'
            : "Couldn't load the orders. Please try again."}
        </p>
      </div>
    )
  }

  return (
    <>
      <div className="card card--summary">
        <p className="summary">
          {orders.length === 0
            ? 'No orders yet.'
            : `${orders.length} order(s) in the portal.`}
        </p>
        <button
          type="button"
          className="button"
          onClick={() => setOrderForm('new')}
          disabled={orderForm === 'new' || customers.length === 0}
        >
          New order
        </button>
      </div>

      {customers.length === 0 && (
        <div className="card">
          <p className="message message--error" role="alert">
            There are no customers yet, so an order has nobody to belong to. Add
            one on the server with{' '}
            <code>manage_users.py --add-customer</code>.
          </p>
        </div>
      )}

      {notice && (
        <p className="banner" role="status">
          {notice}
        </p>
      )}

      {error && (
        <div className="card">
          <p className="message message--error" role="alert">
            {error}
          </p>
        </div>
      )}

      {orderForm === 'new' && (
        <OrderForm
          customers={customers}
          onSaved={afterSave}
          onCancel={() => setOrderForm(null)}
        />
      )}

      {orders.map((order) =>
        orderForm?.id === order.id ? (
          <OrderForm
            key={order.id}
            customers={customers}
            order={order}
            onSaved={afterSave}
            onCancel={() => setOrderForm(null)}
          />
        ) : (
          <OrderCard
            key={order.id}
            order={order}
            busy={busy}
            onEdit={() => setOrderForm(order)}
            onSaved={load}
            onRemoveOrder={() => removeOrder(order)}
            onRemoveShipment={removeShipment}
          />
        ),
      )}
    </>
  )
}
