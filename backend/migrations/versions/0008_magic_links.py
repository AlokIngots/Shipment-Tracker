"""Sign-in links sent by email.

A new table, `magic_links`: one row per link sent, holding a SHA-256 hash of
its token (never the token), when it expires, and when it was used. Nothing
existing changes, and signing in with a password works exactly as before.

The downgrade drops the table. Any link sent but not yet used stops working,
which is harmless -- the person asks for another, or uses their password.

Revision: 0008
Previous: 0007
Created:  2026-09-11
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0008'
down_revision: Union[str, None] = '0007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply this change."""
    op.create_table('magic_links',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_magic_links_token_hash'), 'magic_links', ['token_hash'], unique=True)
    op.create_index(op.f('ix_magic_links_user_id'), 'magic_links', ['user_id'], unique=False)


def downgrade() -> None:
    """Undo this change."""
    op.drop_index(op.f('ix_magic_links_user_id'), table_name='magic_links')
    op.drop_index(op.f('ix_magic_links_token_hash'), table_name='magic_links')
    op.drop_table('magic_links')
