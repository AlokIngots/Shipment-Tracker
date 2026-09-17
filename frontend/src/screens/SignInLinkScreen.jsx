import { useEffect, useRef, useState } from 'react'
import axios from 'axios'
import { applyToken } from '../lib/session'

const EXPIRED = 'This link has expired, please request a new one.'

// Where a sign-in link from an email lands.
//
// It signs the person in the moment the page opens. There is no button to
// press: a customer who has already proved they hold the inbox should not be
// asked to confirm it.
//
// Why that is safe here, since it was not always. The button used to exist
// because company mail systems -- Outlook's Safe Links is the common one --
// open every link in an email before the person sees it, and a page that
// spent the link on opening would have been spent by that check. Two things
// mean it cannot be now:
//
//   * the token travels after the "#", which no browser ever sends to a
//     server, so a scanner fetching the address never learns it (this was
//     always true, and is why the risk was theoretical even then);
//   * the server keeps links reusable for 24 hours
//     (MAGIC_LINK_SINGLE_USE=false), so opening one twice costs nothing.
//
// The token is taken out of the address bar as the portal loads, before this
// screen is drawn, so a refresh does not try to redeem it a second time --
// it simply shows the sign-in screen.
export default function SignInLinkScreen({ token, onSignedIn, onStartOver }) {
  // 'busy' from the first moment: there is nothing to decide, only to wait.
  // Then 'expired', or 'error' (with a message) if it could not be done.
  const [state, setState] = useState('busy')
  const [message, setMessage] = useState(null)
  // React runs an effect twice in development. Redeeming twice would be
  // harmless while links are reusable and wrong the moment they are not, so
  // it is done once whatever the setting on the server.
  const started = useRef(false)

  async function signIn() {
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

  useEffect(() => {
    if (started.current) return
    started.current = true
    signIn()
    // Runs once, for the token this screen was opened with.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  if (state === 'expired') {
    return (
      <div className="card card--login" role="alert">
        <h2>Link expired</h2>
        <p className="lead">{EXPIRED}</p>
        <p className="login-hint login-hint--left">
          A sign-in link stops working once it expires. If you asked for more
          than one, only the newest works.
        </p>
        <button type="button" className="button" onClick={onStartOver}>
          Request a new link
        </button>
      </div>
    )
  }

  // Something went wrong that asking again might fix -- the network, or the
  // server being briefly unreachable. Not a dead end, and not the old
  // "Continue" button: this appears only after a failure.
  if (state === 'error') {
    return (
      <div className="card card--login">
        <h2>Signing you in</h2>
        <p className="error" role="alert">
          {message}
        </p>
        <button type="button" className="button" onClick={signIn}>
          Try again
        </button>
        <p className="login-hint">
          Still not working? Ask for a new sign-in link.{' '}
          <button type="button" className="linkish" onClick={onStartOver}>
            Request a new link
          </button>
        </p>
      </div>
    )
  }

  return (
    <div className="card card--login">
      <h2>Signing you in…</h2>
      <p className="lead" role="status">
        One moment — opening the Alok Ingots customer portal.
      </p>
    </div>
  )
}
