"""add hallucination_claims column

Revision ID: 0005_add_hallucination_claims
Revises: 0004_add_context_metrics
Create Date: 2026-02-23 12:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0005_add_hallucination_claims"
down_revision: Union[str, None] = "0004_add_context_metrics"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "evaluation_results",
        sa.Column("hallucination_claims", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("evaluation_results", "hallucination_claims")
