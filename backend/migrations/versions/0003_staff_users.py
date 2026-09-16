"""Alok Ingots staff logins.

Staff belong to no customer, so users.customer_id becomes optional. Every
existing row has one and keeps it; only a staff login may leave it empty.

Revision: 0003
Previous: 0002
Created:  2026-09-09
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0003'
down_revision: Union[str, None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply this change."""
    op.add_column('users', sa.Column('is_staff', sa.Boolean(), server_default='false', nullable=False))
    op.alter_column('users', 'customer_id',
               existing_type=sa.INTEGER(),
               nullable=True)


def downgrade() -> None:
    """Undo this change.

    Staff logins cannot exist without this migration - they are the only
    rows with no customer - so going back deletes them. Customer logins and
    every order, shipment and document are untouched. Nothing else in the
    database refers to a staff user.
    """
    op.execute("DELETE FROM users WHERE customer_id IS NULL")
    op.alter_column('users', 'customer_id',
               existing_type=sa.INTEGER(),
               nullable=False)
    op.drop_column('users', 'is_staff')
