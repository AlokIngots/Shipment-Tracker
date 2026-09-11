import { useEffect, useState } from 'react'
import axios from 'axios'
import StartHere from '../../components/StartHere'
import StatusPill, { PART_SHIPPED } from '../../components/StatusPill'
import { describeError, fmtDate, plural } from '../../lib/format'
import OrderForm from './OrderForm'
import ShipmentForm from './ShipmentForm'

function ShipmentRow({ shipment, onEdit, onRemove, onDocuments, busy }) {
  // Only what is known, joined into one line. A row of dashes before a vessel
  // is booked reads as broken, when all it means is "not yet".
  const facts = [
    `${shipment.dispatched_qty} ${shipment.unit ?? ''}`.trim(),
    shipment.is_final && 'last shipment',
    shipment.vessel_name &&
      `${shipment.vessel_name}${shipment.imo_number ? ` (IMO ${shipment.imo_number})` : ''}`,
    shipment.etd && `departs ${fmtDate(shipment.etd)}`,
    shipment.eta && `arrives ${fmtDate(shipment.eta)}`,
    shipment.container_no && `container ${shipment.container_no}`,
    shipment.bl_number && `B/L ${shipment.bl_number}`,
    plural(shipment.document_count, 'document'),
  ].filter(Boolean)

  return (
    <div className="shiprow">
      <div className="shiprow-main">
        <span className="mono shiprow-no">{shipment.shipment_no}</span>
        <span className="shiprow-facts">{facts.join(' · ')}</span>
      </div>
      <StatusPill status={shipment.status} />
      <div className="docrow-actions">
        <button type="button" className="minibutton" onClick={onEdit} disabled={busy}>
          Edit
        </button>
        <button type="button" className="minibutton" onClick={onDocuments} disabled={busy}>
          Documents & photos
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

function OrderCard({ order, onEdit, onRemoveOrder, onRemoveShipment, onSaved, onGo, busy }) {
  // Which form, if any, is open under this order: null, 'new', or a shipment.
  const [shipmentForm, setShipmentForm] = useState(null)

  async function saved() {
    setShipmentForm(null)
    await onSaved()
  }

  // Nothing ticks the last shipment for staff, because steel orders finish a
  // few tonnes over or under. So when nearly all of an order has gone and no
  // lot is ticked, say so -- otherwise it would read Part shipped for ever.
  // Only a reminder: the 90% is not a rule the server applies.
  const tickForgotten =
    order.status === PART_SHIPPED &&
    !order.shipments.some((s) => s.is_final) &&
    Number(order.ordered_qty) > 0 &&
    Number(order.dispatched_qty) >= Number(order.ordered_qty) * 0.9

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
          <span className="total-label">Still to dispatch</span>
          <span className="total-value">
            {order.balance_qty} <em>{order.unit}</em>
          </span>
        </div>
      </div>

      {tickForgotten && (
        <p className="guide" role="status">
          {order.dispatched_qty} of {order.ordered_qty} {order.unit} has been
          dispatched, but no shipment is ticked as the last one, so the
          customer sees “Part shipped”. If nothing more is going on this order,
          edit its final shipment and tick “Last shipment”.
        </p>
      )}

      {order.shipments.length === 0 && !shipmentForm && (
        <p className="message message--quiet">
          No shipments yet. Press Add shipment when part of this order is dispatched.
        </p>
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
            onDocuments={() => onGo('documents', { shipmentId: shipment.id })}
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
// create and change them.
export default function StaffOrdersScreen({ startWith, onGo }) {
  const [state, setState] = useState('loading')
  const [orders, setOrders] = useState([])
  const [customers, setCustomers] = useState([])
  // null, 'new', or the order being edited. Opens straight away when the
  // New order quick action brought us here.
  const [orderForm, setOrderForm] = useState(startWith?.action === 'new-order' ? 'new' : null)
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
    if (!window.confirm(`Remove order ${order.sales_order_no}?\n\nThis cannot be undone.`)) return
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
    if (!window.confirm(`Remove shipment ${shipment.shipment_no}?\n\nThis cannot be undone.`)) {
      return
    }
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
            ? 'You have been signed out. Please sign in again.'
            : "Couldn't load the orders. Please refresh the page to try again."}
        </p>
      </div>
    )
  }

  const noCustomers = customers.length === 0

  return (
    <>
      {orders.length === 0 && <StartHere onGo={onGo} />}

      <div className="card card--summary">
        <p className="summary">
          {orders.length === 0 ? 'No orders yet.' : `${plural(orders.length, 'order')} in the portal.`}
        </p>
        {noCustomers ? (
          <button
            type="button"
            className="button"
            onClick={() => onGo('accounts', { action: 'new-customer' })}
          >
            Add a customer first
          </button>
        ) : (
          <button
            type="button"
            className="button"
            onClick={() => setOrderForm('new')}
            disabled={orderForm === 'new'}
          >
            New order
          </button>
        )}
      </div>

      {noCustomers && (
        <p className="guide" role="status">
          Every order belongs to a customer, and there are none yet. Add the
          customer first, then come back here to enter their order.
        </p>
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

      {orderForm === 'new' && !noCustomers && (
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
            onGo={onGo}
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
