"""merge subscribers and citizen pivot

Revision ID: f3a1b2c4d5e6
Revises: e2f8b3c1d4a5, e9c4a2f1b8d3
Create Date: 2026-05-17 13:00:00.000000

"""
from typing import Sequence, Union

revision: str = "f3a1b2c4d5e6"
down_revision: Union[str, Sequence[str], None] = ("e2f8b3c1d4a5", "e9c4a2f1b8d3")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
