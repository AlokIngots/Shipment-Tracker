import { useEffect, useState } from 'react'
import axios from 'axios'
import { DASH, describeError, fmtDate, plural } from '../../lib/format'

const PAGE_SIZE = 100

// When, in the reader's own time zone. The server stores UTC; nobody at a
// desk in Mumbai should have to add five and a half hours in their head.
function fmtWhen(iso) {
  const when = new Date(iso)
  if (Number.isNaN(when.getTime())) return iso
  const pad = (n) => String(n).padStart(2, '0')
  return (
    `${pad(when.getDate())}/${pad(when.getMonth() + 1)}/${when.getFullYear()} ` +
    `${pad(when.getHours())}:${pad(when.getMinutes())}`
  )
}

// A recorded value as a person reads it: dates the way the rest of the
// portal writes them, and "not set" as a dash rather than a blank.
function fmtValue(value) {
  if (value === null || value === undefined || value === '') return DASH
  return /^\d{4}-\d{2}-\d{2}$/.test(value) ? fmtDate(value) : value
}

// A change from the server has no signed-in person to name, so say where it
// came from instead.
function who(event) {
  if (event.actor_email) return event.actor_email
  return event.source === 'csv import'
    ? 'Imported from a data file'
    : 'Your IT administrator, on the server'
}

function matches(event, needle) {
  const words = [event.summary, who(event)]
  for (const change of event.changes ?? []) {
    words.push(change.field, change.before, change.after)
  }
  return words.some((word) => word && word.toLowerCase().includes(needle))
}

// Activity. Every change made in the admin console, by the command-line
// tools on the server, or by a CSV import — newest first, and read-only:
// there is no button on this page because there is no route behind one.
export default function StaffActivityScreen() {
  const [state, setState] = useState('loading')
  const [events, setEvents] = useState([])
  const [more, setMore] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [filter, setFilter] = useState('')

  async function fetchPage(beforeId) {
    const params = { limit: PAGE_SIZE }
    if (beforeId) params.before = beforeId
    const res = await axios.get('/api/staff/activity', { params })
    return res.data
  }

  async function load() {
    try {
      const page = await fetchPage()
      setEvents(page.events)
      setMore(page.more)
      setState('ready')
    } catch (err) {
      setState(err.response?.status === 401 ? 'unauthorised' : 'error')
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function loadOlder() {
    setBusy(true)
    setError(null)
    try {
      const page = await fetchPage(events[events.length - 1].id)
      setEvents((loaded) => [...loaded, ...page.events])
      setMore(page.more)
    } catch (err) {
      setError(describeError(err, "Couldn't load older changes."))
    } finally {
      setBusy(false)
    }
  }

  if (state === 'loading') {
    return (
      <div className="card">
        <p className="message">Loading activity…</p>
      </div>
    )
  }

  if (state !== 'ready') {
    return (
      <div className="card">
        <p className="message message--error" role="alert">
          {state === 'unauthorised'
            ? 'Your session has expired. Please sign in again.'
            : "Couldn't load the activity. Please try again."}
        </p>
      </div>
    )
  }

  const needle = filter.trim().toLowerCase()
  const visible = needle ? events.filter((event) => matches(event, needle)) : events

  return (
    <>
      <div className="card card--summary">
        <p className="summary">
          {needle
            ? `${visible.length} of the ${plural(events.length, 'change')} loaded match.`
            : more
              ? `Showing the latest ${plural(events.length, 'change')}.`
              : `${plural(events.length, 'change')} recorded so far.`}
        </p>
        <input
          type="search"
          className="activity-filter"
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
          placeholder="Filter: an order, a shipment, a person…"
          aria-label="Filter the changes"
        />
      </div>

      <div className="card">
        <p className="shipment-sub activity-note">
          Written at the moment each change is saved: who made it, and what
          each field was before and after. Nothing on this page can be edited
          or removed, by anybody.
          {needle && more && ' The filter only searches the changes loaded so far.'}
        </p>

        {visible.length === 0 && (
          <p className="message message--quiet">
            {events.length === 0
              ? 'Nothing has been changed yet.'
              : 'None of the changes loaded match that filter.'}
          </p>
        )}

        {visible.map((event) => (
          <div className="activity" key={event.id}>
            <div className="activity-head">
              <span className="activity-summary">{event.summary}</span>
              <span className="activity-when">{fmtWhen(event.happened_at)}</span>
            </div>
            <span className="activity-who">{who(event)}</span>
            {event.changes?.length > 0 && (
              <ul className="activity-changes">
                {event.changes.map((change, index) => (
                  <li key={index}>
                    <span className="activity-field">{change.field}</span>{' '}
                    {fmtValue(change.before)} → {fmtValue(change.after)}
                  </li>
                ))}
              </ul>
            )}
          </div>
        ))}

        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}

        {more && (
          <div className="card-actions">
            <button type="button" className="minibutton" onClick={loadOlder} disabled={busy}>
              {busy ? 'Loading…' : 'Load older changes'}
            </button>
          </div>
        )}
      </div>
    </>
  )
}
