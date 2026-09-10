import { useState } from 'react'
import axios from 'axios'
import { ChoiceField, TextField } from '../../components/Field'
import { ALL_STATUSES, statusStep } from '../../components/StatusPill'
import { blankToNull, describeError } from '../../lib/format'

// Same form for adding a part-shipment and editing one. `shipment` being
// null means "new", and then `orderId` says which order it belongs to.
// The server refuses a move back down the sequence unless the request says
// it is deliberate. Rather than let it refuse and then explain, ask first:
// the person knows whether they are correcting a mistake, and the server
// cannot.
function confirmBackwards(current, next, what) {
  const here = statusStep(current)
  const there = statusStep(next)
  if (here === null || there === null || there >= here) return true
  return window.confirm(
    `This moves ${what} back from ${current} to ${next}.

` +
      'Going backwards is usually a misclick. Is this a correction?',
  )
}

export default function ShipmentForm({ orderId, shipment, onSaved, onCancel }) {
  const [form, setForm] = useState(() => ({
    shipment_no: shipment?.shipment_no ?? '',
    dispatched_qty: shipment?.dispatched_qty ?? '',
    unit: shipment?.unit ?? 'MT',
    status: shipment?.status ?? '',
    vessel_name: shipment?.vessel_name ?? '',
    imo_number: shipment?.imo_number ?? '',
    container_no: shipment?.container_no ?? '',
    bl_number: shipment?.bl_number ?? '',
    etd: shipment?.etd ?? '',
    eta: shipment?.eta ?? '',
  }))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  function set(field) {
    return (value) => setForm((f) => ({ ...f, [field]: value }))
  }

  async function submit(event) {
    event.preventDefault()

    if (!String(form.shipment_no).trim()) {
      setError('A shipment number is required.')
      return
    }
    if (String(form.dispatched_qty).trim() === '') {
      setError('A dispatched quantity is required.')
      return
    }

    const backwards =
      statusStep(blankToNull(form.status)) !== null &&
      statusStep(shipment?.status) !== null &&
      statusStep(blankToNull(form.status)) < statusStep(shipment?.status)

    if (backwards && !confirmBackwards(shipment?.status, form.status, 'this shipment')) return

    setBusy(true)
    setError(null)

    const payload = {
      shipment_no: String(form.shipment_no).trim(),
      dispatched_qty: String(form.dispatched_qty).trim(),
      unit: blankToNull(form.unit),
      status: blankToNull(form.status),
      allow_backwards: backwards,
      vessel_name: blankToNull(form.vessel_name),
      imo_number: blankToNull(form.imo_number),
      container_no: blankToNull(form.container_no),
      bl_number: blankToNull(form.bl_number),
      etd: blankToNull(form.etd),
      eta: blankToNull(form.eta),
    }

    try {
      if (shipment) await axios.put(`/api/staff/shipments/${shipment.id}`, payload)
      else await axios.post(`/api/staff/orders/${orderId}/shipments`, payload)
      await onSaved()
    } catch (err) {
      setError(describeError(err, 'Could not save that shipment. Please try again.'))
      setBusy(false)
    }
  }

  return (
    <form className="card--form card--form-inner" onSubmit={submit} noValidate>
      <h4 className="form-title">
        {shipment ? `Edit ${shipment.shipment_no}` : 'New shipment'}
      </h4>

      <div className="formgrid">
        <TextField
          label="Shipment number"
          value={form.shipment_no}
          onChange={set('shipment_no')}
        />

        <TextField
          label="Dispatched quantity"
          value={form.dispatched_qty}
          onChange={set('dispatched_qty')}
          type="number"
          step="0.001"
          min="0"
        />

        <TextField label="Unit" value={form.unit} onChange={set('unit')} />

        <ChoiceField
          label="Status"
          value={form.status}
          options={ALL_STATUSES}
          onChange={set('status')}
        />

        <TextField
          label="Vessel name"
          value={form.vessel_name}
          onChange={set('vessel_name')}
        />

        <TextField
          label="IMO number"
          value={form.imo_number}
          onChange={set('imo_number')}
          inputMode="numeric"
          maxLength={7}
          hint="Seven digits. The last one is a check digit, so a typo is refused."
        />

        <TextField
          label="Container number"
          value={form.container_no}
          onChange={set('container_no')}
          maxLength={20}
          placeholder="MSCU1234566"
          hint="Four letters then seven digits. The last one is a check digit, so a typo is refused."
        />

        <TextField
          label="B/L number"
          value={form.bl_number}
          onChange={set('bl_number')}
          maxLength={60}
          hint="As the carrier issued it. No format is enforced."
        />

        <TextField label="ETD" value={form.etd} onChange={set('etd')} type="date" />
        <TextField label="ETA" value={form.eta} onChange={set('eta')} type="date" />
      </div>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      <div className="form-actions">
        <button type="submit" className="button" disabled={busy}>
          {busy ? 'Saving…' : shipment ? 'Save changes' : 'Add shipment'}
        </button>
        <button
          type="button"
          className="button button--ghost"
          onClick={onCancel}
          disabled={busy}
        >
          Cancel
        </button>
      </div>
    </form>
  )
}
