import { useEffect, useState } from 'react'
import axios from 'axios'
import StartHere from '../../components/StartHere'
import StatusPill from '../../components/StatusPill'
import StaffPhotoStrip from './StaffPhotoStrip'
import { describeError, plural } from '../../lib/format'

function StaffDocumentRow({ shipment, doc, onChanged }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function upload(event) {
    const file = event.target.files?.[0]
    // Clear it, or choosing the same file twice in a row does nothing.
    event.target.value = ''
    if (!file) return

    setBusy(true)
    setError(null)
    const form = new FormData()
    form.append('doc_type', doc.doc_type)
    form.append('file', file)

    try {
      await axios.post(`/api/staff/shipments/${shipment.id}/documents`, form)
      await onChanged()
    } catch (err) {
      setError(describeError(err, 'Could not upload that file. Please try again.'))
    } finally {
      setBusy(false)
    }
  }

  async function remove() {
    if (!window.confirm(`Remove the ${doc.doc_type} from ${shipment.shipment_no}?`)) return
    setBusy(true)
    setError(null)
    try {
      await axios.delete(`/api/staff/documents/${doc.document_id}`)
      await onChanged()
    } catch (err) {
      setError(describeError(err, 'Could not remove that document.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="docrow">
      <span className={doc.uploaded ? 'dot dot--on' : 'dot'} aria-hidden="true" />
      <div className="docrow-main">
        <span className="docrow-type">{doc.doc_type}</span>
        <span className="docrow-file">
          {busy
            ? 'Working…'
            : doc.uploaded
              ? doc.file_name
              : 'Not uploaded yet — the customer cannot see it'}
        </span>
        {error && (
          <span className="docrow-error" role="alert">
            {error}
          </span>
        )}
      </div>

      <div className="docrow-actions">
        <label className={busy ? 'minibutton minibutton--off' : 'minibutton'}>
          {doc.uploaded ? 'Replace' : 'Upload'}
          <input
            type="file"
            accept=".pdf,.jpg,.jpeg,.png"
            hidden
            disabled={busy}
            onChange={upload}
          />
        </label>
        {doc.uploaded && (
          <button
            type="button"
            className="minibutton minibutton--quiet"
            onClick={remove}
            disabled={busy}
          >
            Remove
          </button>
        )}
      </div>
    </div>
  )
}

// Which of the four documents each shipment has, and Upload / Replace /
// Remove on every one of them.
export default function StaffDocumentsScreen({ startWith, onGo }) {
  const [state, setState] = useState('loading')
  const [shipments, setShipments] = useState([])
  // Arriving from the Upload document quick action: show what still needs
  // something. Arriving from one shipment's button: show only that one.
  const [onlyIncomplete, setOnlyIncomplete] = useState(startWith?.action === 'upload')
  const [focus, setFocus] = useState(startWith?.shipmentId ?? null)

  async function load() {
    try {
      const res = await axios.get('/api/staff/shipments')
      setShipments(res.data)
      setState('ready')
    } catch (err) {
      setState(err.response?.status === 401 ? 'unauthorised' : 'error')
    }
  }

  useEffect(() => {
    load()
  }, [])

  const incomplete = shipments.filter((s) => s.missing_count > 0).length
  const shown =
    focus !== null
      ? shipments.filter((s) => s.id === focus)
      : onlyIncomplete
        ? shipments.filter((s) => s.missing_count > 0)
        : shipments

  return (
    <>
      {state === 'loading' && (
        <div className="card">
          <p className="message">Loading shipments…</p>
        </div>
      )}

      {state === 'error' && (
        <div className="card">
          <p className="message message--error" role="alert">
            Couldn&apos;t load the shipments. Please refresh the page to try again.
          </p>
        </div>
      )}

      {state === 'unauthorised' && (
        <div className="card">
          <p className="message message--error" role="alert">
            You have been signed out. Please sign in again.
          </p>
        </div>
      )}

      {state === 'ready' && shipments.length === 0 && (
        <>
          <StartHere onGo={onGo} />
          <div className="card">
            <div className="empty">
              <p className="empty-title">No shipments yet</p>
              <p className="empty-text">
                Documents and photos are uploaded against a shipment. Open an
                order and press Add shipment, then come back here.
              </p>
              <button type="button" className="button" onClick={() => onGo('orders')}>
                Go to orders
              </button>
            </div>
          </div>
        </>
      )}

      {state === 'ready' && shipments.length > 0 && (
        <>
          <div className="card card--summary">
            <p className="summary">
              {focus !== null
                ? `Showing ${shown[0]?.shipment_no ?? 'one shipment'} only.`
                : incomplete === 0
                  ? `All ${plural(shipments.length, 'shipment')} have every document.`
                  : `${incomplete} of ${plural(shipments.length, 'shipment')} are missing documents.`}
            </p>
            {focus !== null ? (
              <button type="button" className="minibutton" onClick={() => setFocus(null)}>
                Show all shipments
              </button>
            ) : (
              <label className="checkline">
                <input
                  type="checkbox"
                  checked={onlyIncomplete}
                  onChange={(e) => setOnlyIncomplete(e.target.checked)}
                />
                <span>Show only shipments with something missing</span>
              </label>
            )}
          </div>

          <p className="guide" role="note">
            Press <strong>Upload</strong> beside a document and choose the file:
            PDF, JPG or PNG, up to 20 MB. The customer can download it as soon
            as it is uploaded.
          </p>

          {shown.map((shipment) => (
            <div className="card" key={shipment.id}>
              <div className="shipment-head">
                <div>
                  <h3 className="shipment-no">{shipment.shipment_no}</h3>
                  <p className="shipment-sub">
                    {shipment.customer_name} ({shipment.customer_code}) · order{' '}
                    {shipment.sales_order_no}
                    {shipment.vessel_name ? ` · ${shipment.vessel_name}` : ''}
                  </p>
                </div>
                <StatusPill status={shipment.status} />
              </div>

              {shipment.documents.map((doc) => (
                <StaffDocumentRow
                  key={doc.doc_type}
                  shipment={shipment}
                  doc={doc}
                  onChanged={load}
                />
              ))}

              <StaffPhotoStrip shipment={shipment} />
            </div>
          ))}

          {shown.length === 0 && (
            <div className="card">
              <p className="message">
                {focus !== null
                  ? 'That shipment is no longer here. It may have been removed.'
                  : 'Nothing missing. Every shipment has all its documents.'}
              </p>
            </div>
          )}
        </>
      )}
    </>
  )
}
