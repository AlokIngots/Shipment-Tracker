"""The activity record: who changed what, and when.

A new table, `audit_events`, and a trigger that makes it append-only. Every
change made through the admin console, the command-line tools or the CSV
importer adds a row here in the same transaction as the change itself.

The trigger refuses UPDATE, DELETE and TRUNCATE on the table, from anybody,
including somebody typing SQL. That is the point of it: a record the people
it records can tidy is not a record. It does not stop somebody with full
access to the database server, who could drop the trigger first -- nothing
inside a database can -- but it does stop a stolen staff session, a bug,
and a slip of the keyboard.

`CREATE OR REPLACE FUNCTION`, not `CREATE FUNCTION`, because
`seed.py --reset` drops the portal's tables but knows nothing about
functions, so the function survives a reset and must not make this migration
fail the next time it runs.

The downgrade drops the table and every event in it. Nothing else depends on
it, so nothing breaks -- but the history is gone for good. Back up first.

Revision: 0006
Previous: 0005
Created:  2026-09-11
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0006'
down_revision: Union[str, None] = '0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


REFUSE_CHANGE = """
CREATE OR REPLACE FUNCTION audit_events_refuse_change() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_events is append-only: an event cannot be changed or removed';
END;
$$ LANGUAGE plpgsql
"""


def upgrade() -> None:
    """Apply this change."""
    op.create_table('audit_events',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('happened_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('actor_user_id', sa.Integer(), nullable=True),
    sa.Column('actor_email', sa.String(length=255), nullable=True),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('action', sa.String(length=40), nullable=False),
    sa.Column('summary', sa.String(length=300), nullable=False),
    sa.Column('changes', sa.JSON(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.execute(REFUSE_CHANGE)
    op.execute(
        "CREATE TRIGGER audit_events_append_only "
        "BEFORE UPDATE OR DELETE ON audit_events "
        "FOR EACH ROW EXECUTE FUNCTION audit_events_refuse_change()"
    )
    # A row trigger does not see TRUNCATE, which empties a table without
    # deleting its rows one by one. This one does.
    op.execute(
        "CREATE TRIGGER audit_events_no_truncate "
        "BEFORE TRUNCATE ON audit_events "
        "FOR EACH STATEMENT EXECUTE FUNCTION audit_events_refuse_change()"
    )


def downgrade() -> None:
    """Undo this change."""
    op.execute("DROP TRIGGER IF EXISTS audit_events_no_truncate ON audit_events")
    op.execute("DROP TRIGGER IF EXISTS audit_events_append_only ON audit_events")
    op.drop_table('audit_events')
    op.execute("DROP FUNCTION IF EXISTS audit_events_refuse_change()")
