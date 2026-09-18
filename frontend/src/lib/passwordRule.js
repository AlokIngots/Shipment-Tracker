// The password rule, as the screens state it and check it while typing.
//
// The server decides (password_problem in backend/app/core/security.py) and
// says it in the same words, PASSWORD_RULE there. This copy exists so a
// form can say what is missing before it is sent; if the two ever differ,
// the server's refusal is what the person sees.

export const PASSWORD_MIN_LENGTH = 8

export const PASSWORD_RULE = 'At least 8 characters, including a letter and a number'

// What the typed password still lacks, in a few words, or null if nothing.
export function passwordShortfall(password) {
  const missing = []
  if (password.length < PASSWORD_MIN_LENGTH) {
    missing.push(`${PASSWORD_MIN_LENGTH - password.length} more characters`)
  }
  if (!/\p{L}/u.test(password)) missing.push('a letter')
  if (!/\p{Nd}/u.test(password)) missing.push('a number')
  return missing.length ? missing.join(', ') : null
}

// Same letters as the server's temporary passwords: no 0/O or 1/l/I, so it
// survives being read out over the phone. Three groups of four, drawn again
// until it meets the rule -- twelve picks can come up with no number.
const READABLE = 'abcdefghjkmnpqrstuvwxyz23456789'

export function suggestPassword() {
  for (;;) {
    const picks = crypto.getRandomValues(new Uint32Array(12))
    const raw = Array.from(picks, (n) => READABLE[n % READABLE.length]).join('')
    const password = `${raw.slice(0, 4)}-${raw.slice(4, 8)}-${raw.slice(8)}`
    if (!passwordShortfall(password)) return password
  }
}
