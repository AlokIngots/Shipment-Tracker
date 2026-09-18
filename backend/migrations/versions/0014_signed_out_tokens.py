"""Sign out ends the sign-in on the server: a table of ended sign-ins.

One new table, `signed_out_tokens`. Sign out writes the random id of the
token being ended; a token whose id is there is refused. Rows are removed
once the token would have expired anyway, so it never grows past about 30
days of sign-outs. Nothing already in the database is touched.

The downgrade drops the table. Tokens signed out before that start working
again until they expire (at most SESSION_TTL_DAYS), which is how Sign out
behaved before this migration.

Revision: 0014
Previous: 0013
Created:  2026-09-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0014'
down_revision: Union[str, None] = '0013'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply this change."""
    op.create_table('signed_out_tokens',
    sa.Column('token_id', sa.String(length=32), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('signed_out_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('token_id')
    )
    op.create_index(op.f('ix_signed_out_tokens_user_id'), 'signed_out_tokens', ['user_id'], unique=False)
    op.create_index(op.f('ix_signed_out_tokens_expires_at'), 'signed_out_tokens', ['expires_at'], unique=False)


def downgrade() -> None:
    """Undo this change."""
    op.drop_index(op.f('ix_signed_out_tokens_expires_at'), table_name='signed_out_tokens')
    op.drop_index(op.f('ix_signed_out_tokens_user_id'), table_name='signed_out_tokens')
    op.drop_table('signed_out_tokens')
