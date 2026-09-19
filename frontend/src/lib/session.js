// Where the sign-in token is kept between page loads.
//
// localStorage, since 18 Sep 2026: somebody who signs in stays signed in
// for SESSION_TTL_DAYS (30 by default), through closing the browser, so a
// customer who looks in once a week is not asked to sign in every time.
// The server decides how long the token lasts; this only keeps it. Sign out
// removes it at once -- from every tab, see App.jsx -- which is what to
// press on a shared machine in a shipping office.
//
// Until then it was sessionStorage, thrown away when the tab closed. A
// token left there by the old site is still read once, moved here, and
// removed, so nobody already signed in is signed out by the change.
//
// Every read and write is wrapped, because a browser set to block site data
// throws rather than returning nothing, and being unable to remember a token
// is not a reason to fail to load the portal.

import axios from 'axios'

export const TOKEN_KEY = 'alok.portal.token'

export function rememberToken(token) {
  try {
    localStorage.setItem(TOKEN_KEY, token)
  } catch {
    // Nothing to do: the portal still works, it just forgets on refresh.
  }
}

export function recallToken() {
  try {
    const kept = localStorage.getItem(TOKEN_KEY)
    if (kept) return kept
    const old = sessionStorage.getItem(TOKEN_KEY)
    if (old) {
      sessionStorage.removeItem(TOKEN_KEY)
      localStorage.setItem(TOKEN_KEY, old)
    }
    return old
  } catch {
    return null
  }
}

export function forgetToken() {
  for (const store of [() => localStorage, () => sessionStorage]) {
    try {
      store().removeItem(TOKEN_KEY)
    } catch {
      // Nothing to do.
    }
  }
}

// A sign-in link arrives as https://portal.alokindia.co.in/#sign-in=<token>.
// The token sits after the #, which a browser never sends to a server, so it
// cannot end up in an access log. It is read once and wiped from the address
// bar straight away: left there, it would sit in the browser's history for
// the next person at a shared computer to find.
const LINK_PREFIX = '#sign-in='

export function takeSignInLinkToken() {
  const { hash, pathname, search } = window.location
  if (!hash.startsWith(LINK_PREFIX)) return null

  const token = decodeURIComponent(hash.slice(LINK_PREFIX.length))
  try {
    window.history.replaceState(null, '', pathname + search)
  } catch {
    // Nothing to do: signing in still works, the address bar just keeps it.
  }
  return token || null
}

// Start using a token: send it with every later request, and remember it for
// this browser. Not a React hook, despite what the old name (useToken) suggested.
export function applyToken(token) {
  axios.defaults.headers.common.Authorization = `Bearer ${token}`
  rememberToken(token)
}

// Stop using it, both places, so nothing is left behind for the next person
// at the same machine.
export function dropToken() {
  forgetToken()
  delete axios.defaults.headers.common.Authorization
}
