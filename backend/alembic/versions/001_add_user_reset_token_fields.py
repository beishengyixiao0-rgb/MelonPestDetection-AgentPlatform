"""add user reset_token and reset_token_expires_at fields

Revision ID: 001
Revises: d4202e4685c4
Create Date: 2026-07-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = 'd4202e4685c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('reset_token', sa.String(length=100), nullable=True, comment='密码重置令牌')
    )
    op.add_column(
        'users',
        sa.Column('reset_token_expires_at', sa.DateTime(), nullable=True, comment='重置令牌过期时间')
    )


def downgrade() -> None:
    op.drop_column('users', 'reset_token_expires_at')
    op.drop_column('users', 'reset_token')
