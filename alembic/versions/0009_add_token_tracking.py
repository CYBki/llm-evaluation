"""Add token usage and cost tracking columns to evaluation_results

Revision ID: 0009_add_token_tracking
Revises: 0008_add_content_hash_cache
Create Date: 2026-03-05
"""

from typing import Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0009_add_token_tracking"
down_revision: Union[str, None] = "0008_add_content_hash_cache"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column(
        "evaluation_results",
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
    )
    op.add_column(
        "evaluation_results",
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
    )
    op.add_column(
        "evaluation_results",
        sa.Column("total_tokens", sa.Integer(), nullable=True),
    )
    op.add_column(
        "evaluation_results",
        sa.Column("cost_usd", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("evaluation_results", "cost_usd")
    op.drop_column("evaluation_results", "total_tokens")
    op.drop_column("evaluation_results", "completion_tokens")
    op.drop_column("evaluation_results", "prompt_tokens")
