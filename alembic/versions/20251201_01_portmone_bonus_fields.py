"""Add Portmone columns to bonus transactions

Revision ID: 20251201_01
Revises: 
Create Date: 2025-12-01 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20251201_01"
down_revision = "20251201_00"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # This migration is a no-op for fresh databases because the initial schema
    # (20251201_00) already creates all the Portmone columns with correct names.
    # This migration exists for backward compatibility with databases that had
    # the old easypay_* column names.
    
    from sqlalchemy import inspect
    
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('bonus_transactions')]
    
    # Only perform operations if old columns exist (migrating from old schema)
    if "easypay_status" in columns and "payout_status" not in columns:
        with op.batch_alter_table("bonus_transactions") as batch:
            batch.alter_column("easypay_status", new_column_name="payout_status")
    
    if "easypay_reference" in columns and "portmone_bill_id" not in columns:
        with op.batch_alter_table("bonus_transactions") as batch:
            batch.alter_column("easypay_reference", new_column_name="portmone_bill_id")
    
    # Add missing columns only if they don't exist
    with op.batch_alter_table("bonus_transactions") as batch:
        if "provider" not in columns:
            batch.add_column(sa.Column("provider", sa.String(length=32), nullable=False, server_default="portmone"))
        if "currency" not in columns:
            batch.add_column(sa.Column("currency", sa.String(length=8), nullable=False, server_default="UAH"))
        if "payee_id" not in columns:
            batch.add_column(sa.Column("payee_id", sa.String(length=64), nullable=True))
        if "contract_number" not in columns:
            batch.add_column(sa.Column("contract_number", sa.String(length=64), nullable=True))
        if "portmone_status" not in columns:
            batch.add_column(sa.Column("portmone_status", sa.String(length=32), nullable=True))
        if "portmone_error_code" not in columns:
            batch.add_column(sa.Column("portmone_error_code", sa.String(length=32), nullable=True))
        if "portmone_error_description" not in columns:
            batch.add_column(sa.Column("portmone_error_description", sa.String(length=255), nullable=True))
        if "callback_payload" not in columns:
            batch.add_column(sa.Column("callback_payload", sa.JSON(), nullable=True))
    
    # Update existing rows and remove server defaults
    try:
        op.execute("UPDATE bonus_transactions SET provider='portmone' WHERE provider IS NULL;")
        op.execute("UPDATE bonus_transactions SET currency='UAH' WHERE currency IS NULL;")
        
        # Remove server defaults
        with op.batch_alter_table("bonus_transactions") as batch:
            batch.alter_column("provider", server_default=None)
            batch.alter_column("currency", server_default=None)
    except Exception:
        pass  # Ignore errors for fresh databases


def downgrade() -> None:
    with op.batch_alter_table("bonus_transactions") as batch:
        batch.alter_column("payout_status", new_column_name="easypay_status")
        batch.alter_column("portmone_bill_id", new_column_name="easypay_reference")
        batch.drop_column("provider")
        batch.drop_column("currency")
        batch.drop_column("payee_id")
        batch.drop_column("contract_number")
        batch.drop_column("portmone_status")
        batch.drop_column("portmone_error_code")
        batch.drop_column("portmone_error_description")
        batch.drop_column("callback_payload")

