import { useEffect, useState } from 'react'
import axios from 'axios'
import LiveTracking from '../components/LiveTracking'
import PhotoGallery from '../components/PhotoGallery'
import StatusPill, { PART_SHIPPED } from '../components/StatusPill'
import StatusTrack from '../components/StatusTrack'
import Toolbar from '../components/Toolbar'
import { CopyButton } from '../components/Tracking'
import { DASH, fmtDate } from '../lib/format'

// Small line icons, drawn inline so they need no file and no permission from
// the Content-Security-Policy. Decoration only: hidden from screen readers.
function DocIcon() {
  return (
    <svg className="doc-icon" viewBox="0 0 20 20" aria-hidden="true" focusable="false">
      <path
        d="M5 2.5h6.5L15.5 6.5V17a.5.5 0 0 1-.5.5H5a.5.5 0 0 1-.5-.5V3a.5.5 0 0 1 .5-.5Z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinejoin="round"
      />
      <path d="M11.5 2.5V6.5h4" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
      <path d="M7.5 10.5h5M7.5 13.5h5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  )
}

function DownloadIcon() {
  return (
    <svg className="doc-download-icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false">
      <path
        d="M8 2.5v7.5M4.75 7 8 10.25 11.25 7M3 13.25h10"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

// An expected document that is not attached yet: the same row, greyed, so
// the customer sees the whole set and which of it is still on its way.
function ComingRow({ docType }) {
  return (
    <li className="doc doc--coming">
      <DocIcon />
      <span className="doc-name">{docType}</span>
      <span className="doc-state">Coming soon</span>
    </li>
  )
}

// How much of the order has gone, as a bar under the three totals. Worked
// out from the same two numbers shown above it, so it cannot disagree.
function shippedShare(order) {
  const ordered = Number.parseFloat(order.ordered_qty)
  const shipped = Number.parseFloat(order.dispatched_qty)
  if (!(ordered > 0) || !(shipped >= 0)) return null
  return Math.min(100, Math.round((shipped / ordered) * 100))
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
      <DocIcon />
      <span className="doc-name">{doc.doc_type}</span>
      {doc.available ? (
        <button
          type="button"
          className="doc-download"
          onClick={download}
          disabled={state === 'busy'}
        >
          {state !== 'busy' && state !== 'failed' && <DownloadIcon />}
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
//
// The IMO number used to be here. It is gone, because the only thing it was
// for was a link to the vessel's position, and that link was wrong for
// transshipped cargo. Staff still see it; it is on the paperwork.
//
// Nothing here leaves the portal. The "Track this container on <carrier>"
// button went on 16 Sep 2026, on Alok's decision: a customer reading their
// own order should not be handed off to somebody else's website. The two
// numbers a carrier or forwarder will ask for are copyable instead, so they
// can be used wherever the customer chooses.
function Tracking({ shipment }) {
  const facts = [
    ['From', shipment.port_of_loading],
    ['To', shipment.port_of_discharge],
    ['Departure date', shipment.etd && fmtDate(shipment.etd)],
    ['Expected arrival', shipment.eta && fmtDate(shipment.eta)],
    ['Shipping line', shipment.carrier],
    ['Vessel', shipment.vessel_name],
    ['Voyage', shipment.voyage_no],
    ['Container number', shipment.container_no, 'copy'],
    ['Container size', shipment.container_size],
    ['Seal number', shipment.seal_no, 'copy'],
    ['Bill of Lading number', shipment.bl_number, 'copy'],
    ['Gross weight', shipment.gross_weight && `${shipment.gross_weight} ${shipment.unit ?? ''}`.trim()],
  ].filter(([, value]) => value)

  return (
    <div className="docs">
      <span className="docs-label">Shipment details</span>

      {facts.length === 0 && (
        <p className="docs-none">
          The route, vessel, container and dates will appear here once this
          shipment is booked.
        </p>
      )}

      {facts.length > 0 && (
        <dl className="facts facts--tight">
          {facts.map(([label, value, copyable]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd className={copyable ? 'fact--copyable' : undefined}>
                <span className={copyable ? 'fact-number' : undefined}>{value}</span>
                {copyable && <CopyButton label={label} value={value} />}
              </dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  )
}

export default function OrderDetailScreen({ orderId, onBack, onChangePassword, onSignOut, session }) {
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
        <button type="button" className="button button--ghost" onClick={onChangePassword}>
          Change password
        </button>
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
            {order.status === PART_SHIPPED && (
              <p className="status-note">
                Some of this order has shipped. More is still to come.
              </p>
            )}
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
              {order.order_date && (
                <div>
                  <dt>Order date</dt>
                  <dd>{fmtDate(order.order_date)}</dd>
                </div>
              )}
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
            {shippedShare(order) !== null && (
              <div className="shipbar">
                <div
                  className="shipbar-track"
                  role="progressbar"
                  aria-label="Share of the order shipped"
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={shippedShare(order)}
                >
                  <span className="shipbar-fill" style={{ width: `${shippedShare(order)}%` }} />
                </div>
                <span className="shipbar-text">{shippedShare(order)}% shipped</span>
              </div>
            )}
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
                  documents and where the container has got to.
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
                    {shipment.is_final && ' · final shipment, nothing more to follow on this order'}
                  </span>
                </div>
                <StatusPill status={shipment.status} emptyLabel="Awaiting update" />
              </div>

              <StatusTrack status={shipment.status} />

              {/* Documents first: they are what a buyer most often opens
                  the portal for. Every expected one is listed, ready to
                  download or marked as coming, so the set is never a guess. */}
              <div className="docs">
                <span className="docs-label">Your documents</span>
                {shipment.documents.length === 0 &&
                (shipment.documents_to_come ?? []).length === 0 ? (
                  <p className="docs-none">
                    Your packing list, invoice, Bill of Lading and test
                    certificates will appear here as soon as they are ready.
                  </p>
                ) : (
                  <ul className="doc-list">
                    {shipment.documents.map((doc) => (
                      <DocumentRow key={doc.id} doc={doc} />
                    ))}
                    {(shipment.documents_to_come ?? []).map((docType) => (
                      <ComingRow key={docType} docType={docType} />
                    ))}
                  </ul>
                )}
              </div>

              <Tracking shipment={shipment} />

              {/* Where the container is now, from the stored copy of
                  ShipsGo's news. Only there once staff have switched it on. */}
              <LiveTracking tracking={shipment.live_tracking} />

              <PhotoGallery photos={shipment.photos} />
            </div>
          ))}
        </>
      )}
    </>
  )
}
