"""Add ground_truth to traces and context_precision/context_recall to evaluation_results.

Revision ID: 0002
Revises: 0001
Create Date: 2026-02-19
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_add_context_metrics"
down_revision = "0003_add_completeness_key_points"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("traces", sa.Column("ground_truth", sa.Text(), nullable=True))
    op.add_column("evaluation_results", sa.Column("context_precision", sa.Float(), nullable=True))
    op.add_column("evaluation_results", sa.Column("context_recall", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("evaluation_results", "context_recall")
    op.drop_column("evaluation_results", "context_precision")
    op.drop_column("traces", "ground_truth")
