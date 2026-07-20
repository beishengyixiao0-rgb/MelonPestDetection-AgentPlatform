"""expand detection task risk level length

Revision ID: f4a7d8c9b2e0
Revises: e3b8c6a4d2f9
Create Date: 2026-07-20 12:35:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f4a7d8c9b2e0"
down_revision: Union[str, None] = "e3b8c6a4d2f9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "detection_tasks",
        "risk_level",
        existing_type=sa.String(length=20),
        type_=sa.String(length=32),
        existing_nullable=True,
        existing_comment="风险等级: low/medium/high/critical",
        comment="风险等级: low/moderate/high/critical/insufficient_information",
    )


def downgrade() -> None:
    op.execute(
        "UPDATE detection_tasks SET risk_level = NULL "
        "WHERE char_length(risk_level) > 20"
    )
    op.alter_column(
        "detection_tasks",
        "risk_level",
        existing_type=sa.String(length=32),
        type_=sa.String(length=20),
        existing_nullable=True,
        existing_comment="风险等级: low/moderate/high/critical/insufficient_information",
        comment="风险等级: low/medium/high/critical",
    )
