// Guessing a document's type from its file name, for the several-at-once
// upload. Only a guess: staff see it in a dropdown and can change it before
// anything is saved, and a name that says nothing gets no guess at all.

export const DOCUMENT_TYPES = [
  'Packing List',
  'Commercial Invoice',
  'Bill of Lading',
  'Mill Test Certificate',
]

// Anything else staff name themselves (Certificate of Origin, say). The
// customer sees the name they type, so "Other" itself is never saved.
export const OTHER = 'Other'

// The server keeps a document type in 60 characters.
export const TYPE_MAX_LENGTH = 60

// Checked in this order, so "MTC invoice copy" is still a certificate. Each
// test sees the name in capitals, both whole ("PACKING LIST 12.PDF") and cut
// into words at anything that is not a letter or digit, so "B_L", "B-L" and
// "B/L" all become the two words B and L.
const RULES = [
  {
    type: 'Mill Test Certificate',
    test: (whole, words) =>
      words.some((w) => /^(MTC|TC)\d*$/.test(w) || w === 'TEST') ||
      /MILL\s*TEST|TEST\s*CERT/.test(whole),
  },
  {
    type: 'Bill of Lading',
    test: (whole, words, joined) =>
      words.some((w) => /^(BL|BOL|HBL|MBL|OBL)\d*$/.test(w)) ||
      /B[\s_./-]L(\b|[^A-Z])/.test(whole) ||
      /LADING/.test(joined),
  },
  {
    type: 'Packing List',
    test: (whole, words) =>
      words.some((w) => /^PL\d*$/.test(w)) || /PACKING/.test(whole),
  },
  {
    type: 'Commercial Invoice',
    test: (whole, words) =>
      words.some((w) => /^(CI|INV)\d*$/.test(w)) || /INVOICE|COMMERCIAL/.test(whole),
  },
]

// The type a file name suggests, or '' when it suggests none.
export function guessDocumentType(fileName) {
  const base = String(fileName || '').replace(/\.[A-Za-z0-9]+$/, '')
  const whole = base.toUpperCase()
  const words = whole.split(/[^A-Z0-9]+/).filter(Boolean)
  const joined = words.join('')
  const hit = RULES.find((rule) => rule.test(whole, words, joined))
  return hit ? hit.type : ''
}

// The same limits the server applies, checked before anything is sent, so
// a wrong file is flagged in the list rather than failing half-way through.
const ACCEPTED = /\.(pdf|jpe?g|png)$/i
export const MAX_BYTES = 20 * 1024 * 1024

export function fileProblem(file) {
  if (!ACCEPTED.test(file.name)) return 'Only PDF, JPG and PNG files can be uploaded.'
  if (file.size > MAX_BYTES) return 'Larger than 20 MB.'
  if (file.size === 0) return 'The file is empty.'
  return null
}
