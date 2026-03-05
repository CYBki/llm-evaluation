"""Add webhook_url column to traces

Revision ID: 0010_add_webhook_url
Revises: 0009_add_token_tracking
Create Date: 2026-03-05
"""

from typing import Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0010_add_webhook_url"
down_revision: Union[str, None] = "0009_add_token_tracking"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column(
        "traces",
        sa.Column("webhook_url", sa.String(2048), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("traces", "webhook_url")
