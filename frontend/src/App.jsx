import { useEffect, useState } from 'react'
import axios from 'axios'
import Header from './components/Header'
import ChangePasswordScreen from './screens/ChangePasswordScreen'
import LoginScreen from './screens/LoginScreen'
import OrderDetailScreen from './screens/OrderDetailScreen'
import OrdersScreen from './screens/OrdersScreen'
import SignInLinkScreen from './screens/SignInLinkScreen'
import StaffScreen from './screens/staff/StaffScreen'
import { dropToken, recallToken, takeSignInLinkToken } from './lib/session'

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
  const [changingPassword, setChangingPassword] = useState(false)
  const [passwordChanged, setPasswordChanged] = useState(false)

  // On load, see whether this tab already holds a token and whether the
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

  function signedInByLink(data) {
    setLinkToken(null)
    setSession(data)
  }

  function signOut() {
    dropToken()
    setOpenOrderId(null)
    setChangingPassword(false)
    setPasswordChanged(false)
    setSession(null)
  }

  // Nothing but the password screen is reachable until a temporary password
  // has been replaced.
  const mustChangePassword = Boolean(session?.must_change_password)

  function passwordWasChanged() {
    setSession({ ...session, must_change_password: false })
    setChangingPassword(false)
    setPasswordChanged(true)
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
            onSignOut={signOut}
            onChangePassword={() => setChangingPassword(true)}
          />
        )}

        {showing === 'orders' && (
          <OrdersScreen
            session={session}
            onSignOut={signOut}
            onOpenOrder={setOpenOrderId}
            onChangePassword={() => setChangingPassword(true)}
          />
        )}

        {showing === 'order' && (
          <OrderDetailScreen
            orderId={openOrderId}
            session={session}
            onBack={() => setOpenOrderId(null)}
            onSignOut={signOut}
          />
        )}
      </main>
      <footer className="footer">
        Stainless steel bright bars · Mumbai, India
      </footer>
    </div>
  )
}
