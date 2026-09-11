// The lifecycle a shipment moves through, in order. Mirrors
// backend/app/services/statuses.py, which is the authority: the server
// refuses anything not on its list, so this only has to agree.
//
// Four of these five are the steps the business named. "In transit" was
// already in the data and in the notification defaults, and it means
// something the others do not — at sea, rather than merely loaded — so it
// was kept and placed where it belongs.
export const SEQUENCE = [
  'In production',
  'Packed',
  'Shipped',
  'In transit',
  'Delivered',
]

export const CANCELLED = 'Cancelled'

export const ALL_STATUSES = [...SEQUENCE, CANCELLED]

// Only an order says this: some of it has left the factory, and either the
// rest has not or no shipment is ticked as the last one. The server works an
// order's status out (order_status in statuses.py); the portal only draws it.
export const PART_SHIPPED = 'Part shipped'

// Which step a status is, 1-based. Null for unset and for Cancelled, which
// is reachable from anywhere and is not part of the progression.
export function statusStep(status) {
  if (!status) return null
  const at = SEQUENCE.findIndex((s) => s.toLowerCase() === status.trim().toLowerCase())
  return at === -1 ? null : at + 1
}

const STATUS_CLASS = {
  'in production': 'pill--production',
  packed: 'pill--packed',
  shipped: 'pill--shipped',
  'in transit': 'pill--transit',
  delivered: 'pill--delivered',
  cancelled: 'pill--cancelled',
  'part shipped': 'pill--part',
}

// emptyLabel: what an unset status reads as. Staff see "Not set", which is
// what it is; a customer is better told "Awaiting update" than shown a gap.
export default function StatusPill({ status, emptyLabel = 'Not set' }) {
  if (!status) return <span className="pill pill--neutral">{emptyLabel}</span>

  const tone = STATUS_CLASS[status.trim().toLowerCase()] ?? 'pill--neutral'
  return <span className={`pill ${tone}`}>{status}</span>
}
