"""Initial schema for DarnitsaCashBot.

Revision ID: 20251201_00
Revises:
Create Date: 2025-12-01 15:45:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg


revision = "20251201_00"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("phone_number", sa.String(length=256), nullable=True),
        sa.Column("phone_hash", sa.String(length=128), nullable=True),
        sa.Column("locale", sa.String(length=5), nullable=False, server_default="uk"),
        sa.Column("consent_timestamp", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("uq_users_telegram_id", "users", ["telegram_id"], unique=True)
    op.create_index("ix_users_phone_hash", "users", ["phone_hash"], unique=False)

    op.create_table(
        "catalog_items",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
        sa.Column("sku_code", sa.String(length=64), nullable=False),
        sa.Column("product_aliases", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column(
            "active_flag",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.create_index("uq_catalog_items_sku_code", "catalog_items", ["sku_code"], unique=True)

    op.create_table(
        "receipts",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("upload_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("purchase_ts", sa.DateTime(timezone=True), nullable=True),
        sa.Column("merchant", sa.String(length=128), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("ocr_payload", sa.JSON(), nullable=True),
        sa.Column("storage_object_key", sa.String(length=256), nullable=False),
        sa.Column("checksum", sa.String(length=128), nullable=False),
    )
    op.create_index("ix_receipts_user_id", "receipts", ["user_id"], unique=False)

    op.create_table(
        "line_items",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("receipt_id", pg.UUID(as_uuid=True), sa.ForeignKey("receipts.id"), nullable=False),
        sa.Column("sku_code", sa.String(length=64), nullable=True),
        sa.Column("product_name", sa.String(length=256), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("unit_price", sa.Integer(), nullable=False),
        sa.Column("total_price", sa.Integer(), nullable=False),
        sa.Column(
            "confidence",
            sa.Float(),
            nullable=False,
            server_default="0",
        ),
    )
    op.create_index("ix_line_items_receipt_id", "line_items", ["receipt_id"], unique=False)

    op.create_table(
        "bonus_transactions",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
        sa.Column("receipt_id", pg.UUID(as_uuid=True), sa.ForeignKey("receipts.id"), nullable=False, unique=True),
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("msisdn", sa.String(length=32), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False, server_default="100"),
        sa.Column(
            "payout_status",
            sa.String(length=32),
            nullable=False,
            server_default="created",
        ),
        sa.Column(
            "provider",
            sa.String(length=32),
            nullable=False,
            server_default="portmone",
        ),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="UAH"),
        sa.Column("retries", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("payee_id", sa.String(length=64), nullable=True),
        sa.Column("contract_number", sa.String(length=64), nullable=True),
        sa.Column("portmone_bill_id", sa.String(length=64), nullable=True),
        sa.Column("portmone_status", sa.String(length=32), nullable=True),
        sa.Column("portmone_error_code", sa.String(length=32), nullable=True),
        sa.Column("portmone_error_description", sa.String(length=255), nullable=True),
        sa.Column("callback_payload", sa.JSON(), nullable=True),
    )
    op.create_index("ix_bonus_transactions_user_id", "bonus_transactions", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_bonus_transactions_user_id", table_name="bonus_transactions")
    op.drop_table("bonus_transactions")

    op.drop_index("ix_line_items_receipt_id", table_name="line_items")
    op.drop_table("line_items")

    op.drop_index("ix_receipts_user_id", table_name="receipts")
    op.drop_table("receipts")

    op.drop_index("uq_catalog_items_sku_code", table_name="catalog_items")
    op.drop_table("catalog_items")

    op.drop_index("ix_users_phone_hash", table_name="users")
    op.drop_index("uq_users_telegram_id", table_name="users")
    op.drop_table("users")

