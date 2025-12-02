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
    # Drop Portmone-specific columns (PostgreSQL-compatible)
    op.drop_column("bonus_transactions", "portmone_bill_id")
    op.drop_column("bonus_transactions", "portmone_status")
    op.drop_column("bonus_transactions", "portmone_error_code")
    op.drop_column("bonus_transactions", "portmone_error_description")
    op.drop_column("bonus_transactions", "payee_id")
    
    # Update provider default to "manual" instead of "portmone"
    # First remove the old default, then set the new one
    op.alter_column("bonus_transactions", "provider", server_default=None)
    op.alter_column("bonus_transactions", "provider", server_default=sa.text("'manual'"))


def downgrade() -> None:
    """Restore Portmone-specific fields (for rollback purposes)."""
    # Restore Portmone-specific columns (PostgreSQL-compatible)
    op.add_column("bonus_transactions", sa.Column("portmone_bill_id", sa.String(length=64), nullable=True))
    op.add_column("bonus_transactions", sa.Column("portmone_status", sa.String(length=32), nullable=True))
    op.add_column("bonus_transactions", sa.Column("portmone_error_code", sa.String(length=32), nullable=True))
    op.add_column("bonus_transactions", sa.Column("portmone_error_description", sa.String(length=255), nullable=True))
    op.add_column("bonus_transactions", sa.Column("payee_id", sa.String(length=64), nullable=True))
    
    # Restore provider default to "portmone"
    op.alter_column("bonus_transactions", "provider", server_default=None)
    op.alter_column("bonus_transactions", "provider", server_default=sa.text("'portmone'"))

