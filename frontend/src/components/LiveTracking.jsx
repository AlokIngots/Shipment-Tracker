import { fmtDate } from '../lib/format'

// Live container tracking, from what ShipsGo last told the portal.
//
// Everything here is drawn from the stored copy the server sends with the
// order. Opening this page never asks ShipsGo anything: it is fast, and a
// busy day of customers reading their orders costs nothing.
//
// The timeline follows the CONTAINER, not a ship. When the box comes off one
// vessel and goes onto another (transshipment), it says so and names both
// vessels -- the thing the old vessel map got wrong, because the first ship
// sails on to a voyage the cargo is not on.

// "15/09/2026 14:05", in the reader's own time, for the "last updated" line.
function fmtStamp(value) {
  if (!value) return null
  const when = new Date(value)
  if (Number.isNaN(when.getTime())) return null
  const pad = (n) => String(n).padStart(2, '0')
  return `${pad(when.getDate())}/${pad(when.getMonth() + 1)}/${when.getFullYear()} ${pad(
    when.getHours(),
  )}:${pad(when.getMinutes())}`
}

function Move({ move }) {
  const state = move.latest ? 'now' : move.actual ? 'done' : 'todo'
  const where = [move.location, move.country].filter(Boolean).join(', ')
  const ship = move.vessel
    ? `${move.vessel}${move.voyage ? ` · voyage ${move.voyage}` : ''}`
    : null

  return (
    <li className={`livemove livemove--${state}${move.transshipment ? ' livemove--ts' : ''}`}>
      <span className="livemove-dot" aria-hidden="true" />
      <div className="livemove-body">
        <div className="livemove-head">
          <span className="livemove-label">{move.label}</span>
          {move.transshipment && <span className="livetag">Transshipment</span>}
          {!move.actual && <span className="livetag livetag--quiet">Expected</span>}
        </div>
        <div className="livemove-meta">
          {where && <span>{where}</span>}
          {move.date && <span>{fmtDate(move.date)}</span>}
          {ship && <span>{ship}</span>}
        </div>
        {move.from_vessel && move.vessel && (
          <p className="livemove-note">
            The container moved from {move.from_vessel} to {move.vessel} here.
          </p>
        )}
      </div>
    </li>
  )
}

export default function LiveTracking({ tracking, staff = false }) {
  if (!tracking) return null

  const updating = tracking.state === 'updating'
  const unavailable = tracking.state === 'unavailable'
  const facts = [
    ['From', tracking.port_of_loading],
    ['To', tracking.port_of_discharge],
    ['Loaded on', tracking.loaded_on && fmtDate(tracking.loaded_on)],
    ['Expected arrival', tracking.eta && fmtDate(tracking.eta)],
    [
      'Transshipment',
      tracking.transshipments > 0 &&
        (tracking.transshipments === 1
          ? 'Yes, the container changes vessel once on the way'
          : `Yes, the container changes vessel ${tracking.transshipments} times`),
    ],
    [
      'Container',
      tracking.container_number &&
        `${tracking.container_number}${
          tracking.other_containers?.length
            ? ` (and ${tracking.other_containers.length} more on this B/L)`
            : ''
        }`,
    ],
  ].filter(([, value]) => value)

  const updated = fmtStamp(tracking.updated_at)

  return (
    <div className="livebox" aria-live="polite">
      <div className="livebox-head">
        <span className="docs-label livebox-title">Live tracking</span>
        {!updating && (
          <span className={unavailable ? 'livestatus livestatus--bad' : 'livestatus'}>
            {tracking.status_label}
          </span>
        )}
      </div>

      {updating && (
        <p className="livebox-updating" role="status">
          Tracking is updating… The route and dates will appear here as soon
          as the shipping line reports them.
        </p>
      )}

      {!updating && facts.length > 0 && (
        <dl className="facts facts--tight livebox-facts">
          {facts.map(([label, value]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      )}

      {!updating && tracking.movements.length > 0 && (
        <ol className="livemoves" aria-label="Container movements">
          {tracking.movements.map((move, index) => (
            <Move key={`${move.event}-${move.timestamp}-${index}`} move={move} />
          ))}
        </ol>
      )}

      {(updated || !updating) && (
        <p className="livebox-note">
          {updated ? `Last updated ${updated}. ` : ''}
          {staff
            ? 'Refreshed automatically a few times a day.'
            : 'Dates marked “Expected” are the shipping line’s estimate and can change.'}
        </p>
      )}
    </div>
  )
}
