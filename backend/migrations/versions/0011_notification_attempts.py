"""Notifications remember when they were last tried, and how often.

The table already recorded the outcome of each message, but it only ever
held the moment the row was first written. A message that was suppressed in
the morning and genuinely sent in the afternoon still said "morning", which
is precisely the wrong answer on a screen whose whole job is to say what
has been sent and what is still waiting.

- `notifications.last_attempt_at`, filled in from `created_at` for every row
  already there: the only attempt those rows know about is the one that made
  them.
- `notifications.attempts`, 1 for every row already there, for the same
  reason.

The downgrade drops both. Nothing else knows about them.

Numbered 0011 and not 0010 on purpose. 0010 is already taken by
`0010_password_reset_links` on `feature/step30-password-reset`, which is held
unmerged on the user's decision. Two files claiming revision 0010 is the one
Alembic mistake there is no clean way out of, so this one steps over it. If
step 30 is ever merged, its migration needs renumbering to follow this one --
change its `revision` to 0012 and its `down_revision` to 0011.

Revision: 0011
Previous: 0009
Created:  2026-09-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0011'
down_revision: Union[str, None] = '0009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "notifications",
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "notifications",
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="1"),
    )
    # Every row that exists was written by an attempt, so that attempt is
    # both the last one and the only one.
    op.execute(
        "UPDATE notifications SET last_attempt_at = created_at "
        "WHERE last_attempt_at IS NULL"
    )


def downgrade() -> None:
    op.drop_column("notifications", "attempts")
    op.drop_column("notifications", "last_attempt_at")
