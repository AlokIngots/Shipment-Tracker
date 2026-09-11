"""An order's status is worked out from its shipments, not typed.

- `shipments.is_final`, false for every shipment already there. Staff tick
  it on the last lot of an order.
- `orders.cancelled`, true for every order whose status was Cancelled.
  Cancelling is the one part of an order's status still set by hand.
- `orders.status` is dropped. Apart from Cancelled, every value in it was
  typed by hand and is exactly what this replaces. The activity record keeps
  each change made to it since step 24.

The downgrade puts `orders.status` back and fills it in from the shipments
by the same rules, so the older code shows something sensible rather than
"Not set" -- except that "Part shipped", which the older code would refuse
when the order was next saved, is written as "Shipped". The ticks and the
two new columns are dropped.

Revision: 0009
Previous: 0008
Created:  2026-09-11
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0009'
down_revision: Union[str, None] = '0008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Copied, not imported: a migration must go on doing what it did when it was
# written, whatever later happens to app/services/statuses.py.
SEQUENCE = ["In production", "Packed", "Shipped", "In transit", "Delivered"]
LEFT_THE_FACTORY = 3


def upgrade() -> None:
    """Apply this change."""
    op.add_column('orders', sa.Column('cancelled', sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column('shipments', sa.Column('is_final', sa.Boolean(), server_default=sa.false(), nullable=False))
    op.execute("UPDATE orders SET cancelled = true WHERE status = 'Cancelled'")
    op.drop_column('orders', 'status')


def downgrade() -> None:
    """Undo this change."""
    op.add_column('orders', sa.Column('status', sa.String(length=50), nullable=True))

    bind = op.get_bind()
    cancelled: dict[int, bool] = {}
    lots: dict[int, list[tuple[str | None, bool]]] = {}
    rows = bind.execute(sa.text(
        "SELECT o.id, o.cancelled, s.id, s.status, s.is_final "
        "FROM orders o LEFT JOIN shipments s ON s.order_id = o.id"
    ))
    for order_id, is_cancelled, shipment_id, status, is_final in rows:
        cancelled[order_id] = is_cancelled
        lots.setdefault(order_id, [])
        if shipment_id is not None:
            lots[order_id].append((status, is_final))

    for order_id, order_lots in lots.items():
        bind.execute(
            sa.text("UPDATE orders SET status = :status WHERE id = :id"),
            {"status": _older_status(cancelled[order_id], order_lots), "id": order_id},
        )

    op.drop_column('shipments', 'is_final')
    op.drop_column('orders', 'cancelled')


def _older_status(cancelled: bool, lots: list[tuple[str | None, bool]]) -> str:
    """statuses.order_status as it was at 0009, in words the older code knows."""
    if cancelled:
        return "Cancelled"
    live = [(status, final) for status, final in lots if status != "Cancelled"]
    if not live:
        return SEQUENCE[0]
    steps = [SEQUENCE.index(s) + 1 if s in SEQUENCE else 1 for s, _ in live]
    behind, ahead = min(steps), max(steps)
    finished = any(final for _, final in live)
    if finished and behind >= LEFT_THE_FACTORY:
        return SEQUENCE[behind - 1]
    if ahead >= LEFT_THE_FACTORY:
        return "Shipped"  # "Part shipped" to the newer code
    if finished:
        return SEQUENCE[behind - 1]
    return SEQUENCE[0]
