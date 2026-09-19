import { useRef, useState } from 'react'
import axios from 'axios'
import {
  DOCUMENT_TYPES,
  OTHER,
  TYPE_MAX_LENGTH,
  fileProblem,
  guessDocumentType,
} from '../../lib/docTypeGuess'
import { describeError } from '../../lib/format'

// Several documents onto one shipment in one go. An addition to the Upload
// and Replace buttons on each document row, which work exactly as before.
//
// Each file is sent on its own, one after another, through the same route
// those buttons use -- so the server checks every file exactly as it always
// has, a refused one is refused alone, and nothing new was needed on the
// server. The list then says which went in and which did not.

let nextId = 1

function sizeText(bytes) {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${Math.max(1, Math.round(bytes / 1024))} KB`
}

// The name a row will be saved under: the chosen type, or for Other the
// name typed beside it. '' while there is nothing usable yet.
function typeOf(row) {
  if (row.type === OTHER) return row.otherName.trim()
  return row.type
}

export default function BulkUpload({ shipments, shipmentId, onShipmentChange, onUploaded, onClose }) {
  const [rows, setRows] = useState([])
  const [dragging, setDragging] = useState(false)
  const [running, setRunning] = useState(false)
  const [finished, setFinished] = useState(null)
  const input = useRef(null)

  const shipment = shipments.find((s) => s.id === shipmentId) ?? null
  // Types this shipment already holds, so a row can say it will replace one.
  const onFile = new Set(
    (shipment?.documents ?? []).filter((d) => d.uploaded).map((d) => d.doc_type.toLowerCase()),
  )

  function add(fileList) {
    const files = Array.from(fileList ?? [])
    if (files.length === 0) return
    setFinished(null)
    setRows((current) => [
      // Anything already uploaded from an earlier run leaves the list, so
      // the list is always "what the next Upload all will send".
      ...current.filter((r) => r.state !== 'done'),
      ...files.map((file) => ({
        id: nextId++,
        file,
        type: guessDocumentType(file.name),
        guessed: guessDocumentType(file.name) !== '',
        otherName: '',
        problem: fileProblem(file),
        state: 'waiting',
        error: null,
      })),
    ])
  }

  function update(id, changes) {
    setRows((current) => current.map((r) => (r.id === id ? { ...r, ...changes } : r)))
  }

  function drop(event) {
    event.preventDefault()
    setDragging(false)
    if (!running) add(event.dataTransfer?.files)
  }

  const queued = rows.filter((r) => r.state !== 'done')
  // Two files given the same type: the second would replace the first, so
  // the batch is held until one of them is changed.
  const counts = {}
  for (const r of queued) {
    const t = typeOf(r).toLowerCase()
    if (t) counts[t] = (counts[t] ?? 0) + 1
  }
  const clash = (r) => {
    const t = typeOf(r).toLowerCase()
    return Boolean(t) && counts[t] > 1
  }
  const blockers = queued.filter((r) => r.problem || !typeOf(r) || clash(r))
  const ready = shipment && queued.length > 0 && blockers.length === 0 && !running

  async function uploadAll() {
    if (!ready) return
    setRunning(true)
    setFinished(null)
    let done = 0
    let failed = 0
    for (const row of queued) {
      update(row.id, { state: 'sending', error: null })
      const form = new FormData()
      form.append('doc_type', typeOf(row))
      form.append('file', row.file)
      try {
        await axios.post(`/api/staff/shipments/${shipment.id}/documents`, form)
        update(row.id, { state: 'done' })
        done += 1
      } catch (err) {
        update(row.id, {
          state: 'failed',
          error: describeError(err, 'Could not upload this file.'),
        })
        failed += 1
      }
    }
    setRunning(false)
    setFinished({ done, failed })
    if (done > 0) await onUploaded()
  }

  return (
    <div className="card bulk" aria-labelledby="bulk-title">
      <div className="bulk-head">
        <div>
          <h3 className="form-title" id="bulk-title">
            Upload several documents
          </h3>
          <p className="bulk-lead">
            Pick the shipment, add the files, check the type of each, then press
            Upload all. PDF, JPG or PNG, up to 20 MB each.
          </p>
        </div>
        <button type="button" className="minibutton minibutton--quiet" onClick={onClose} disabled={running}>
          Close
        </button>
      </div>

      <label className="field bulk-shipment">
        <span>Shipment</span>
        <select
          id="bulk-shipment"
          value={shipmentId ?? ''}
          disabled={running}
          onChange={(e) => onShipmentChange(e.target.value ? Number(e.target.value) : null)}
        >
          <option value="">Choose a shipment…</option>
          {shipments.map((s) => (
            <option key={s.id} value={s.id}>
              {s.shipment_no} · order {s.sales_order_no} · {s.customer_name}
            </option>
          ))}
        </select>
      </label>

      <div
        className={dragging ? 'dropzone dropzone--over' : 'dropzone'}
        onDragOver={(e) => {
          e.preventDefault()
          if (!running) setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={drop}
      >
        <p className="dropzone-text">
          <strong>Drag files here</strong>, or
        </p>
        <button
          type="button"
          className="minibutton minibutton--primary"
          onClick={() => input.current?.click()}
          disabled={running}
        >
          Choose files
        </button>
        <input
          ref={input}
          id="bulk-files"
          type="file"
          accept=".pdf,.jpg,.jpeg,.png"
          multiple
          hidden
          onChange={(e) => {
            add(e.target.files)
            // Cleared, or choosing the same files again does nothing.
            e.target.value = ''
          }}
        />
      </div>

      {rows.length > 0 && (
        <ul className="bulk-list" aria-label="Files to upload">
          {rows.map((row) => {
            const saveAs = typeOf(row)
            const replaces = saveAs && onFile.has(saveAs.toLowerCase())
            const note = row.problem
              ? { tone: 'bad', text: row.problem }
              : row.state === 'failed'
                ? { tone: 'bad', text: row.error }
                : row.state === 'done'
                  ? { tone: 'ok', text: 'Uploaded' }
                  : row.state === 'sending'
                    ? { tone: 'quiet', text: 'Uploading…' }
                    : clash(row)
                      ? { tone: 'bad', text: `Another file is also marked ${saveAs}. Change one of them.` }
                      : !saveAs
                        ? {
                            tone: 'quiet',
                            text: row.type === OTHER ? 'Type the name of this document.' : 'Choose what this document is.',
                          }
                        : replaces
                          ? { tone: 'quiet', text: `Replaces the ${saveAs} already uploaded.` }
                          : row.guessed && row.type !== OTHER
                            ? { tone: 'quiet', text: 'Type guessed from the file name.' }
                            : null
            return (
              <li key={row.id} className={`bulk-row bulk-row--${row.state}`}>
                <div className="bulk-file">
                  <span className="bulk-name">{row.file.name}</span>
                  <span className="bulk-size">{sizeText(row.file.size)}</span>
                </div>
                <div className="bulk-type">
                  <select
                    id={`bulk-type-${row.id}`}
                    aria-label={`Document type for ${row.file.name}`}
                    value={row.type}
                    disabled={running || row.state === 'done'}
                    onChange={(e) => update(row.id, { type: e.target.value, guessed: false })}
                  >
                    <option value="">Choose type…</option>
                    {DOCUMENT_TYPES.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                    <option value={OTHER}>Other…</option>
                  </select>
                  {row.type === OTHER && (
                    <input
                      id={`bulk-other-${row.id}`}
                      aria-label={`Name of the document ${row.file.name}`}
                      placeholder="e.g. Certificate of Origin"
                      maxLength={TYPE_MAX_LENGTH}
                      value={row.otherName}
                      disabled={running || row.state === 'done'}
                      onChange={(e) => update(row.id, { otherName: e.target.value })}
                    />
                  )}
                </div>
                <div className="bulk-state">
                  {note && <span className={`bulk-note bulk-note--${note.tone}`}>{note.text}</span>}
                  {row.state !== 'done' && row.state !== 'sending' && (
                    <button
                      type="button"
                      className="bulk-remove"
                      aria-label={`Take ${row.file.name} off the list`}
                      onClick={() => setRows((current) => current.filter((r) => r.id !== row.id))}
                      disabled={running}
                    >
                      &times;
                    </button>
                  )}
                </div>
              </li>
            )
          })}
        </ul>
      )}

      {finished && (
        <p className={finished.failed ? 'error' : 'banner'} role="status">
          {finished.failed === 0
            ? `All ${finished.done} uploaded to ${shipment?.shipment_no}. The customer can download them now.`
            : `${finished.done} uploaded, ${finished.failed} not. The ones that did not go are still in the list with the reason; fix them and press Upload all again.`}
        </p>
      )}

      <div className="form-actions">
        <button type="button" className="button" onClick={uploadAll} disabled={!ready}>
          {running
            ? 'Uploading…'
            : queued.length > 0
              ? `Upload all (${queued.length})`
              : 'Upload all'}
        </button>
        {rows.length > 0 && (
          <button
            type="button"
            className="button button--ghost"
            onClick={() => {
              setRows([])
              setFinished(null)
            }}
            disabled={running}
          >
            Clear the list
          </button>
        )}
        {!shipment && queued.length > 0 && (
          <span className="bulk-hint">Choose the shipment first.</span>
        )}
      </div>
    </div>
  )
}
