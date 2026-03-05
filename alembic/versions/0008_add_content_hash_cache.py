"""Add content_hash column to evaluation_results for cache lookup

Revision ID: 0008_add_content_hash_cache
Revises: 0007_add_faithfulness_to_steps
Create Date: 2026-03-05
"""

from typing import Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0008_add_content_hash_cache"
down_revision: Union[str, None] = "0007_add_faithfulness_to_steps"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column(
        "evaluation_results",
        sa.Column("content_hash", sa.String(64), nullable=True),
    )
    op.create_index(
        "ix_evaluation_results_content_hash",
        "evaluation_results",
        ["content_hash"],
    )


def downgrade() -> None:
    op.drop_index("ix_evaluation_results_content_hash", table_name="evaluation_results")
    op.drop_column("evaluation_results", "content_hash")
