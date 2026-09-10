import { useState } from 'react'
import axios from 'axios'
import { Field, SuggestField, TextField } from '../../components/Field'
import { ORDER_STATUSES } from '../../components/StatusPill'
import { blankToNull, describeError } from '../../lib/format'

// Creating and editing use the same form and the same shape of request; the
// only difference is where it is sent. `order` being null means "new".
export default function OrderForm({ customers, order, onSaved, onCancel }) {
  const [form, setForm] = useState(() => ({
    customer_id: order?.customer_id ?? customers[0]?.id ?? '',
    sales_order_no: order?.sales_order_no ?? '',
    customer_po: order?.customer_po ?? '',
    grade: order?.grade ?? '',
    description: order?.description ?? '',
    ordered_qty: order?.ordered_qty ?? '',
    unit: order?.unit ?? 'MT',
    status: order?.status ?? '',
  }))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  function set(field) {
    return (value) => setForm((f) => ({ ...f, [field]: value }))
  }

  async function submit(event) {
    event.preventDefault()

    // Two things are checked here only so the message is a sentence rather
    // than a validation error about a missing field. Everything else — the
    // sales order number being unique, the quantity not being negative — is
    // the server's to decide, and is not repeated here.
    if (!String(form.sales_order_no).trim()) {
      setError('A sales order number is required.')
      return
    }
    if (String(form.ordered_qty).trim() === '') {
      setError('An ordered quantity is required.')
      return
    }

    setBusy(true)
    setError(null)

    const payload = {
      customer_id: Number(form.customer_id),
      sales_order_no: String(form.sales_order_no).trim(),
      customer_po: blankToNull(form.customer_po),
      grade: blankToNull(form.grade),
      description: blankToNull(form.description),
      ordered_qty: String(form.ordered_qty).trim(),
      unit: blankToNull(form.unit),
      status: blankToNull(form.status),
    }

    try {
      if (order) await axios.put(`/api/staff/orders/${order.id}`, payload)
      else await axios.post('/api/staff/orders', payload)
      await onSaved()
    } catch (err) {
      setError(describeError(err, 'Could not save that order. Please try again.'))
      setBusy(false)
    }
  }

  return (
    <form className="card card--form" onSubmit={submit} noValidate>
      <h3 className="form-title">{order ? 'Edit order' : 'New order'}</h3>

      <div className="formgrid">
        <Field label="Customer">
          <select
            value={form.customer_id}
            onChange={(e) => set('customer_id')(e.target.value)}
          >
            {customers.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} ({c.code})
              </option>
            ))}
          </select>
        </Field>

        <TextField
          label="Sales order number"
          value={form.sales_order_no}
          onChange={set('sales_order_no')}
          placeholder="AIMPL/SO/EXP/163/2025-26"
        />

        <TextField
          label="Customer PO"
          value={form.customer_po}
          onChange={set('customer_po')}
        />

        <TextField
          label="Grade"
          value={form.grade}
          onChange={set('grade')}
          placeholder="431 / 1.4057"
        />

        <TextField
          label="Ordered quantity"
          value={form.ordered_qty}
          onChange={set('ordered_qty')}
          type="number"
          step="0.001"
          min="0"
        />

        <TextField label="Unit" value={form.unit} onChange={set('unit')} />

        <SuggestField
          label="Status"
          id="order-statuses"
          value={form.status}
          options={ORDER_STATUSES}
          onChange={set('status')}
        />

        <Field label="Description" wide>
          <textarea
            rows={2}
            value={form.description}
            onChange={(e) => set('description')(e.target.value)}
          />
        </Field>
      </div>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      <div className="form-actions">
        <button type="submit" className="button" disabled={busy}>
          {busy ? 'Saving…' : order ? 'Save changes' : 'Create order'}
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
