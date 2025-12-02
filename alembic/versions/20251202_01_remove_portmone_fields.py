"""Remove Portmone-specific fields from bonus_transactions

Revision ID: 20251202_01
Revises: 20251202_00
Create Date: 2025-12-02 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20251202_01"
down_revision = "20251202_00"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Remove Portmone-specific fields from bonus_transactions table."""
    with op.batch_alter_table("bonus_transactions") as batch:
        # Drop Portmone-specific columns
        batch.drop_column("portmone_bill_id")
        batch.drop_column("portmone_status")
        batch.drop_column("portmone_error_code")
        batch.drop_column("portmone_error_description")
        batch.drop_column("payee_id")
        
        # Update provider default to "manual" instead of "portmone"
        batch.alter_column("provider", server_default="manual")


def downgrade() -> None:
    """Restore Portmone-specific fields (for rollback purposes)."""
    with op.batch_alter_table("bonus_transactions") as batch:
        # Restore Portmone-specific columns
        batch.add_column(sa.Column("portmone_bill_id", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("portmone_status", sa.String(length=32), nullable=True))
        batch.add_column(sa.Column("portmone_error_code", sa.String(length=32), nullable=True))
        batch.add_column(sa.Column("portmone_error_description", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("payee_id", sa.String(length=64), nullable=True))
        
        # Restore provider default to "portmone"
        batch.alter_column("provider", server_default="portmone")

