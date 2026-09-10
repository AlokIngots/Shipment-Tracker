import { useEffect, useState } from 'react'
import axios from 'axios'
import PhotoGallery from '../components/PhotoGallery'
import StatusPill from '../components/StatusPill'
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
              ? 'Try again'
              : 'Download'}
        </button>
      ) : (
        <span className="doc-state">Not uploaded yet</span>
      )}
    </li>
  )
}

export default function OrderDetailScreen({ orderId, onBack, onSignOut, session }) {
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
      <Toolbar
        title={state === 'ready' ? order.sales_order_no : 'Order'}
        subtitle={session.customer?.name}
        onBack={onBack}
        backLabel="Back to orders"
      >
        <button type="button" className="button button--ghost" onClick={onSignOut}>
          Sign out
        </button>
      </Toolbar>

      {state === 'loading' && (
        <div className="card">
          <p className="message">Loading order…</p>
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
                <dd className="mono">{order.customer_po || DASH}</dd>
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
                    {shipment.vessel_name || DASH}
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
                  <dd className="mono">{shipment.imo_number || DASH}</dd>
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

              <PhotoGallery photos={shipment.photos} />

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
