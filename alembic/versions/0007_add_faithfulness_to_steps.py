"""Add faithfulness and faithfulness_claims to step_evaluation_results

Revision ID: 0007_add_faithfulness_to_steps
Revises: 0006_multi_agent_eval
Create Date: 2026-02-27
"""

from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "0007_add_faithfulness_to_steps"
down_revision: Union[str, None] = "0006_multi_agent_eval"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column(
        "step_evaluation_results",
        sa.Column("faithfulness", sa.Float(), nullable=True),
    )
    op.add_column(
        "step_evaluation_results",
        sa.Column("faithfulness_claims", JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("step_evaluation_results", "faithfulness_claims")
    op.drop_column("step_evaluation_results", "faithfulness")
