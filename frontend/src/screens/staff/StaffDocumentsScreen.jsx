import { useEffect, useState } from 'react'
import axios from 'axios'
import StatusPill from '../../components/StatusPill'
import StaffPhotoStrip from './StaffPhotoStrip'
import { describeError } from '../../lib/format'

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
          {busy ? 'Working…' : doc.uploaded ? doc.file_name : 'Not uploaded yet'}
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
export default function StaffDocumentsScreen() {
  const [state, setState] = useState('loading')
  const [shipments, setShipments] = useState([])
  const [onlyIncomplete, setOnlyIncomplete] = useState(false)

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

  const shown = onlyIncomplete
    ? shipments.filter((s) => s.missing_count > 0)
    : shipments
  const incomplete = shipments.filter((s) => s.missing_count > 0).length

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
            Couldn&apos;t load the shipments. Please try again.
          </p>
        </div>
      )}

      {state === 'unauthorised' && (
        <div className="card">
          <p className="message message--error" role="alert">
            Your session has expired. Please sign in again.
          </p>
        </div>
      )}

      {state === 'ready' && shipments.length === 0 && (
        <div className="card">
          <p className="message">
            There are no shipments yet. Add one under Orders, or import them.
          </p>
        </div>
      )}

      {state === 'ready' && shipments.length > 0 && (
        <>
          <div className="card card--summary">
            <p className="summary">
              {incomplete === 0
                ? `All ${shipments.length} shipments have every document.`
                : `${incomplete} of ${shipments.length} shipments are missing documents.`}
            </p>
            <label className="checkline">
              <input
                type="checkbox"
                checked={onlyIncomplete}
                onChange={(e) => setOnlyIncomplete(e.target.checked)}
              />
              <span>Show only shipments with something missing</span>
            </label>
          </div>

          {shown.map((shipment) => (
            <div className="card" key={shipment.id}>
              <div className="shipment-head">
                <div>
                  <h3 className="shipment-no">{shipment.shipment_no}</h3>
                  <p className="shipment-sub">
                    {shipment.customer_name} ({shipment.customer_code}) ·{' '}
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
              <p className="message">Nothing missing. Every document is attached.</p>
            </div>
          )}
        </>
      )}
    </>
  )
}
