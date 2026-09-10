import { useEffect, useState } from 'react'
import axios from 'axios'
import { TextField } from '../../components/Field'
import { describeError } from '../../lib/format'

// A temporary password, shown once and never again. It is deliberately
// awkward to lose: it stays on screen until dismissed, and says plainly that
// closing it is the end of it.
function TemporaryPassword({ result, onDone }) {
  const [copied, setCopied] = useState(false)

  async function copy() {
    try {
      await navigator.clipboard.writeText(result.temporary_password)
      setCopied(true)
    } catch {
      // Clipboard access can be refused; the password is on screen anyway.
      setCopied(false)
    }
  }

  return (
    <div className="card card--password" role="alert">
      <h3 className="form-title">Temporary password for {result.email}</h3>
      <p className="password-value">{result.temporary_password}</p>
      <p className="lead">
        <strong>This is the only time it can be read.</strong> It is stored as
        a hash, so nobody — not even the server — can look it up again. If it
        is lost, use Reset password and send a new one.
      </p>
      <p className="lead">
        Send it the way you would send anything else confidential, and not in
        the same message as the portal address. {result.email} will have to
        choose their own password before the portal shows them a single order.
      </p>
      <div className="form-actions">
        <button type="button" className="button" onClick={onDone}>
          I have copied it — close
        </button>
        <button type="button" className="button button--ghost" onClick={copy}>
          {copied ? 'Copied' : 'Copy to clipboard'}
        </button>
      </div>
    </div>
  )
}

function CustomerForm({ customer, onSaved, onCancel }) {
  const [form, setForm] = useState(() => ({
    code: customer?.code ?? '',
    name: customer?.name ?? '',
    country: customer?.country ?? '',
  }))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  function set(field) {
    return (value) => setForm((f) => ({ ...f, [field]: value }))
  }

  async function submit(event) {
    event.preventDefault()
    if (!form.name.trim()) {
      setError('A customer name is required.')
      return
    }
    if (!customer && !form.code.trim()) {
      setError('A customer code is required.')
      return
    }

    setBusy(true)
    setError(null)
    const body = { name: form.name.trim(), country: form.country.trim() || null }

    try {
      if (customer) await axios.put(`/api/staff/customers/${customer.id}`, body)
      else await axios.post('/api/staff/customers', { ...body, code: form.code.trim() })
      await onSaved()
    } catch (err) {
      setError(describeError(err, 'Could not save that customer.'))
      setBusy(false)
    }
  }

  return (
    <form className="card card--form" onSubmit={submit} noValidate>
      <h3 className="form-title">{customer ? 'Edit customer' : 'New customer'}</h3>

      <div className="formgrid">
        {customer ? (
          <TextField
            label="Customer code"
            value={form.code}
            onChange={() => {}}
            disabled
            hint="Cannot be changed: the CSV importer matches on it."
          />
        ) : (
          <TextField
            label="Customer code"
            value={form.code}
            onChange={set('code')}
            placeholder="HANSA"
            hint="Must match what SAP/PMS exports. Cannot be changed later."
          />
        )}

        <TextField
          label="Company name"
          value={form.name}
          onChange={set('name')}
          placeholder="Hansa Stahl GmbH"
        />

        <TextField
          label="Country"
          value={form.country}
          onChange={set('country')}
          placeholder="Germany"
        />
      </div>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      <div className="form-actions">
        <button type="submit" className="button" disabled={busy}>
          {busy ? 'Saving…' : customer ? 'Save changes' : 'Add customer'}
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

function LoginForm({ customer, onCreated, onCancel }) {
  const [email, setEmail] = useState('')
  const [fullName, setFullName] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function submit(event) {
    event.preventDefault()
    if (!email.trim()) {
      setError('An email address is required.')
      return
    }

    setBusy(true)
    setError(null)
    try {
      const res = await axios.post(`/api/staff/customers/${customer.id}/logins`, {
        email: email.trim(),
        full_name: fullName.trim() || null,
      })
      await onCreated(res.data)
    } catch (err) {
      setError(describeError(err, 'Could not create that login.'))
      setBusy(false)
    }
  }

  return (
    <form className="card--form card--form-inner" onSubmit={submit} noValidate>
      <h4 className="form-title">New login for {customer.name}</h4>

      <div className="formgrid">
        <TextField
          label="Email address"
          value={email}
          onChange={setEmail}
          type="email"
          placeholder="einkauf@hansa-stahl.de"
          hint="Nothing checks that this address is real. A typo makes a login nobody can use."
        />
        <TextField
          label="Their name"
          value={fullName}
          onChange={setFullName}
          placeholder="Petra Baumann"
        />
      </div>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      <div className="form-actions">
        <button type="submit" className="button" disabled={busy}>
          {busy ? 'Creating…' : 'Create login'}
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

function LoginRow({ login, busy, onReset, onSetActive }) {
  return (
    <div className="docrow">
      <span
        className={login.is_active ? 'dot dot--on' : 'dot'}
        aria-hidden="true"
      />
      <div className="docrow-main">
        <span className="docrow-type">
          {login.email}
          {login.full_name ? ` · ${login.full_name}` : ''}
        </span>
        <span className="docrow-file">
          {!login.is_active
            ? 'Deactivated — cannot sign in'
            : login.must_change_password
              ? 'Still on the temporary password; sees no orders until it is changed'
              : 'Active'}
        </span>
      </div>
      <div className="docrow-actions">
        <button
          type="button"
          className="minibutton"
          onClick={onReset}
          disabled={busy}
        >
          Reset password
        </button>
        <button
          type="button"
          className="minibutton minibutton--quiet"
          onClick={onSetActive}
          disabled={busy}
        >
          {login.is_active ? 'Deactivate' : 'Reactivate'}
        </button>
      </div>
    </div>
  )
}

// Customers & logins. Everything here used to need somebody with access to
// the server running scripts/manage_users.py.
export default function StaffAccountsScreen() {
  const [state, setState] = useState('loading')
  const [data, setData] = useState({ customers: [], staff: [] })
  // null, 'new', or the customer being edited.
  const [customerForm, setCustomerForm] = useState(null)
  // The customer a login is being created for, or null.
  const [loginFor, setLoginFor] = useState(null)
  // A one-time password waiting to be read.
  const [password, setPassword] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function load() {
    try {
      const res = await axios.get('/api/staff/accounts')
      setData(res.data)
      setState('ready')
    } catch (err) {
      setState(err.response?.status === 401 ? 'unauthorised' : 'error')
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function afterSave() {
    setCustomerForm(null)
    setError(null)
    await load()
  }

  async function resetPassword(login) {
    if (
      !window.confirm(
        `Give ${login.email} a new temporary password?\n\n` +
          'Their current password stops working at once, and every session ' +
          'they have open is signed out.',
      )
    )
      return

    setBusy(true)
    setError(null)
    try {
      const res = await axios.post(`/api/staff/logins/${login.id}/reset-password`)
      setPassword(res.data)
      await load()
    } catch (err) {
      setError(describeError(err, 'Could not reset that password.'))
    } finally {
      setBusy(false)
    }
  }

  async function setActive(login) {
    const next = !login.is_active
    const question = next
      ? `Let ${login.email} sign in again?`
      : `Lock ${login.email} out?\n\nThis takes effect immediately, including ` +
        'for a session they already have open.'
    if (!window.confirm(question)) return

    setBusy(true)
    setError(null)
    try {
      await axios.post(`/api/staff/logins/${login.id}/active`, { active: next })
      await load()
    } catch (err) {
      setError(describeError(err, 'Could not change that account.'))
    } finally {
      setBusy(false)
    }
  }

  if (state === 'loading') {
    return (
      <div className="card">
        <p className="message">Loading customers…</p>
      </div>
    )
  }

  if (state !== 'ready') {
    return (
      <div className="card">
        <p className="message message--error" role="alert">
          {state === 'unauthorised'
            ? 'Your session has expired. Please sign in again.'
            : "Couldn't load the customers. Please try again."}
        </p>
      </div>
    )
  }

  return (
    <>
      {password && (
        <TemporaryPassword result={password} onDone={() => setPassword(null)} />
      )}

      <div className="card card--summary">
        <p className="summary">
          {data.customers.length} customer(s), {data.staff.length} staff login(s).
        </p>
        <button
          type="button"
          className="button"
          onClick={() => setCustomerForm('new')}
          disabled={customerForm === 'new'}
        >
          New customer
        </button>
      </div>

      {error && (
        <div className="card">
          <p className="message message--error" role="alert">
            {error}
          </p>
        </div>
      )}

      {customerForm === 'new' && (
        <CustomerForm onSaved={afterSave} onCancel={() => setCustomerForm(null)} />
      )}

      {data.customers.map((customer) =>
        customerForm?.id === customer.id ? (
          <CustomerForm
            key={customer.id}
            customer={customer}
            onSaved={afterSave}
            onCancel={() => setCustomerForm(null)}
          />
        ) : (
          <div className="card" key={customer.id}>
            <div className="shipment-head">
              <div>
                <h3 className="shipment-no">
                  {customer.name} <em className="mono">({customer.code})</em>
                </h3>
                <p className="shipment-sub">
                  {customer.country || 'Country not set'} · {customer.order_count}{' '}
                  order(s) · {customer.logins.length} login(s)
                </p>
              </div>
            </div>

            {customer.logins.length === 0 && (
              <p className="message message--quiet">
                Nobody can sign in for this customer yet.
              </p>
            )}

            {customer.logins.map((login) => (
              <LoginRow
                key={login.id}
                login={login}
                busy={busy}
                onReset={() => resetPassword(login)}
                onSetActive={() => setActive(login)}
              />
            ))}

            {loginFor?.id === customer.id && (
              <LoginForm
                customer={customer}
                onCreated={async (result) => {
                  setLoginFor(null)
                  setPassword(result)
                  await load()
                }}
                onCancel={() => setLoginFor(null)}
              />
            )}

            <div className="card-actions">
              <button
                type="button"
                className="minibutton"
                onClick={() => setLoginFor(customer)}
                disabled={busy || loginFor?.id === customer.id}
              >
                Add a login
              </button>
              <button
                type="button"
                className="minibutton"
                onClick={() => setCustomerForm(customer)}
                disabled={busy}
              >
                Edit customer
              </button>
            </div>
          </div>
        ),
      )}

      <div className="card">
        <div className="shipment-head">
          <div>
            <h3 className="shipment-no">Alok Ingots staff</h3>
            <p className="shipment-sub">
              These accounts see this admin console instead of a customer
              portal. A staff login can only be created on the server, with{' '}
              <code>scripts/manage_users.py --add-staff</code> — on purpose,
              because staff is the flag that unlocks every write in the portal.
            </p>
          </div>
        </div>

        {data.staff.map((login) => (
          <LoginRow
            key={login.id}
            login={login}
            busy={busy}
            onReset={() => resetPassword(login)}
            onSetActive={() => setActive(login)}
          />
        ))}
      </div>
    </>
  )
}
