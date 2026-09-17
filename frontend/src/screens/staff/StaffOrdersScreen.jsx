import { useEffect, useState } from 'react'
import axios from 'axios'
import StartHere from '../../components/StartHere'
import StatusPill, { PART_SHIPPED } from '../../components/StatusPill'
import { describeError, fmtDate, plural } from '../../lib/format'
import OrderForm from './OrderForm'
import ShipmentForm from './ShipmentForm'
import LiveTracking from '../../components/LiveTracking'
import { TrackActions } from '../../components/Tracking'

// Which orders are open, kept for this browser tab only. A save reloads the
// list, and without this every order would shut itself the moment anything
// was changed. sessionStorage rather than localStorage: it is a working
// position, not a preference, and a new tab should start tidy.
const OPEN_KEY = 'staff-orders-open'

function readOpen() {
  try {
    const raw = sessionStorage.getItem(OPEN_KEY)
    return new Set(raw ? JSON.parse(raw) : [])
  } catch {
    // Private windows and locked-down browsers refuse storage. Starting with
    // everything shut is exactly what this screen does anyway.
    return new Set()
  }
}

function writeOpen(ids) {
  try {
    sessionStorage.setItem(OPEN_KEY, JSON.stringify([...ids]))
  } catch {
    // Nothing to do: the list still opens and shuts, it just forgets.
  }
}

// Nothing ticks the last shipment for staff, because steel orders finish a
// few tonnes over or under. So when nearly all of an order has gone and no
// lot is ticked, say so -- otherwise it would read Part shipped for ever.
// Only a reminder: the 90% is not a rule the server applies.
function needsFinalTick(order) {
  return (
    order.status === PART_SHIPPED &&
    !order.shipments.some((s) => s.is_final) &&
    Number(order.ordered_qty) > 0 &&
    Number(order.dispatched_qty) >= Number(order.ordered_qty) * 0.9
  )
}

// Live tracking for one shipment, as staff look after it.
//
// Enable tracking is the one button in the portal that can spend a ShipsGo
// credit, so it asks first, says what it will cost, and the server spends at
// most one credit per B/L however often it is pressed. Refresh and Stop cost
// nothing.
function LiveTrackingControls({ shipment, onTracking, busy }) {
  const live = shipment.live_tracking

  if (!live) {
    const blocked = !shipment.live_tracking_available
      ? 'Live tracking is not set up on this server yet (no ShipsGo key).'
      : !shipment.bl_number
        ? 'Add the Bill of Lading number first — tracking follows the B/L.'
        : null

    function enable() {
      const ok = window.confirm(
        `Turn on live tracking for B/L ${shipment.bl_number}?\n\n` +
          'This uses 1 ShipsGo credit — or none, if ShipsGo is already ' +
          'following this B/L. It is done once for this shipment; after that ' +
          'the portal only reads updates, which are free.',
      )
      if (ok) onTracking(shipment, 'enable')
    }

    return (
      <div className="livecontrols">
        <p className="livecontrols-text">
          Live tracking is off. Customers see the timeline only once it is on.
        </p>
        <button
          type="button"
          className="minibutton"
          onClick={enable}
          disabled={busy || Boolean(blocked)}
          title={blocked ?? undefined}
        >
          Enable tracking (1 credit)
        </button>
        {blocked && <p className="livecontrols-hint">{blocked}</p>}
      </div>
    )
  }

  function stop() {
    const ok = window.confirm(
      `Stop live tracking for ${shipment.shipment_no}?\n\n` +
        'The customer stops seeing the timeline. It stays in ShipsGo, so ' +
        'turning it on again for the same B/L uses no credit.',
    )
    if (ok) onTracking(shipment, 'stop')
  }

  const housekeeping = [
    `B/L ${live.booking_number}`,
    `ShipsGo #${live.external_id}`,
    live.enabled_by && `turned on by ${live.enabled_by}`,
    live.reused ? 'no credit used' : '1 credit used',
    live.finished && 'journey finished, ShipsGo no longer updates it',
  ].filter(Boolean)

  return (
    <div className="livecontrols">
      <p className="livecontrols-text">{housekeeping.join(' · ')}</p>
      {live.stale && (
        <p className="message message--error" role="alert">
          The shipment’s B/L number has changed since tracking was turned on,
          so customers are not shown this. Stop tracking, then enable it again
          for the new number.
        </p>
      )}
      {live.last_error && (
        <p className="livecontrols-hint" role="status">
          Last refresh failed: {live.last_error}
        </p>
      )}
      <div className="livecontrols-actions">
        <button
          type="button"
          className="minibutton"
          onClick={() => onTracking(shipment, 'refresh')}
          disabled={busy}
        >
          Refresh now (free)
        </button>
        <button
          type="button"
          className="minibutton minibutton--quiet"
          onClick={stop}
          disabled={busy}
        >
          Stop tracking
        </button>
      </div>
      <LiveTracking tracking={live} staff />
    </div>
  )
}

function ShipmentRow({ shipment, onEdit, onRemove, onDocuments, onTracking, busy }) {
  // Shut by default: a staff list is a list, and an order can hold many
  // lots. Open, it gives the numbers to read down a phone line.
  const [tracking, setTracking] = useState(false)
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
    shipment.carrier,
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
        {/* Always offered: live tracking is switched on from inside it. */}
        <button
          type="button"
          className="minibutton"
          onClick={() => setTracking((open) => !open)}
          aria-expanded={tracking}
        >
          {tracking ? 'Hide tracking' : shipment.live_tracking ? 'Track (live)' : 'Track'}
        </button>
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

      {/* The same link and the same numbers the customer gets, from the
          same function on the server -- so staff on the phone to a customer
          are not reading out something different. */}
      {tracking && (
        <div className="shiprow-tracking">
          <LiveTrackingControls shipment={shipment} onTracking={onTracking} busy={busy} />
          <TrackActions shipment={shipment} />
        </div>
      )}
    </div>
  )
}

// One order as a slim row that opens. Shut, it is the four things staff scan
// for: the sales order number, who it is for, where it has got to, and how
// much of it has gone. Everything else -- the totals, the shipments, the
// tracking and every button -- waits inside until it is asked for.
function OrderRow({
  order,
  open,
  onToggle,
  onEdit,
  onRemoveOrder,
  onRemoveShipment,
  onTracking,
  onSaved,
  onGo,
  busy,
}) {
  // Which form, if any, is open under this order: null, 'new', or a shipment.
  const [shipmentForm, setShipmentForm] = useState(null)

  async function saved() {
    setShipmentForm(null)
    await onSaved()
  }

  const bodyId = `order-body-${order.id}`
  const tickForgotten = needsFinalTick(order)

  return (
    <div className={open ? 'card card--order card--order-open' : 'card card--order'}>
      <button
        type="button"
        className={open ? 'orderhead orderhead--open' : 'orderhead'}
        aria-expanded={open}
        aria-controls={bodyId}
        onClick={onToggle}
      >
        <span className="orderchev" aria-hidden="true" />
        <span className="mono orderno">{order.sales_order_no}</span>
        <span className="ordercust">
          {order.customer_name}
          {order.grade ? ` · ${order.grade}` : ''}
        </span>
        {/* The one thing that must not hide inside a shut row: an order that
            looks unfinished only because nobody ticked the last lot. It sits
            before the three columns on the right so that it takes its width
            from the customer name and leaves those columns lined up. */}
        {tickForgotten && <span className="orderflag">Tick last shipment</span>}
        {/* Dispatched of ordered: the one number that says how far along an
            order is without opening it. */}
        <span className="mono orderqty">
          {order.dispatched_qty} / {order.ordered_qty} <em>{order.unit}</em>
        </span>
        <span className="orderstatus">
          <StatusPill status={order.status} />
        </span>
        <span className="ordermeta">
          {order.shipments.length === 0
            ? 'no shipments'
            : plural(order.shipments.length, 'shipment')}
        </span>
      </button>

      {open && (
        <div className="orderbody" id={bodyId}>
          <p className="ordersub">
            {order.customer_name} ({order.customer_code})
            {order.customer_po ? ` · PO ${order.customer_po}` : ''}
            {order.description ? ` · ${order.description}` : ''}
          </p>

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
              customer sees “Part shipped”. If nothing more is going on this
              order, edit its final shipment and tick “Last shipment”.
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
                onTracking={onTracking}
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
      )}
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
  // Every order shut until it is asked for, however many shipments it has.
  // One rule for the whole list beats a list that opens some rows and not
  // others for reasons nobody can see.
  const [open, setOpen] = useState(readOpen)

  function toggle(id) {
    setOpen((was) => {
      const next = new Set(was)
      if (!next.delete(id)) next.add(id)
      writeOpen(next)
      return next
    })
  }

  function openThese(ids) {
    if (ids.length === 0) return
    setOpen((was) => {
      const next = new Set(was)
      ids.forEach((id) => next.add(id))
      writeOpen(next)
      return next
    })
  }

  async function load() {
    try {
      const [ordersRes, customersRes] = await Promise.all([
        axios.get('/api/staff/orders'),
        axios.get('/api/staff/customers'),
      ])
      setOrders(ordersRes.data)
      setCustomers(customersRes.data)
      setState('ready')
      return ordersRes.data
    } catch (err) {
      setState(err.response?.status === 401 ? 'unauthorised' : 'error')
      return null
    }
  }

  useEffect(() => {
    load()
  }, [])

  // An order just saved opens itself, so the thing that was worked on is the
  // thing on the screen. A new one has no id here until it comes back, so it
  // is found by comparing the list with what was there a moment ago.
  async function afterSave() {
    const edited = orderForm?.id ?? null
    const before = new Set(orders.map((o) => o.id))
    setOrderForm(null)
    setError(null)
    const fresh = await load()
    const added = (fresh ?? []).map((o) => o.id).filter((id) => !before.has(id))
    openThese(edited ? [edited, ...added] : added)
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

  // Enable, refresh or stop live tracking. The server answers with the order
  // as it now stands, so only that order is replaced -- the rest of the list
  // and whatever is open stay exactly where they were.
  async function trackingAction(shipment, kind) {
    const url = `/api/staff/shipments/${shipment.id}/tracking`
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      const res =
        kind === 'enable'
          ? await axios.post(url, { confirm: true })
          : kind === 'refresh'
            ? await axios.post(`${url}/refresh`)
            : await axios.delete(url)
      const updated = res.data.order
      setOrders((list) => list.map((o) => (o.id === updated.id ? updated : o)))
      setNotice(res.data.detail)
    } catch (err) {
      setError(describeError(err, 'Could not change live tracking for that shipment.'))
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
  const openHere = orders.filter((o) => open.has(o.id)).length

  return (
    <>
      {orders.length === 0 && <StartHere onGo={onGo} />}

      <div className="card card--summary">
        <p className="summary">
          {orders.length === 0 ? 'No orders yet.' : `${plural(orders.length, 'order')} in the portal.`}
        </p>
        <div className="summary-actions">
          {/* Only offered when it would do something. One press to shut the
              list again is what makes opening several rows safe. */}
          {openHere > 0 && (
            <button
              type="button"
              className="minibutton"
              onClick={() => {
                setOpen(new Set())
                writeOpen(new Set())
              }}
            >
              Collapse all
            </button>
          )}
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

      <div className="orderlist">
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
            <OrderRow
              key={order.id}
              order={order}
              open={open.has(order.id)}
              onToggle={() => toggle(order.id)}
              busy={busy}
              onGo={onGo}
              onEdit={() => setOrderForm(order)}
              onSaved={load}
              onRemoveOrder={() => removeOrder(order)}
              onRemoveShipment={removeShipment}
              onTracking={trackingAction}
            />
          ),
        )}
      </div>
    </>
  )
}
