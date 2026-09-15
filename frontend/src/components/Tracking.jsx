import { useState } from 'react'

// The tracking pieces both halves of the portal show. Staff on the phone to
// a customer need to be looking at the same map and the same numbers, so
// there is one component and not two that drift.

// One number, big enough to read out and one tap to copy. Copying can fail
// -- an old browser, a page served over plain http, a permission refused --
// so the value is always on screen as text as well. The button is the
// convenience; the text is the guarantee.
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
        <button type="button" className="copynum-button" onClick={copy}>
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

// The vessel's live position, on the page rather than behind a link. An
// iframe, not the provider's script: a script would run in the portal's own
// page, where the sign-in token lives, and a frame cannot reach it.
export function VesselMap({ shipment }) {
  if (!shipment.vessel_map_url) return null

  return (
    <div className="vesselmap">
      <iframe
        className="vesselmap-frame"
        src={shipment.vessel_map_url}
        title={`Live position of ${shipment.vessel_name || 'the vessel'}`}
        loading="lazy"
      />
      <small className="vesselmap-caption">
        Live position of the vessel — may pause when the ship is out of range.
        {shipment.vessel_map_provider ? ` Map by ${shipment.vessel_map_provider}.` : ''}
      </small>
    </div>
  )
}

// The two buttons, and the numbers a carrier's search page will ask for.
export function TrackActions({ shipment }) {
  const needsNumbers =
    shipment.container_tracking_url && !shipment.container_tracking_prefilled

  return (
    <>
      {/* The box first, the ship second. "Where is my container" is the
          question a buyer actually asks; where the vessel happens to be is
          interesting, but it cannot tell them the box is aboard. */}
      {shipment.container_tracking_url && (
        <p className="track-line">
          <a
            className="track track--button track--primary"
            href={shipment.container_tracking_url}
            target="_blank"
            rel="noopener noreferrer"
          >
            Track container
          </a>
          <span className="track-by">
            {shipment.container_tracking_prefilled
              ? `Opens ${shipment.container_tracking_carrier} in a new tab`
              : `Opens the ${shipment.container_tracking_carrier} search page in a new tab — paste one of these in`}
          </span>
        </p>
      )}

      {/* The carrier's page opens empty, so the numbers it will ask for are
          put right next to the button rather than left to be hunted for
          further up the screen. */}
      {needsNumbers && (
        <div className="copynums">
          {shipment.bl_number && (
            <CopyNumber label="Bill of Lading number" value={shipment.bl_number} />
          )}
          {shipment.container_no && (
            <CopyNumber label="Container number" value={shipment.container_no} />
          )}
        </div>
      )}

      {shipment.tracking_url && (
        <p className="track-line">
          <a
            className="track track--button"
            href={shipment.tracking_url}
            target="_blank"
            rel="noopener noreferrer"
          >
            See where the vessel is now
          </a>
          <span className="track-by">
            Opens {shipment.tracking_provider} in a new tab
          </span>
        </p>
      )}
    </>
  )
}
