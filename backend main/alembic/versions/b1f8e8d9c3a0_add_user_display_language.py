"""为用户增加独立显示语言偏好。

Revision ID: b1f8e8d9c3a0
Revises: 90a738e14bd1
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b1f8e8d9c3a0"
down_revision: Union[str, None] = "90a738e14bd1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 默认中文，确保已有用户迁移后无需补写数据即可正常使用。
    op.add_column(
        "users",
        sa.Column(
            "display_language",
            sa.String(length=8),
            nullable=False,
            server_default="zh",
            comment="用户显示语言: zh/en",
        ),
    )


def downgrade() -> None:
    # 回滚时移除该用户偏好字段。
    op.drop_column("users", "display_language")
