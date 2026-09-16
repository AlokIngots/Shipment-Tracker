"""The shipping line a shipment travels with, so its own tracking can be linked.

One new column, `shipments.carrier`, free text and nullable. Every row already
in the table predates it and is left empty: the carrier of a past shipment is
on its Bill of Lading, not in the portal, and guessing it from the B/L prefix
would be a guess written into real data.

No format is checked, for the same reason `bl_number` checks none -- there is
no register of carrier names, and refusing anything would only refuse a real
one. What matters is that the name matches a carrier the portal knows how to
build a tracking link for, and that is matched loosely (case and punctuation
ignored, with aliases) rather than by forcing staff to type a code.

The downgrade drops the column. Nothing else knows about it, and the tracking
link is built on every read rather than stored, so nothing goes stale.

Revision: 0012
Previous: 0011
Created:  2026-09-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0012'
down_revision: Union[str, None] = '0011'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "shipments",
        sa.Column("carrier", sa.String(length=60), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("shipments", "carrier")
