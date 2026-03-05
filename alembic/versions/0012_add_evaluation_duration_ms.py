"""add evaluation_duration_ms column

Revision ID: 0012_add_evaluation_duration_ms
Revises: 0011_add_cascade_delete_and_updated_at
Create Date: 2026-03-05 13:30:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0012_add_evaluation_duration_ms"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "evaluation_results",
        sa.Column("evaluation_duration_ms", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("evaluation_results", "evaluation_duration_ms")
