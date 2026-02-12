"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-02-12 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("api_key_hash", sa.String(length=64), nullable=False),
        sa.Column("api_key_prefix", sa.String(length=8), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("api_key_hash"),
        sa.UniqueConstraint("email"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=False)
    op.create_index(op.f("ix_users_api_key_hash"), "users", ["api_key_hash"], unique=False)

    op.create_table(
        "traces",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("contexts", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_traces_user_id"), "traces", ["user_id"], unique=False)
    op.create_index(op.f("ix_traces_status"), "traces", ["status"], unique=False)
    op.create_index(op.f("ix_traces_created_at"), "traces", ["created_at"], unique=False)

    op.create_table(
        "evaluation_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("clarity", sa.Float(), nullable=True),
        sa.Column("specificity", sa.Float(), nullable=True),
        sa.Column("is_off_topic", sa.Boolean(), nullable=True),
        sa.Column("completeness", sa.Float(), nullable=True),
        sa.Column("coherence", sa.Float(), nullable=True),
        sa.Column("helpfulness", sa.Float(), nullable=True),
        sa.Column("is_deflection", sa.Boolean(), nullable=True),
        sa.Column("overall_score", sa.Float(), nullable=True),
        sa.Column("evaluation_confidence", sa.Float(), nullable=True),
        sa.Column("reasoning_summary", sa.Text(), nullable=True),
        sa.Column("disagreement_claims", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("stage_1_reasoning", sa.Text(), nullable=True),
        sa.Column("raw_response", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(), nullable=False),
        sa.Column("model_used", sa.String(length=50), nullable=True),
        sa.Column("prompt_version", sa.String(length=50), nullable=True),
        sa.Column("rubric_version", sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(["trace_id"], ["traces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("trace_id"),
    )
    op.create_index(op.f("ix_evaluation_results_trace_id"), "evaluation_results", ["trace_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_evaluation_results_trace_id"), table_name="evaluation_results")
    op.drop_table("evaluation_results")

    op.drop_index(op.f("ix_traces_created_at"), table_name="traces")
    op.drop_index(op.f("ix_traces_status"), table_name="traces")
    op.drop_index(op.f("ix_traces_user_id"), table_name="traces")
    op.drop_table("traces")

    op.drop_index(op.f("ix_users_api_key_hash"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
