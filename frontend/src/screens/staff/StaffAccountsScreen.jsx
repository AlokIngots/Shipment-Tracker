import { useEffect, useState } from 'react'
import axios from 'axios'
import StartHere from '../../components/StartHere'
import { Field, TextField } from '../../components/Field'
import { describeError, plural } from '../../lib/format'
import { PASSWORD_RULE, passwordShortfall, suggestPassword } from '../../lib/passwordRule'

// Said once a login has been made. The server also makes a random temporary
// password, as it always did; it is not shown, because Set password is the
// simpler thing to hand over -- a password staff chose is not one the
// customer is then made to replace.
function LoginCreated({ result, onDone }) {
  return (
    <div className="card card--password" role="status">
      <h3 className="form-title">Login created for {result.email}</h3>
      <p className="lead">
        They can sign in now with an email link: tell them to open{' '}
        <strong>{window.location.origin}</strong>, type {result.email} and
        press <strong>Sign in with email link</strong>.
      </p>
      <p className="lead">
        To let them in without email, press <strong>Set password</strong> next
        to their login below and share the password with them directly.
      </p>
      <div className="form-actions">
        <button type="button" className="button" onClick={onDone}>
          Close
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
    if (!customer && !form.code.trim()) {
      setError('Enter a short customer code, such as HANSA.')
      return
    }
    if (!form.name.trim()) {
      setError('Enter the company name.')
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
      <h3 className="form-title">{customer ? 'Edit customer' : 'Add a customer'}</h3>

      <div className="formgrid">
        {customer ? (
          <TextField
            label="Customer code"
            value={form.code}
            onChange={() => {}}
            disabled
            hint="Cannot be changed, because imported orders are matched to it."
          />
        ) : (
          <TextField
            label="Customer code"
            value={form.code}
            onChange={set('code')}
            placeholder="HANSA"
            autoFocus
            hint="A short code for the company. Use the same one as in SAP/PMS. It cannot be changed later."
          />
        )}

        <TextField
          label="Company name"
          value={form.name}
          onChange={set('name')}
          placeholder="Hansa Stahl GmbH"
          autoFocus={Boolean(customer)}
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

// Asked first when the Add customer login quick action brought us here and
// there is more than one customer it could be for.
function LoginPicker({ customers, onPick, onCancel }) {
  const [chosen, setChosen] = useState(String(customers[0]?.id ?? ''))

  return (
    <div className="card card--form">
      <h3 className="form-title">Add a customer login</h3>
      <div className="formgrid">
        <Field label="Which customer is the login for?">
          <select autoFocus value={chosen} onChange={(e) => setChosen(e.target.value)}>
            {customers.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} ({c.code})
              </option>
            ))}
          </select>
        </Field>
      </div>
      <div className="form-actions">
        <button
          type="button"
          className="button"
          onClick={() => onPick(customers.find((c) => String(c.id) === chosen))}
        >
          Continue
        </button>
        <button type="button" className="button button--ghost" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </div>
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
      setError('Enter their email address.')
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
          label="Their email address"
          value={email}
          onChange={setEmail}
          type="email"
          placeholder="einkauf@hansa-stahl.de"
          autoFocus
          hint="Check the spelling. The portal cannot tell if an address is wrong."
        />
        <TextField
          label="Their name"
          value={fullName}
          onChange={setFullName}
          placeholder="Petra Baumann"
          hint="Optional. Used to greet them."
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

// Staff choose a password for somebody and hand it over themselves: the way
// in that needs no email. Shown in plain text on purpose -- the point is to
// read it out or copy it -- and never sent back by the server.
function SetPasswordForm({ login, onSaved, onCancel }) {
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function submit(event) {
    event.preventDefault()
    if (passwordShortfall(password)) {
      setError(`${PASSWORD_RULE}, please — or press Suggest one.`)
      return
    }
    setBusy(true)
    setError(null)
    try {
      await axios.post(`/api/staff/logins/${login.id}/set-password`, { password })
      await onSaved({ email: login.email, password })
    } catch (err) {
      setError(describeError(err, 'Could not set that password.'))
      setBusy(false)
    }
  }

  return (
    <form className="card--form card--form-inner" onSubmit={submit} noValidate>
      <h4 className="form-title">Set a password for {login.email}</h4>
      <div className="formgrid">
        <TextField
          label="New password"
          value={password}
          onChange={setPassword}
          autoComplete="off"
          spellCheck={false}
          autoFocus
          hint={`${PASSWORD_RULE}. They can sign in with it straight away; anywhere they were already signed in is signed out.`}
        />
      </div>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <div className="form-actions">
        <button type="submit" className="button" disabled={busy}>
          {busy ? 'Saving…' : 'Set password'}
        </button>
        <button
          type="button"
          className="button button--outline"
          onClick={() => setPassword(suggestPassword())}
          disabled={busy}
        >
          Suggest one
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

// Said once, straight after Set password. The password is only here because
// staff typed it a moment ago; the server never sends it back.
function PasswordSet({ result, onDone }) {
  return (
    <div className="card card--password" role="status">
      <h3 className="form-title">Password set for {result.email}</h3>
      <p className="lead">
        Share it with them directly — by phone or WhatsApp, not in the same
        email as the portal address:
      </p>
      <p className="lead">
        <strong className="mono">{result.password}</strong>
      </p>
      <p className="lead">
        They open <strong>{window.location.origin}</strong>, type{' '}
        {result.email} and this password, and press <strong>Sign in</strong>.
        They stay signed in on that device, even after closing the browser,
        until they press Sign out.
      </p>
      <div className="form-actions">
        <button type="button" className="button" onClick={onDone}>
          Done
        </button>
      </div>
    </div>
  )
}

function LoginRow({ login, busy, onSetActive, onSetPassword }) {
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
            ? 'Disabled — cannot sign in'
            : login.must_change_password
              ? 'Signs in with an email link · no password set yet'
              : 'Signs in with a password or an email link'}
        </span>
      </div>
      <div className="docrow-actions">
        {onSetPassword && (
          <button
            type="button"
            className="minibutton"
            onClick={onSetPassword}
            disabled={busy}
          >
            Set password
          </button>
        )}
        <button
          type="button"
          className="minibutton minibutton--quiet"
          onClick={onSetActive}
          disabled={busy}
        >
          {login.is_active ? 'Disable login' : 'Enable login'}
        </button>
      </div>
    </div>
  )
}

// Customers & logins: add a customer, give somebody there a login, set their
// password, disable a login. The server decides every one of these in
// app/services/accounts.py; this screen only asks.
export default function StaffAccountsScreen({ startWith, onGo }) {
  const [state, setState] = useState('loading')
  const [data, setData] = useState({ customers: [], staff: [] })
  // null, 'new', or the customer being edited.
  const [customerForm, setCustomerForm] = useState(
    startWith?.action === 'new-customer' ? 'new' : null,
  )
  // The customer a login is being created for, or null.
  const [loginFor, setLoginFor] = useState(null)
  // Asking "which customer?" before a login form can open.
  const [picking, setPicking] = useState(startWith?.action === 'new-login')
  // The login just created, until the note about it is closed.
  const [created, setCreated] = useState(null)
  // The login whose password is being set, and the note once it is.
  const [passwordFor, setPasswordFor] = useState(null)
  const [passwordSet, setPasswordSet] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function load() {
    try {
      const res = await axios.get('/api/staff/accounts')
      setData(res.data)
      setState('ready')
      return res.data
    } catch (err) {
      setState(err.response?.status === 401 ? 'unauthorised' : 'error')
      return null
    }
  }

  useEffect(() => {
    load().then((loaded) => {
      // Only one customer: nothing to choose, so go straight to its form.
      if (loaded && startWith?.action === 'new-login' && loaded.customers.length === 1) {
        setPicking(false)
        setLoginFor(loaded.customers[0])
      }
    })
  }, [])

  async function afterSave() {
    setCustomerForm(null)
    setError(null)
    await load()
  }

  async function setActive(login) {
    const next = !login.is_active
    const question = next
      ? `Let ${login.email} sign in again?`
      : `Disable the login for ${login.email}?\n\nThey are signed out at once and ` +
        'cannot sign in until you enable it again. Nothing is deleted.'
    if (!window.confirm(question)) return

    setBusy(true)
    setError(null)
    try {
      await axios.post(`/api/staff/logins/${login.id}/active`, { active: next })
      await load()
    } catch (err) {
      setError(describeError(err, 'Could not change that login.'))
    } finally {
      setBusy(false)
    }
  }

  // One row, with the Set password form under it while that login is chosen.
  function loginRow(login) {
    return (
      <div key={login.id}>
        <LoginRow
          login={login}
          busy={busy}
          onSetActive={() => setActive(login)}
          onSetPassword={
            passwordFor === login.id ? null : () => setPasswordFor(login.id)
          }
        />
        {passwordFor === login.id && (
          <SetPasswordForm
            login={login}
            onSaved={async (result) => {
              setPasswordFor(null)
              setPasswordSet(result)
              window.scrollTo(0, 0)
              await load()
            }}
            onCancel={() => setPasswordFor(null)}
          />
        )}
      </div>
    )
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
            ? 'You have been signed out. Please sign in again.'
            : "Couldn't load the customers. Please refresh the page to try again."}
        </p>
      </div>
    )
  }

  const loginCount = data.customers.reduce((total, c) => total + c.logins.length, 0)

  return (
    <>
      {created && <LoginCreated result={created} onDone={() => setCreated(null)} />}
      {passwordSet && (
        <PasswordSet result={passwordSet} onDone={() => setPasswordSet(null)} />
      )}

      {(data.customers.length === 0 || loginCount === 0) && <StartHere onGo={onGo} />}

      <div className="card card--summary">
        <p className="summary">
          {plural(data.customers.length, 'customer')} ·{' '}
          {plural(loginCount, 'customer login')} · {plural(data.staff.length, 'team login')}
        </p>
        <button
          type="button"
          className="button"
          onClick={() => setCustomerForm('new')}
          disabled={customerForm === 'new'}
        >
          Add customer
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

      {picking && data.customers.length > 1 && (
        <LoginPicker
          customers={data.customers}
          onPick={(customer) => {
            setPicking(false)
            setLoginFor(customer)
          }}
          onCancel={() => setPicking(false)}
        />
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
                  {customer.country || 'Country not set'} ·{' '}
                  {plural(customer.order_count, 'order')} ·{' '}
                  {plural(customer.logins.length, 'login')}
                </p>
              </div>
            </div>

            {customer.logins.length === 0 && loginFor?.id !== customer.id && (
              <p className="message message--quiet">
                No logins yet. Press Add a login so someone at {customer.name} can
                see their orders.
              </p>
            )}

            {customer.logins.map(loginRow)}

            {loginFor?.id === customer.id && (
              <LoginForm
                customer={customer}
                onCreated={async (result) => {
                  setLoginFor(null)
                  setCreated(result)
                  window.scrollTo(0, 0)
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
            <h3 className="shipment-no">Alok Ingots team</h3>
            <p className="shipment-sub">
              Team logins see this admin screen instead of the customer portal,
              and can change anything in it. For that reason a new team login is
              added by your IT administrator, not from this screen.
            </p>
          </div>
        </div>

        {data.staff.map(loginRow)}
      </div>
    </>
  )
}
