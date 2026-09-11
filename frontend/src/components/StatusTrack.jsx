import { CANCELLED, SEQUENCE, statusStep } from './StatusPill'

// Where a shipment has got to, as a track rather than a word.
//
// A customer reading "In transit" has to know what comes before and after it
// to know whether that is good news. A track answers that without them
// asking anybody.
export default function StatusTrack({ status }) {
  if (!status) return null

  if (status.trim().toLowerCase() === CANCELLED.toLowerCase()) {
    return (
      <p className="track-cancelled" role="status">
        This shipment was cancelled.
      </p>
    )
  }

  const at = statusStep(status)
  // A status the portal does not recognise: show nothing rather than draw a
  // track with no position marked on it.
  if (at === null) return null

  return (
    <ol className="steptrack" aria-label={`Step ${at} of ${SEQUENCE.length}: ${status}`}>
      {SEQUENCE.map((name, index) => {
        const step = index + 1
        const state = step < at ? 'done' : step === at ? 'now' : 'todo'
        return (
          <li key={name} className={`step step--${state}`}>
            <span className="step-dot" aria-hidden="true" />
            <span className="step-name">{name}</span>
          </li>
        )
      })}
    </ol>
  )
}
