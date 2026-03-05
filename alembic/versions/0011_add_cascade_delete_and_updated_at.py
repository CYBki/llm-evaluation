"""add cascade delete and updated_at

Revision ID: 0011
Revises: 0010
Create Date: 2025-01-20
"""
from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add updated_at column to traces
    op.add_column(
        "traces",
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=True,
            server_default=sa.text("NOW()"),
        ),
    )
    # Backfill updated_at = created_at for existing rows
    op.execute("UPDATE traces SET updated_at = created_at WHERE updated_at IS NULL")
    op.alter_column("traces", "updated_at", nullable=False)

    # Update FK on evaluation_results to add ON DELETE CASCADE
    op.drop_constraint(
        "evaluation_results_trace_id_fkey", "evaluation_results", type_="foreignkey"
    )
    op.create_foreign_key(
        "evaluation_results_trace_id_fkey",
        "evaluation_results",
        "traces",
        ["trace_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Update FK on step_evaluation_results to add ON DELETE CASCADE
    op.drop_constraint(
        "step_evaluation_results_trace_id_fkey",
        "step_evaluation_results",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "step_evaluation_results_trace_id_fkey",
        "step_evaluation_results",
        "traces",
        ["trace_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    # Revert FK on step_evaluation_results
    op.drop_constraint(
        "step_evaluation_results_trace_id_fkey",
        "step_evaluation_results",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "step_evaluation_results_trace_id_fkey",
        "step_evaluation_results",
        "traces",
        ["trace_id"],
        ["id"],
    )

    # Revert FK on evaluation_results
    op.drop_constraint(
        "evaluation_results_trace_id_fkey", "evaluation_results", type_="foreignkey"
    )
    op.create_foreign_key(
        "evaluation_results_trace_id_fkey",
        "evaluation_results",
        "traces",
        ["trace_id"],
        ["id"],
    )

    # Drop updated_at column
    op.drop_column("traces", "updated_at")
