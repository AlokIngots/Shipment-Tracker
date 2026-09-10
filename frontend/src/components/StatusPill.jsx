// Maps a status to a pill colour. Unknown statuses fall back to grey, so a
// status the importer has never seen before still renders as a status rather
// than breaking the row.
const STATUS_CLASS = {
  'in production': 'pill--production',
  'ready to ship': 'pill--neutral',
  shipped: 'pill--shipped',
  'in transit': 'pill--transit',
  delivered: 'pill--delivered',
  draft: 'pill--neutral',
  cancelled: 'pill--cancelled',
}

// The statuses the staff forms offer. Free text is still accepted, because
// the CSV importer accepts it and the two must not disagree; these are only
// the suggestions.
export const ORDER_STATUSES = [
  'In production',
  'Ready to ship',
  'In transit',
  'Shipped',
  'Delivered',
  'Cancelled',
]

export const SHIPMENT_STATUSES = ['Shipped', 'In transit', 'Delivered', 'Cancelled']

export default function StatusPill({ status }) {
  if (!status) return <span className="pill pill--neutral">—</span>

  const tone = STATUS_CLASS[status.trim().toLowerCase()] ?? 'pill--neutral'
  return <span className={`pill ${tone}`}>{status}</span>
}
