"""add location and weather risk fields

Revision ID: e3b8c6a4d2f9
Revises: c7a9d2f4b6e1
Create Date: 2026-07-19 23:40:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e3b8c6a4d2f9"
down_revision: Union[str, None] = "c7a9d2f4b6e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("detection_tasks", sa.Column("latitude", sa.Float(), nullable=True, comment="检测地点纬度"))
    op.add_column("detection_tasks", sa.Column("longitude", sa.Float(), nullable=True, comment="检测地点经度"))
    op.add_column("detection_tasks", sa.Column("location_name", sa.String(length=255), nullable=True, comment="检测地点名称"))
    op.add_column("detection_tasks", sa.Column("location_source", sa.String(length=20), nullable=True, comment="位置来源: browser/manual/exif/other"))
    op.add_column("detection_tasks", sa.Column("location_updated_at", sa.DateTime(), nullable=True, comment="位置更新时间"))

    op.add_column("detection_tasks", sa.Column("environment_risk_level", sa.String(length=32), nullable=True, comment="天气环境风险: low/moderate/high/critical/unavailable"))
    op.add_column("detection_tasks", sa.Column("weather_summary", sa.Text(), nullable=True, comment="天气风险摘要"))
    op.add_column("detection_tasks", sa.Column("weather_recommendations", sa.JSON(), nullable=True, comment="天气相关建议"))
    op.add_column("detection_tasks", sa.Column("weather_snapshot", sa.JSON(), nullable=True, comment="天气接口快照"))
    op.add_column("detection_tasks", sa.Column("weather_updated_at", sa.DateTime(), nullable=True, comment="天气风险更新时间"))


def downgrade() -> None:
    op.drop_column("detection_tasks", "weather_updated_at")
    op.drop_column("detection_tasks", "weather_snapshot")
    op.drop_column("detection_tasks", "weather_recommendations")
    op.drop_column("detection_tasks", "weather_summary")
    op.drop_column("detection_tasks", "environment_risk_level")
    op.drop_column("detection_tasks", "location_updated_at")
    op.drop_column("detection_tasks", "location_source")
    op.drop_column("detection_tasks", "location_name")
    op.drop_column("detection_tasks", "longitude")
    op.drop_column("detection_tasks", "latitude")
