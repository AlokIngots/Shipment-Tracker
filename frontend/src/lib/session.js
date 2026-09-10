// Where the sign-in token is kept between page loads.
//
// sessionStorage, not localStorage, on purpose. sessionStorage survives a
// refresh and a link opened in the same tab, and is thrown away when the tab
// is closed. localStorage would survive the browser being closed and
// reopened, which is convenient on your own laptop and wrong on the shared
// machine in a shipping office.
//
// Every read and write is wrapped, because a browser set to block site data
// throws rather than returning nothing, and being unable to remember a token
// is not a reason to fail to load the portal.

import axios from 'axios'

const TOKEN_KEY = 'alok.portal.token'

export function rememberToken(token) {
  try {
    sessionStorage.setItem(TOKEN_KEY, token)
  } catch {
    // Nothing to do: the portal still works, it just forgets on refresh.
  }
}

export function recallToken() {
  try {
    return sessionStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function forgetToken() {
  try {
    sessionStorage.removeItem(TOKEN_KEY)
  } catch {
    // Nothing to do.
  }
}

// Start using a token: send it with every later request, and remember it for
// this tab. Not a React hook, despite what the old name (useToken) suggested.
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
