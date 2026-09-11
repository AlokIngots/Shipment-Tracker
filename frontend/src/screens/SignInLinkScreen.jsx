import { useState } from 'react'
import axios from 'axios'
import { applyToken } from '../lib/session'

const EXPIRED = 'This link has expired, please request a new one.'

// Where a sign-in link from an email lands.
//
// It waits for a press of the button instead of signing in the moment the
// page opens. Company mail systems — Outlook's Safe Links is the common one
// — open every link in an email to check it before the person ever sees it.
// A page that spent the link on opening would be spent by that check, and
// the customer would click a link already used up. A scanner does not press
// buttons.
export default function SignInLinkScreen({ token, onSignedIn, onStartOver }) {
  // 'ready', 'busy', 'expired', or 'error' (with a message).
  const [state, setState] = useState('ready')
  const [message, setMessage] = useState(null)

  async function continueSigningIn() {
    setState('busy')
    setMessage(null)
    try {
      const res = await axios.post('/api/magic-link/redeem', { token })
      applyToken(res.data.token)
      onSignedIn(res.data)
    } catch (err) {
      if (err.response?.status === 400) {
        setState('expired')
        return
      }
      const detail = err.response?.data?.detail
      setMessage(
        typeof detail === 'string' ? detail : 'Could not reach the server. Please try again.',
      )
      setState('error')
    }
  }

  if (state === 'expired') {
    return (
      <div className="card card--login" role="alert">
        <h2>Link expired</h2>
        <p className="lead">{EXPIRED}</p>
        <p className="login-hint login-hint--left">
          A sign-in link works once, and only for 15 minutes after it was sent.
          If you asked for more than one, only the newest works.
        </p>
        <button type="button" className="button" onClick={onStartOver}>
          Request a new link
        </button>
      </div>
    )
  }

  return (
    <div className="card card--login">
      <h2>Finish signing in</h2>
      <p className="lead">
        You opened a sign-in link for the Alok Ingots customer portal.
      </p>

      {message && (
        <p className="error" role="alert">
          {message}
        </p>
      )}

      <button
        type="button"
        className="button"
        onClick={continueSigningIn}
        disabled={state === 'busy'}
      >
        {state === 'busy' ? 'Signing you in…' : 'Continue to the portal'}
      </button>
      <p className="login-hint">
        Did not ask for this? Close this page. Nothing happens unless you
        continue.
      </p>
    </div>
  )
}
