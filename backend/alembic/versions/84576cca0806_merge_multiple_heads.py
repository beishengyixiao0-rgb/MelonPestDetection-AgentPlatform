"""merge multiple heads

Revision ID: 84576cca0806
Revises: 7dff0d28d157, f4a7d8c9b2e0
Create Date: 2026-07-20 15:16:00.759299

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '84576cca0806'
down_revision: Union[str, None] = ('7dff0d28d157', 'f4a7d8c9b2e0')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
