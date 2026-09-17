"""A small preview for each material photo.

One nullable column on `photos`, holding the stored name of the preview. A
photo that predates this migration has none, and the gallery serves the full
picture in its place until `python -m scripts.make_thumbnails` is run. This
migration does not make the previews itself: that needs the image files and
an image library, and a schema step should need neither.

The downgrade drops the column. The preview files stay in the storage
directory as orphans -- nothing is lost that cannot be made again from the
originals.

Revision: 0007
Previous: 0006
Created:  2026-09-11
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0007'
down_revision: Union[str, None] = '0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply this change."""
    op.add_column('photos', sa.Column('thumb_path', sa.String(length=500), nullable=True))


def downgrade() -> None:
    """Undo this change."""
    op.drop_column('photos', 'thumb_path')
