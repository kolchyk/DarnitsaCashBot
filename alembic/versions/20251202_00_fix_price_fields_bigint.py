"""Fix price fields to use BIGINT instead of INTEGER

Revision ID: 20251202_00
Revises: 20251201_01
Create Date: 2025-12-02 08:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20251202_00"
down_revision = "20251201_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Change unit_price and total_price from INTEGER to BIGINT
    # This is needed because OCR can extract values that exceed int32 range
    with op.batch_alter_table("line_items") as batch:
        batch.alter_column("unit_price", type_=sa.BigInteger(), existing_type=sa.Integer())
        batch.alter_column("total_price", type_=sa.BigInteger(), existing_type=sa.Integer())


def downgrade() -> None:
    # Note: This downgrade may fail if there are values > int32 max
    # In practice, we should not downgrade this migration
    with op.batch_alter_table("line_items") as batch:
        batch.alter_column("unit_price", type_=sa.Integer(), existing_type=sa.BigInteger())
        batch.alter_column("total_price", type_=sa.Integer(), existing_type=sa.BigInteger())

