import { useState } from 'react'
import axios from 'axios'
import { applyToken } from '../lib/session'

// Shown two ways: forced, when staff have just handed over a temporary
// password and nothing else may be seen until it is replaced; and by choice,
// from the orders screen. The server enforces the forced case regardless of
// what this screen does — it will not return an order to somebody who is
// still on a temporary password.
export default function ChangePasswordScreen({
  session,
  forced,
  onDone,
  onCancel,
  onSignOut,
}) {
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const longEnough = next.length >= 8

  async function handleSubmit(event) {
    event.preventDefault()
    setError(null)

    if (next !== confirm) {
      setError('The two new passwords do not match.')
      return
    }

    setBusy(true)
    try {
      const res = await axios.post('/api/change-password', {
        current_password: current,
        new_password: next,
      })
      // Changing the password signs out every token issued before it,
      // including the one that made this request. The server hands back a
      // replacement so this tab stays signed in and other places do not.
      if (res.data?.token) applyToken(res.data.token)
      onDone()
    } catch (err) {
      // The server is the authority on what makes a password acceptable, so
      // show what it said rather than guessing here.
      setError(
        err.response?.data?.detail ?? 'Could not reach the server. Please try again.',
      )
      setBusy(false)
    }
  }

  return (
    <div className="card card--login">
      <h2>{forced ? 'Choose your password' : 'Change your password'}</h2>

      {forced ? (
        <p className="lead">
          You are signed in with a temporary password given to you by Alok
          Ingots. Please choose your own before continuing.
        </p>
      ) : (
        <p className="lead">Signed in as {session.email}.</p>
      )}

      <form onSubmit={handleSubmit} noValidate>
        <label className="field">
          <span>{forced ? 'Temporary password' : 'Current password'}</span>
          <input
            type="password"
            value={current}
            autoComplete="current-password"
            onChange={(e) => setCurrent(e.target.value)}
          />
        </label>

        <label className="field">
          <span>New password</span>
          <input
            type="password"
            value={next}
            autoComplete="new-password"
            onChange={(e) => setNext(e.target.value)}
          />
        </label>

        <label className="field">
          <span>New password again</span>
          <input
            type="password"
            value={confirm}
            autoComplete="new-password"
            onChange={(e) => setConfirm(e.target.value)}
          />
        </label>

        {/* Say what is needed while it is being typed, rather than refusing
            it afterwards. The server still decides; this only stops the
            rule being a surprise. */}
        <p className={longEnough ? 'hint hint--met' : 'hint'}>
          {longEnough
            ? 'Long enough.'
            : `At least 8 characters — ${next.length} so far.`}{' '}
          Longer is better than complicated.
        </p>

        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}

        <button type="submit" className="button" disabled={busy}>
          {busy ? 'Saving…' : 'Save new password'}
        </button>

        {!forced && (
          <button
            type="button"
            className="button button--ghost button--block"
            onClick={onCancel}
            disabled={busy}
          >
            Cancel
          </button>
        )}
      </form>

      {forced && (
        <p className="demo-note">
          <button type="button" className="linkish" onClick={onSignOut}>
            Sign out instead
          </button>
        </p>
      )}
    </div>
  )
}
