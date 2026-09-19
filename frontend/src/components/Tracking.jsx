import { useState } from 'react'

// What is left of the old tracking links: a Copy button.
//
// There is no vessel map and no vessel link (removed 15 Sep 2026: export
// cargo is transshipped, so a map of the first hull shows a ship going
// somewhere the cargo is not). The customer stopped being sent to the
// carrier's website on 16 Sep 2026, and staff on 17 Sep 2026, when live
// tracking inside the portal (LiveTracking.jsx) made the
// "Track this container on <carrier>" box redundant. Nothing in the portal
// sends anybody off-site to follow a container any more.
//
// The B/L and container numbers stay on screen, each with this button, so
// they are still one tap away for whoever needs to quote them.

// Just the button. The number it copies is already on screen beside it,
// which is what makes this safe to offer: copying can fail -- an old
// browser, a page served over plain http, a permission refused -- and then
// the number is still there to select by hand.
export function CopyButton({ label, value }) {
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
    <button
      type="button"
      className="copynum-button copynum-button--inline"
      onClick={copy}
      aria-label={`Copy the ${label.toLowerCase()}`}
      title={state === 'failed' ? 'Select the number and copy it yourself' : undefined}
    >
      {state === 'copied' ? 'Copied' : state === 'failed' ? 'Select it' : 'Copy'}
    </button>
  )
}
