"""add completeness_key_points column

Revision ID: 0002_add_completeness_key_points
Revises: 0001_initial_schema
Create Date: 2026-02-18 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003_add_completeness_key_points"
down_revision: Union[str, None] = "0002_rag_metrics"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "evaluation_results",
        sa.Column("completeness_key_points", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("evaluation_results", "completeness_key_points")
