"""add phase 3 trade sync tables

Revision ID: 20260612_0002
Revises: 20260612_0001
Create Date: 2026-06-12 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20260612_0002"
down_revision: str | None = "20260612_0001"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.create_table(
        "raw_binance_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("external_id", sa.String(length=256), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=True),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source",
            "external_id",
            name="uq_raw_binance_events_source_external_id",
        ),
    )
    op.create_index(op.f("ix_raw_binance_events_event_time"), "raw_binance_events", ["event_time"])
    op.create_index(op.f("ix_raw_binance_events_event_type"), "raw_binance_events", ["event_type"])
    op.create_index(
        op.f("ix_raw_binance_events_external_id"), "raw_binance_events", ["external_id"]
    )
    op.create_index(op.f("ix_raw_binance_events_source"), "raw_binance_events", ["source"])
    op.create_index(op.f("ix_raw_binance_events_symbol"), "raw_binance_events", ["symbol"])

    op.create_table(
        "trades",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("symbol_id", sa.Integer(), nullable=False),
        sa.Column("raw_event_id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("base_asset_code", sa.String(length=32), nullable=False),
        sa.Column("quote_asset_code", sa.String(length=32), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("binance_trade_id", sa.BigInteger(), nullable=False),
        sa.Column("binance_order_id", sa.BigInteger(), nullable=False),
        sa.Column("binance_order_list_id", sa.BigInteger(), nullable=True),
        sa.Column("price", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("quote_quantity", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("fee_asset_code", sa.String(length=32), nullable=True),
        sa.Column("fee_amount", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_buyer", sa.Boolean(), nullable=False),
        sa.Column("is_maker", sa.Boolean(), nullable=False),
        sa.Column("is_best_match", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["raw_event_id"], ["raw_binance_events.id"]),
        sa.ForeignKeyConstraint(["symbol_id"], ["symbols.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("symbol", "binance_trade_id", name="uq_trades_symbol_binance_trade_id"),
    )
    op.create_index(op.f("ix_trades_base_asset_code"), "trades", ["base_asset_code"])
    op.create_index(op.f("ix_trades_binance_order_id"), "trades", ["binance_order_id"])
    op.create_index(op.f("ix_trades_executed_at"), "trades", ["executed_at"])
    op.create_index(op.f("ix_trades_fee_asset_code"), "trades", ["fee_asset_code"])
    op.create_index(op.f("ix_trades_quote_asset_code"), "trades", ["quote_asset_code"])
    op.create_index(op.f("ix_trades_side"), "trades", ["side"])
    op.create_index(op.f("ix_trades_symbol"), "trades", ["symbol"])
    op.create_index(op.f("ix_trades_symbol_id"), "trades", ["symbol_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_trades_symbol_id"), table_name="trades")
    op.drop_index(op.f("ix_trades_symbol"), table_name="trades")
    op.drop_index(op.f("ix_trades_side"), table_name="trades")
    op.drop_index(op.f("ix_trades_quote_asset_code"), table_name="trades")
    op.drop_index(op.f("ix_trades_fee_asset_code"), table_name="trades")
    op.drop_index(op.f("ix_trades_executed_at"), table_name="trades")
    op.drop_index(op.f("ix_trades_binance_order_id"), table_name="trades")
    op.drop_index(op.f("ix_trades_base_asset_code"), table_name="trades")
    op.drop_table("trades")
    op.drop_index(op.f("ix_raw_binance_events_symbol"), table_name="raw_binance_events")
    op.drop_index(op.f("ix_raw_binance_events_source"), table_name="raw_binance_events")
    op.drop_index(op.f("ix_raw_binance_events_external_id"), table_name="raw_binance_events")
    op.drop_index(op.f("ix_raw_binance_events_event_type"), table_name="raw_binance_events")
    op.drop_index(op.f("ix_raw_binance_events_event_time"), table_name="raw_binance_events")
    op.drop_table("raw_binance_events")
