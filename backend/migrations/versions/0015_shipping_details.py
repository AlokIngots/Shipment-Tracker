"""Shipping details that had nowhere to go: twelve nullable columns.

What the Bill of Lading and the export paperwork carry that the portal could
not store until now.

  customers  address, eori_number, contact_name, contact_email
             Staff only. The contact is a person to write to, not a login.
  orders     order_date (the customer sees it), shipping_bill_no (staff only)
  shipments  port_of_loading, port_of_discharge, voyage_no, seal_no,
             container_size, gross_weight (the customer sees all six)

Every column is nullable and every row already in the tables is left empty:
these facts are on paper for past orders, and filling them in is a job for
staff, not a guess made here.

The downgrade drops the twelve columns and whatever was typed into them.

Revision: 0015
Previous: 0014
Created:  2026-09-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0015'
down_revision: Union[str, None] = '0014'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


COLUMNS = {
    "customers": [
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("eori_number", sa.String(length=20), nullable=True),
        sa.Column("contact_name", sa.String(length=200), nullable=True),
        sa.Column("contact_email", sa.String(length=255), nullable=True),
    ],
    "orders": [
        sa.Column("order_date", sa.Date(), nullable=True),
        sa.Column("shipping_bill_no", sa.String(length=60), nullable=True),
    ],
    "shipments": [
        sa.Column("port_of_loading", sa.String(length=100), nullable=True),
        sa.Column("port_of_discharge", sa.String(length=100), nullable=True),
        sa.Column("voyage_no", sa.String(length=40), nullable=True),
        sa.Column("seal_no", sa.String(length=60), nullable=True),
        sa.Column("container_size", sa.String(length=30), nullable=True),
        sa.Column("gross_weight", sa.Numeric(14, 3), nullable=True),
    ],
}


def upgrade() -> None:
    """Apply this change."""
    for table, columns in COLUMNS.items():
        for column in columns:
            op.add_column(table, column)


def downgrade() -> None:
    """Undo this change."""
    for table, columns in reversed(list(COLUMNS.items())):
        for column in reversed(columns):
            op.drop_column(table, column.name)
