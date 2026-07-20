"""add history treatment and severity assessment fields

Revision ID: c7a9d2f4b6e1
Revises: bd5115dc322e
Create Date: 2026-07-19 23:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c7a9d2f4b6e1"
down_revision: Union[str, None] = "bd5115dc322e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "detection_tasks",
        sa.Column(
            "treatment_status",
            sa.String(length=20),
            nullable=False,
            server_default="pending",
            comment="治疗状态: pending/in_progress/monitoring/treated/resolved",
        ),
    )
    op.add_column(
        "detection_tasks",
        sa.Column("treatment_note", sa.Text(), nullable=True, comment="用户维护的治疗备注"),
    )
    op.add_column(
        "detection_tasks",
        sa.Column("treatment_updated_at", sa.DateTime(), nullable=True, comment="治疗状态更新时间"),
    )

    op.create_table(
        "severity_assessments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False, comment="所属检测任务"),
        sa.Column("class_name", sa.String(length=100), nullable=False, comment="评估类别"),
        sa.Column("answers", sa.JSON(), nullable=False, comment="用户问卷答案"),
        sa.Column(
            "risk_level",
            sa.String(length=32),
            nullable=False,
            comment="严重程度: low/moderate/high/critical/insufficient_information",
        ),
        sa.Column(
            "assessment_confidence",
            sa.String(length=20),
            nullable=False,
            server_default="medium",
            comment="评估可信度: low/medium/high",
        ),
        sa.Column("summary", sa.Text(), nullable=False, comment="评估摘要"),
        sa.Column("reasons", sa.JSON(), nullable=False, comment="评估依据"),
        sa.Column("uncertainties", sa.JSON(), nullable=False, comment="不确定信息"),
        sa.Column("recommended_actions", sa.JSON(), nullable=False, comment="建议措施"),
        sa.Column("llm_model", sa.String(length=100), nullable=True, comment="生成说明时使用的模型"),
        sa.Column("created_at", sa.DateTime(), nullable=True, comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), nullable=True, comment="更新时间"),
        sa.ForeignKeyConstraint(["task_id"], ["detection_tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_severity_assessments_task_id"),
        "severity_assessments",
        ["task_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_severity_assessments_class_name"),
        "severity_assessments",
        ["class_name"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_severity_assessments_class_name"), table_name="severity_assessments")
    op.drop_index(op.f("ix_severity_assessments_task_id"), table_name="severity_assessments")
    op.drop_table("severity_assessments")
    op.drop_column("detection_tasks", "treatment_updated_at")
    op.drop_column("detection_tasks", "treatment_note")
    op.drop_column("detection_tasks", "treatment_status")
