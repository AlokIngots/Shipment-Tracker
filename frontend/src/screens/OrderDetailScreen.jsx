import { useEffect, useState } from 'react'
import axios from 'axios'
import PhotoGallery from '../components/PhotoGallery'
import StatusPill from '../components/StatusPill'
import StatusTrack from '../components/StatusTrack'
import Toolbar from '../components/Toolbar'
import { DASH, fmtDate } from '../lib/format'

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
          {state === 'busy'
            ? 'Preparing…'
            : state === 'failed'
              ? 'Did not download — try again'
              : 'Download'}
        </button>
      ) : (
        <span className="doc-state">Not ready yet</span>
      )}
    </li>
  )
}

// Where the goods are, in the words a buyer uses. Only what is known is
// shown: a column of dashes before a vessel is booked looks broken, when all
// it means is "not yet".
function Tracking({ shipment }) {
  const facts = [
    ['Vessel', shipment.vessel_name],
    ['Vessel IMO number', shipment.imo_number],
    ['Container number', shipment.container_no],
    ['Bill of Lading number', shipment.bl_number],
    ['Departure date', shipment.etd && fmtDate(shipment.etd)],
    ['Expected arrival', shipment.eta && fmtDate(shipment.eta)],
  ].filter(([, value]) => value)

  return (
    <div className="docs">
      <span className="docs-label">Track your shipment</span>

      {facts.length === 0 && !shipment.tracking_url && (
        <p className="docs-none">
          The vessel, container and dates will appear here once this shipment
          is booked.
        </p>
      )}

      {facts.length > 0 && (
        <dl className="facts facts--tight">
          {facts.map(([label, value]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      )}

      {shipment.tracking_url && (
        <p className="track-line">
          <a
            className="track track--button"
            href={shipment.tracking_url}
            target="_blank"
            rel="noopener noreferrer"
          >
            See where the vessel is now
          </a>
          <span className="track-by">Opens {shipment.tracking_provider} in a new tab</span>
        </p>
      )}
    </div>
  )
}

export default function OrderDetailScreen({ orderId, onBack, onSignOut, session }) {
  // 'loading' -> 'ready' | 'error' | 'notfound'
  const [state, setState] = useState('loading')
  const [order, setOrder] = useState(null)
  const [attempt, setAttempt] = useState(0)

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
  }, [orderId, attempt])

  function tryAgain() {
    setState('loading')
    setAttempt((n) => n + 1)
  }

  return (
    <>
      <Toolbar
        title={state === 'ready' ? `Order ${order.sales_order_no}` : 'Your order'}
        subtitle={session.customer?.name}
        onBack={onBack}
        backLabel="All your orders"
      >
        <button type="button" className="button button--ghost" onClick={onSignOut}>
          Sign out
        </button>
      </Toolbar>

      {state === 'loading' && (
        <div className="card">
          <p className="message">Loading your order…</p>
        </div>
      )}

      {state === 'notfound' && (
        <div className="card">
          <div className="empty" role="alert">
            <p className="empty-title">We couldn&apos;t find that order</p>
            <p className="empty-text">
              It may have been changed or removed. Your current orders are on
              the list.
            </p>
            <button type="button" className="button" onClick={onBack}>
              Back to your orders
            </button>
          </div>
        </div>
      )}

      {state === 'error' && (
        <div className="card">
          <div className="empty" role="alert">
            <p className="empty-title">We couldn&apos;t load this order just now</p>
            <p className="empty-text">This is usually a short connection problem.</p>
            <button type="button" className="button" onClick={tryAgain}>
              Try again
            </button>
          </div>
        </div>
      )}

      {state === 'ready' && (
        <>
          <div className="card">
            <div className="status-line">
              <span className="status-label">Order status</span>
              <StatusPill status={order.status} emptyLabel="Awaiting update" />
            </div>
            {order.description && <p className="detail-desc">{order.description}</p>}

            <dl className="facts">
              <div>
                <dt>Your PO number</dt>
                <dd>{order.customer_po || DASH}</dd>
              </div>
              <div>
                <dt>Grade</dt>
                <dd>{order.grade || DASH}</dd>
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
                <span className="total-label">Shipped so far</span>
                <span className="total-value">
                  {order.dispatched_qty} <em>{order.unit}</em>
                </span>
              </div>
              <div className="total total--balance">
                <span className="total-label">Still to ship</span>
                <span className="total-value">
                  {order.balance_qty} <em>{order.unit}</em>
                </span>
              </div>
            </div>
          </div>

          <h3 className="section-title">
            Your shipments{order.shipments.length > 0 ? ` (${order.shipments.length})` : ''}
          </h3>

          {order.shipments.length === 0 && (
            <div className="card">
              <div className="empty">
                <p className="empty-title">Nothing has shipped yet</p>
                <p className="empty-text">
                  Each shipment will appear here as it leaves, with its
                  documents and a link to follow the vessel.
                </p>
              </div>
            </div>
          )}

          {order.shipments.map((shipment) => (
            <div className="card shipment" key={shipment.id}>
              <div className="shipment-head">
                <div>
                  <span className="shipment-no">Shipment {shipment.shipment_no}</span>
                  <span className="shipment-qty">
                    {shipment.dispatched_qty} {shipment.unit}
                    {/* Explains an order that says Delivered with a few
                        tonnes of balance left: this was the last lot. */}
                    {shipment.is_final && ' · final shipment'}
                  </span>
                </div>
                <StatusPill status={shipment.status} emptyLabel="Awaiting update" />
              </div>

              <StatusTrack status={shipment.status} />

              <Tracking shipment={shipment} />

              <PhotoGallery photos={shipment.photos} />

              <div className="docs">
                <span className="docs-label">Your documents</span>
                {shipment.documents.length === 0 ? (
                  <p className="docs-none">
                    Your packing list, invoice, Bill of Lading and test
                    certificates will appear here as soon as they are ready.
                  </p>
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
