import { useEffect, useState } from 'react'
import axios from 'axios'
import { DASH, describeError, plural } from '../../lib/format'

const PAGE_SIZE = 100

// When, in the reader's own time zone. The server stores UTC; nobody at a
// desk in Mumbai should have to add five and a half hours in their head.
function fmtWhen(iso) {
  if (!iso) return DASH
  const when = new Date(iso)
  if (Number.isNaN(when.getTime())) return iso
  const pad = (n) => String(n).padStart(2, '0')
  return (
    `${pad(when.getDate())}/${pad(when.getMonth() + 1)}/${when.getFullYear()} ` +
    `${pad(when.getHours())}:${pad(when.getMinutes())}`
  )
}

// What happened to one message, in words rather than in the server's
// vocabulary. "suppressed" is accurate and means nothing to a reader.
const OUTCOMES = {
  sent: { label: 'Sent', className: 'pill pill--delivered' },
  suppressed: { label: 'Not sent', className: 'pill pill--neutral' },
  failed: { label: 'Failed', className: 'pill pill--cancelled' },
}

function outcomeOf(message) {
  return OUTCOMES[message.outcome] ?? { label: message.outcome, className: 'pill' }
}

// The counts from one run, read as a sentence. Nothing to report is worth
// saying plainly instead of "sent 0, suppressed 0, failed 0".
function describeRun(counts) {
  if (!counts) return null
  const parts = []
  if (counts.sent) parts.push(`sent ${plural(counts.sent, 'message')}`)
  if (counts.suppressed) parts.push(`held back ${counts.suppressed}`)
  if (counts.failed) parts.push(`${counts.failed} failed`)
  if (counts.skipped) parts.push('another sender was already running')
  return parts.length ? parts.join(', ') : 'nothing was waiting'
}

// Messages to customers: what the portal has told them, what it is about to
// tell them, and whether it is telling them by itself.
//
// The point of the screen is that "has the customer been told?" stops being
// answered with "did anybody remember to run the command?".
export default function StaffMessagesScreen() {
  const [state, setState] = useState('loading')
  const [sender, setSender] = useState(null)
  const [waiting, setWaiting] = useState([])
  const [messages, setMessages] = useState([])
  const [more, setMore] = useState(false)
  const [busy, setBusy] = useState(false)
  const [sending, setSending] = useState(false)
  const [note, setNote] = useState(null)
  const [error, setError] = useState(null)

  async function fetchPage(beforeId) {
    const params = { limit: PAGE_SIZE }
    if (beforeId) params.before = beforeId
    const res = await axios.get('/api/staff/messages', { params })
    return res.data
  }

  function show(page) {
    setSender(page.sender)
    setWaiting(page.waiting)
    setMessages(page.messages)
    setMore(page.more)
  }

  async function load() {
    try {
      show(await fetchPage())
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
      const page = await fetchPage(messages[messages.length - 1].id)
      setMessages((loaded) => [...loaded, ...page.messages])
      setMore(page.more)
    } catch (err) {
      setError(describeError(err, "Couldn't load older messages."))
    } finally {
      setBusy(false)
    }
  }

  async function sendNow() {
    setSending(true)
    setError(null)
    setNote(null)
    try {
      const res = await axios.post('/api/staff/messages/send')
      setNote(describeRun(res.data))
      // Reloaded rather than patched: the run has changed both lists, and a
      // half-updated screen is worse than a second's wait.
      show(await fetchPage())
    } catch (err) {
      setError(describeError(err, "Couldn't send just now. Please try again."))
    } finally {
      setSending(false)
    }
  }

  if (state === 'loading') {
    return (
      <div className="card">
        <p className="message">Loading messages…</p>
      </div>
    )
  }

  if (state !== 'ready') {
    return (
      <div className="card">
        <p className="message message--error" role="alert">
          {state === 'unauthorised'
            ? 'Your session has expired. Please sign in again.'
            : "Couldn't load the messages. Please try again."}
        </p>
        {state === 'error' && (
          <div className="card-actions">
            <button type="button" className="minibutton" onClick={load}>
              Try again
            </button>
          </div>
        )}
      </div>
    )
  }

  const automatic = sender.every_minutes > 0

  return (
    <>
      <div className="card card--summary">
        <p className="summary">
          {waiting.length === 0
            ? 'Every customer has been told about every shipment.'
            : `${plural(waiting.length, 'message')} waiting to go out.`}
        </p>
        <button type="button" className="button" onClick={sendNow} disabled={sending}>
          {sending ? 'Sending…' : 'Send now'}
        </button>
      </div>

      <div className="card">
        <p className="shipment-sub activity-note">
          {automatic
            ? `The portal sends these by itself, looking every ${plural(
                sender.every_minutes,
                'minute',
              )}. Send now does the same check straight away.`
            : 'Automatic sending is switched off on this server. Nothing goes out unless somebody presses Send now.'}
        </p>

        {!sender.sending_enabled && (
          <p className="message message--quiet">
            Email is switched off on this server, so messages are written down
            here but not delivered to anybody. They stay on the waiting list and
            go out the first time it is switched on — nothing is lost.
          </p>
        )}

        {sender.sending_enabled && sender.pilot_addresses.length > 0 && (
          <p className="message message--quiet">
            Pilot: only {sender.pilot_addresses.join(', ')} receives real email.
            Everybody else stays on the waiting list.
          </p>
        )}

        <ul className="sender-facts">
          <li>
            <span className="activity-field">Last looked</span>{' '}
            {sender.last_run_at
              ? `${fmtWhen(sender.last_run_at)} — ${describeRun(sender.last_counts)}`
              : 'not since the portal last restarted'}
          </li>
          <li>
            <span className="activity-field">A customer is told when a shipment becomes</span>{' '}
            {sender.notify_on.join(', ')}
          </li>
        </ul>

        {sender.last_error && (
          <p className="error" role="alert">
            The last automatic run did not finish: {sender.last_error}. It tries
            again on its own.
          </p>
        )}

        {note && <p className="message message--quiet">Send now: {note}.</p>}
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
      </div>

      {waiting.length > 0 && (
        <div className="card">
          <h3 className="shipment-no">Waiting to go out</h3>
          {waiting.map((row, index) => (
            <div className="msg" key={index}>
              <div className="activity-head">
                <span className="activity-summary">
                  {row.sales_order_no} · {row.shipment_no} — {row.event}
                </span>
                <span className="activity-when">
                  {row.would_send ? 'will be sent' : 'will be held back'}
                </span>
              </div>
              <span className="activity-who">
                {row.customer_name} · {row.to_email}
              </span>
            </div>
          ))}
        </div>
      )}

      <div className="card">
        <h3 className="shipment-no">Already handled</h3>

        {messages.length === 0 && (
          <p className="message message--quiet">
            Nothing has gone to a customer yet.
          </p>
        )}

        {messages.map((message) => {
          const outcome = outcomeOf(message)
          return (
            <div className="msg" key={message.id}>
              <div className="activity-head">
                <span className="activity-summary">
                  {message.sales_order_no} · {message.shipment_no} — {message.event}
                </span>
                <span className="activity-when">{fmtWhen(message.attempted_at)}</span>
              </div>
              <span className="activity-who">
                {message.customer_name} · {message.to_email}
              </span>
              <div className="msg-outcome">
                <span className={outcome.className}>{outcome.label}</span>
                {message.attempts > 1 && (
                  <span className="msg-detail">
                    after {plural(message.attempts, 'try', 'tries')}
                  </span>
                )}
                {message.detail && <span className="msg-detail">{message.detail}</span>}
              </div>
            </div>
          )
        })}

        {more && (
          <div className="card-actions">
            <button
              type="button"
              className="minibutton"
              onClick={loadOlder}
              disabled={busy}
            >
              {busy ? 'Loading…' : 'Load older messages'}
            </button>
          </div>
        )}
      </div>
    </>
  )
}
