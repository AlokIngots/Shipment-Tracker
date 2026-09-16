import { useState } from 'react'

// The tracking both halves of the portal show. Staff on the phone to a
// customer need the same numbers and the same link in front of them, so
// there is one component and not two that drift.
//
// There is no vessel map and no vessel link. Both were removed on
// 15 Sep 2026: export cargo is transshipped, so the named ship sails on to
// another voyage while the boxes wait at a hub, and a map of that hull shows
// a ship going somewhere the cargo is not. The carrier follows the box.

// One number, big enough to read down a phone line and one tap to copy.
// Copying can fail -- an old browser, a page served over plain http, a
// permission refused -- so the number is always on screen as selectable
// text too. The button is the convenience; the text is the guarantee.
function CopyNumber({ label, value }) {
  // 'idle' -> 'copied' | 'failed'
  const [state, setState] = useState('idle')

  async function copy() {
    try {
      if (!navigator.clipboard) throw new Error('no clipboard')
      await navigator.clipboard.writeText(value)
      setState('copied')
      setTimeout(() => setState('idle'), 2000)
    } catch {
      setState('failed')
    }
  }

  return (
    <div className="copynum">
      <span className="copynum-label">{label}</span>
      <span className="copynum-row">
        <code className="copynum-value">{value}</code>
        <button
          type="button"
          className="copynum-button"
          onClick={copy}
          aria-label={`Copy the ${label.toLowerCase()}`}
        >
          {state === 'copied' ? 'Copied' : state === 'failed' ? 'Select it' : 'Copy'}
        </button>
      </span>
      {state === 'failed' && (
        <small className="copynum-hint">
          This browser would not let us copy it for you — select the number
          above and copy it yourself.
        </small>
      )}
    </div>
  )
}

// The one tracking action: the carrier's own page, which knows about the
// transshipment because the carrier arranged it.
export function TrackActions({ shipment }) {
  if (!shipment.container_tracking_url) return null

  const carrier = shipment.container_tracking_carrier
  const numbers = [
    shipment.bl_number && ['Bill of Lading number', shipment.bl_number],
    shipment.container_no && ['Container number', shipment.container_no],
  ].filter(Boolean)

  return (
    <div className="trackbox">
      <a
        className="track track--button track--primary"
        href={shipment.container_tracking_url}
        target="_blank"
        rel="noopener noreferrer"
      >
        Track this container on {carrier}
      </a>
      <p className="trackbox-note">
        Opens the {carrier} website in a new tab.
        {shipment.container_tracking_prefilled
          ? ' Their page can be slow to load.'
          : ` Their page asks for a number — copy one of these into it. ${carrier}'s site can be slow, or busy at times.`}
      </p>

      {numbers.length > 0 && (
        <div className="copynums">
          {numbers.map(([label, value]) => (
            <CopyNumber key={label} label={label} value={value} />
          ))}
        </div>
      )}
    </div>
  )
}
