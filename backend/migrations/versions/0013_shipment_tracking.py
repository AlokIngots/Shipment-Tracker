"""Live container tracking: ShipsGo's reference and latest news per shipment.

One new table, `shipment_tracking`, one row per shipment at most (the unique
`shipment_id` promises it). A row is written only when a member of staff
switches tracking on for a shipment, which is the one step that costs a
ShipsGo credit; everything after that is refreshed by free reads.

Nothing already in the database is touched, and no shipment gets a row: live
tracking starts switched off everywhere and is turned on one shipment at a
time, on purpose.

The downgrade drops the table. The shipments in ShipsGo stay where they are
(deleting them would not refund anything), so upgrading again and pressing
Enable finds them by B/L number without spending a second credit.

Revision: 0013
Previous: 0012
Created:  2026-09-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0013'
down_revision: Union[str, None] = '0012'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "shipment_tracking",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("shipment_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False, server_default="shipsgo"),
        sa.Column("external_id", sa.Integer(), nullable=False),
        sa.Column("booking_number", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("carrier_name", sa.String(length=80), nullable=True),
        sa.Column("port_of_loading", sa.String(length=120), nullable=True),
        sa.Column("port_of_discharge", sa.String(length=120), nullable=True),
        sa.Column("loaded_at", sa.String(length=40), nullable=True),
        sa.Column("eta", sa.String(length=40), nullable=True),
        sa.Column("transshipments", sa.Integer(), nullable=True),
        sa.Column("container_count", sa.Integer(), nullable=True),
        sa.Column("containers", sa.JSON(), nullable=True),
        sa.Column("checked_at", sa.String(length=40), nullable=True),
        sa.Column("discarded_at", sa.String(length=40), nullable=True),
        sa.Column(
            "enabled_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("enabled_by", sa.String(length=255), nullable=True),
        sa.Column("reused", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("refreshed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("failures", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["shipment_id"], ["shipments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_shipment_tracking_shipment_id", "shipment_tracking", ["shipment_id"], unique=True
    )
    op.create_index(
        "ix_shipment_tracking_external_id", "shipment_tracking", ["external_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_shipment_tracking_external_id", table_name="shipment_tracking")
    op.drop_index("ix_shipment_tracking_shipment_id", table_name="shipment_tracking")
    op.drop_table("shipment_tracking")
