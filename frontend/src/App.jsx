import { useEffect, useState } from 'react'
import axios from 'axios'
import Header from './components/Header'
import ChangePasswordScreen from './screens/ChangePasswordScreen'
import LoginScreen from './screens/LoginScreen'
import OrderDetailScreen from './screens/OrderDetailScreen'
import OrdersScreen from './screens/OrdersScreen'
import SignInLinkScreen from './screens/SignInLinkScreen'
import StaffScreen from './screens/staff/StaffScreen'
import { CONTACT_EMAIL } from './lib/contact'
import { TOKEN_KEY, dropToken, recallToken, takeSignInLinkToken } from './lib/session'

// A token from a sign-in link, read once when the portal first loads and
// wiped from the address bar in the same moment. Read out here rather than
// inside the component, so React's development double-render cannot read it
// a second time and find it already gone.
const LINK_TOKEN = takeSignInLinkToken()

// Who is signed in, and therefore which screen they get. Nothing else. Each
// screen fetches its own data and owns its own state, so this file stays
// short enough to hold the whole of the portal's navigation in one view.
export default function App() {
  const [linkToken, setLinkToken] = useState(LINK_TOKEN)
  // 'restoring' while a remembered token is being checked, so the login
  // screen does not flash up for somebody who is already signed in. Not when
  // arriving from a sign-in link: that person is signing in afresh.
  const [restoring, setRestoring] = useState(!LINK_TOKEN)
  const [session, setSession] = useState(null)
  const [openOrderId, setOpenOrderId] = useState(null)
  const [passwordChanged, setPasswordChanged] = useState(false)
  // Change password pressed from a toolbar, as opposed to being made to.
  const [changingPassword, setChangingPassword] = useState(false)

  // On load, see whether this browser already holds a token and whether the
  // server still accepts it. A token can be refused for good reasons —
  // expired, password changed elsewhere, account deactivated — and all of
  // them mean the same thing here: show the login screen.
  useEffect(() => {
    if (LINK_TOKEN) return
    const token = recallToken()
    if (!token) {
      setRestoring(false)
      return
    }

    let cancelled = false
    axios.defaults.headers.common.Authorization = `Bearer ${token}`

    axios
      .get('/api/me')
      .then((res) => {
        if (cancelled) return
        setSession({ ...res.data, token })
      })
      .catch(() => {
        if (cancelled) return
        dropToken()
      })
      .finally(() => {
        if (!cancelled) setRestoring(false)
      })

    return () => {
      cancelled = true
    }
  }, [])

  // Signing out in one tab signs out every other tab of the portal too. The
  // token is shared by the whole browser now, so a tab left open would
  // otherwise go on showing orders to whoever sits down next.
  useEffect(() => {
    function onStorage(event) {
      if (event.key === TOKEN_KEY && !event.newValue) signOut()
    }
    window.addEventListener('storage', onStorage)
    return () => window.removeEventListener('storage', onStorage)
  }, [])

  function signedInByLink(data) {
    setLinkToken(null)
    setSession(data)
  }

  function signOut() {
    // End the sign-in on the server too, so a copy of the token taken from
    // this machine stops working at once rather than lasting 30 days. The
    // token is passed explicitly because dropToken() below removes the
    // shared header before the request would get round to reading it. Not
    // waited for: signing out on screen must never hang on the network. A
    // tab signed out by another tab finds no token here and sends nothing.
    const token = recallToken()
    if (token) {
      axios
        .post('/api/logout', null, { headers: { Authorization: `Bearer ${token}` } })
        .catch(() => {})
    }
    dropToken()
    setOpenOrderId(null)
    setPasswordChanged(false)
    setChangingPassword(false)
    setSession(null)
  }

  // Nothing but the password screen is reachable until a temporary password
  // has been replaced. The server only says so to somebody who signed in
  // WITH a temporary password; a password staff chose, or an email link,
  // goes straight through.
  const mustChangePassword = Boolean(session?.must_change_password)

  function passwordWasChanged() {
    setSession({ ...session, must_change_password: false })
    setChangingPassword(false)
    setPasswordChanged(true)
  }

  function startChangingPassword() {
    setPasswordChanged(false)
    setChangingPassword(true)
    window.scrollTo(0, 0)
  }

  // Worked out once, because five JSX blocks used to repeat it and one of
  // them getting out of step would put two screens on the page at the same
  // time.
  const showing = !session
    ? linkToken
      ? 'link'
      : 'login'
    : mustChangePassword || changingPassword
      ? 'password'
      : session.is_staff
        ? 'staff'
        : openOrderId === null
          ? 'orders'
          : 'order'

  return (
    <div className="page">
      <Header />
      <main className="main">
        {restoring && <p className="message">Signing you in…</p>}

        {!restoring && showing === 'login' && <LoginScreen onSignedIn={setSession} />}

        {!restoring && showing === 'link' && (
          <SignInLinkScreen
            token={linkToken}
            onSignedIn={signedInByLink}
            onStartOver={() => setLinkToken(null)}
          />
        )}

        {showing === 'password' && (
          <ChangePasswordScreen
            session={session}
            forced={mustChangePassword}
            onDone={passwordWasChanged}
            onCancel={() => setChangingPassword(false)}
            onSignOut={signOut}
          />
        )}

        {passwordChanged && showing !== 'password' && (
          <p className="banner" role="status">
            Your password has been changed.
          </p>
        )}

        {showing === 'staff' && (
          <StaffScreen
            session={session}
            onChangePassword={startChangingPassword}
            onSignOut={signOut}
          />
        )}

        {showing === 'orders' && (
          <OrdersScreen
            session={session}
            onChangePassword={startChangingPassword}
            onSignOut={signOut}
            onOpenOrder={setOpenOrderId}
          />
        )}

        {showing === 'order' && (
          <OrderDetailScreen
            orderId={openOrderId}
            session={session}
            onBack={() => setOpenOrderId(null)}
            onChangePassword={startChangingPassword}
            onSignOut={signOut}
          />
        )}
      </main>
      <footer className="footer">
        Stainless steel bright bars · Mumbai, India
        {/* On every screen, the sign-in page included, so a buyer with a
            question never has to leave the portal to find out who to ask. */}
        <span className="footer-contact">
          Questions? Write to{' '}
          <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>
        </span>
      </footer>
    </div>
  )
}
