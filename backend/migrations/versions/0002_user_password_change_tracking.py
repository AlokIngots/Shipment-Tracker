"""Track whether a user still has the temporary password staff gave them.

Existing users get must_change_password = false, which is right: they chose
their own password, or they are demo accounts. Only accounts created by
manage_users.py start with it set.

This is the first migration to run against a database with rows in it.

Revision: 0002
Previous: 0001
Created:  2026-09-09
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply this change."""
    op.add_column('users', sa.Column('must_change_password', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('users', sa.Column('password_changed_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Undo this change."""
    op.drop_column('users', 'password_changed_at')
    op.drop_column('users', 'must_change_password')
