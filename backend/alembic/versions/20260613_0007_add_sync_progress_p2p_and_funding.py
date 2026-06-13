"""add sync progress p2p and funding records

Revision ID: 20260613_0007
Revises: 20260613_0006
Create Date: 2026-06-13 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20260613_0007"
down_revision: str | None = "20260613_0006"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column("sync_state", sa.Column("progress_current", sa.Integer(), nullable=True))
    op.add_column("sync_state", sa.Column("progress_total", sa.Integer(), nullable=True))
    op.add_column("sync_state", sa.Column("progress_message", sa.String(length=255), nullable=True))

    op.create_table(
        "p2p_orders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("raw_event_id", sa.Integer(), nullable=False),
        sa.Column("external_id", sa.String(length=256), nullable=False),
        sa.Column("order_number", sa.String(length=128), nullable=False),
        sa.Column("trade_type", sa.String(length=16), nullable=False),
        sa.Column("asset_code", sa.String(length=32), nullable=False),
        sa.Column("fiat_code", sa.String(length=16), nullable=True),
        sa.Column("amount", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("total_price", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=38, scale=18), nullable=True),
        sa.Column("commission", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("order_status", sa.String(length=64), nullable=True),
        sa.Column("pay_method_name", sa.String(length=128), nullable=True),
        sa.Column("order_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["raw_event_id"], ["raw_binance_events.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
        sa.UniqueConstraint("order_number"),
    )
    op.create_index(op.f("ix_p2p_orders_asset_code"), "p2p_orders", ["asset_code"])
    op.create_index(op.f("ix_p2p_orders_external_id"), "p2p_orders", ["external_id"])
    op.create_index(op.f("ix_p2p_orders_fiat_code"), "p2p_orders", ["fiat_code"])
    op.create_index(op.f("ix_p2p_orders_order_created_at"), "p2p_orders", ["order_created_at"])
    op.create_index(op.f("ix_p2p_orders_order_number"), "p2p_orders", ["order_number"])
    op.create_index(op.f("ix_p2p_orders_order_status"), "p2p_orders", ["order_status"])
    op.create_index(op.f("ix_p2p_orders_trade_type"), "p2p_orders", ["trade_type"])

    op.create_table(
        "funding_transfers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("raw_event_id", sa.Integer(), nullable=False),
        sa.Column("external_id", sa.String(length=256), nullable=False),
        sa.Column("tran_id", sa.BigInteger(), nullable=False),
        sa.Column("transfer_type", sa.String(length=64), nullable=False),
        sa.Column("asset_code", sa.String(length=32), nullable=False),
        sa.Column("amount", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=True),
        sa.Column("transferred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["raw_event_id"], ["raw_binance_events.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
    )
    op.create_index(op.f("ix_funding_transfers_asset_code"), "funding_transfers", ["asset_code"])
    op.create_index(op.f("ix_funding_transfers_external_id"), "funding_transfers", ["external_id"])
    op.create_index(op.f("ix_funding_transfers_status"), "funding_transfers", ["status"])
    op.create_index(op.f("ix_funding_transfers_tran_id"), "funding_transfers", ["tran_id"])
    op.create_index(
        op.f("ix_funding_transfers_transfer_type"),
        "funding_transfers",
        ["transfer_type"],
    )
    op.create_index(
        op.f("ix_funding_transfers_transferred_at"),
        "funding_transfers",
        ["transferred_at"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_funding_transfers_transferred_at"), table_name="funding_transfers")
    op.drop_index(op.f("ix_funding_transfers_transfer_type"), table_name="funding_transfers")
    op.drop_index(op.f("ix_funding_transfers_tran_id"), table_name="funding_transfers")
    op.drop_index(op.f("ix_funding_transfers_status"), table_name="funding_transfers")
    op.drop_index(op.f("ix_funding_transfers_external_id"), table_name="funding_transfers")
    op.drop_index(op.f("ix_funding_transfers_asset_code"), table_name="funding_transfers")
    op.drop_table("funding_transfers")
    op.drop_index(op.f("ix_p2p_orders_trade_type"), table_name="p2p_orders")
    op.drop_index(op.f("ix_p2p_orders_order_status"), table_name="p2p_orders")
    op.drop_index(op.f("ix_p2p_orders_order_number"), table_name="p2p_orders")
    op.drop_index(op.f("ix_p2p_orders_order_created_at"), table_name="p2p_orders")
    op.drop_index(op.f("ix_p2p_orders_fiat_code"), table_name="p2p_orders")
    op.drop_index(op.f("ix_p2p_orders_external_id"), table_name="p2p_orders")
    op.drop_index(op.f("ix_p2p_orders_asset_code"), table_name="p2p_orders")
    op.drop_table("p2p_orders")
    op.drop_column("sync_state", "progress_message")
    op.drop_column("sync_state", "progress_total")
    op.drop_column("sync_state", "progress_current")
