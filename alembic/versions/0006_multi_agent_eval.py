"""Add step_evaluation_results table and pipeline_score column

Revision ID: 0006_multi_agent_eval
Revises: 0005_add_hallucination_claims
Create Date: 2026-02-26
"""

from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision: str = "0006_multi_agent_eval"
down_revision: Union[str, None] = "0005_add_hallucination_claims"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # Add pipeline_score to evaluation_results
    op.add_column("evaluation_results", sa.Column("pipeline_score", sa.Float(), nullable=True))

    # Create step_evaluation_results table
    op.create_table(
        "step_evaluation_results",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("trace_id", UUID(as_uuid=True), sa.ForeignKey("traces.id"), nullable=False, index=True),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("agent_name", sa.String(200), nullable=False),

        # Same metrics as trace-level
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

        # RAG-specific metrics
        sa.Column("answer_relevancy", sa.Float(), nullable=True),
        sa.Column("hallucination_score", sa.Float(), nullable=True),
        sa.Column("citation_check", sa.Float(), nullable=True),
        sa.Column("hallucination_claims", JSONB(), nullable=True),
        sa.Column("completeness_key_points", JSONB(), nullable=True),

        # Context retrieval quality metrics
        sa.Column("context_precision", sa.Float(), nullable=True),
        sa.Column("context_recall", sa.Float(), nullable=True),

        sa.Column("evaluated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("model_used", sa.String(50), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("step_evaluation_results")
    op.drop_column("evaluation_results", "pipeline_score")
