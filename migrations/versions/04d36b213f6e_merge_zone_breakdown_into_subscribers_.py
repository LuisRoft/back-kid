"""merge zone breakdown into subscribers chain

Revision ID: 04d36b213f6e
Revises: f3a1b2c4d5e6, f3d8e1a47b29
Create Date: 2026-05-17 20:01:23.793522

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '04d36b213f6e'
down_revision: Union[str, Sequence[str], None] = ('f3a1b2c4d5e6', 'f3d8e1a47b29')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
