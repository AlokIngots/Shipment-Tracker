// Small shared helpers. Nothing here talks to the server or holds state.

// An em dash, for a field the server had nothing to put in. Written as an
// escape so it cannot be mistaken for a hyphen when reading the source.
export const DASH = '—'

// The API sends dates as YYYY-MM-DD. Customers here read DD/MM/YYYY.
export function fmtDate(value) {
  if (!value) return DASH
  const [y, m, d] = value.split('-')
  return `${d}/${m}/${y}`
}

// The server can refuse a request for several reasons, and FastAPI reports
// one of them (a missing or malformed field) as a list rather than a
// sentence. The server is the authority on what is acceptable, so show what
// it said and only fall back when it said nothing usable.
export function describeError(err, fallback) {
  const detail = err.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg
  return fallback
}

// An empty box on a form means "not given", not "an empty string" — or the
// portal would show a customer an order whose grade is blank rather than
// absent.
export function blankToNull(value) {
  const trimmed = String(value ?? '').trim()
  return trimmed === '' ? null : trimmed
}
