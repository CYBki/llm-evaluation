"""add RAG metrics columns

Revision ID: 0002_rag_metrics
Revises: 0001_initial_schema
Create Date: 2026-02-17 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002_rag_metrics"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("evaluation_results", sa.Column("answer_relevancy", sa.Float(), nullable=True))
    op.add_column("evaluation_results", sa.Column("faithfulness", sa.Float(), nullable=True))
    op.add_column("evaluation_results", sa.Column("hallucination_score", sa.Float(), nullable=True))
    op.add_column("evaluation_results", sa.Column("citation_check", sa.Float(), nullable=True))
    op.add_column(
        "evaluation_results",
        sa.Column("faithfulness_claims", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("evaluation_results", "faithfulness_claims")
    op.drop_column("evaluation_results", "citation_check")
    op.drop_column("evaluation_results", "hallucination_score")
    op.drop_column("evaluation_results", "faithfulness")
    op.drop_column("evaluation_results", "answer_relevancy")
