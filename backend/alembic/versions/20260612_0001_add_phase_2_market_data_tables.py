"""add phase 2 market data tables

Revision ID: 20260612_0001
Revises: 
Create Date: 2026-06-12 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20260612_0001"
down_revision: str | None = None
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(op.f("ix_assets_code"), "assets", ["code"], unique=False)

    op.create_table(
        "symbols",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("base_asset_code", sa.String(length=32), nullable=True),
        sa.Column("quote_asset_code", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("is_spot_trading_allowed", sa.Boolean(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["base_asset_code"], ["assets.code"]),
        sa.ForeignKeyConstraint(["quote_asset_code"], ["assets.code"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("symbol"),
    )
    op.create_index(
        op.f("ix_symbols_base_asset_code"), "symbols", ["base_asset_code"], unique=False
    )
    op.create_index(op.f("ix_symbols_is_enabled"), "symbols", ["is_enabled"], unique=False)
    op.create_index(
        op.f("ix_symbols_quote_asset_code"), "symbols", ["quote_asset_code"], unique=False
    )
    op.create_index(op.f("ix_symbols_status"), "symbols", ["status"], unique=False)
    op.create_index(op.f("ix_symbols_symbol"), "symbols", ["symbol"], unique=False)

    op.create_table(
        "sync_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_name", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("last_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_name"),
    )

    op.create_table(
        "price_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("symbol_id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("price", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["symbol_id"], ["symbols.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_price_snapshots_symbol_observed_at",
        "price_snapshots",
        ["symbol", "observed_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_price_snapshots_observed_at"), "price_snapshots", ["observed_at"], unique=False
    )
    op.create_index(op.f("ix_price_snapshots_symbol"), "price_snapshots", ["symbol"], unique=False)
    op.create_index(
        op.f("ix_price_snapshots_symbol_id"), "price_snapshots", ["symbol_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_price_snapshots_symbol_id"), table_name="price_snapshots")
    op.drop_index(op.f("ix_price_snapshots_symbol"), table_name="price_snapshots")
    op.drop_index(op.f("ix_price_snapshots_observed_at"), table_name="price_snapshots")
    op.drop_index("ix_price_snapshots_symbol_observed_at", table_name="price_snapshots")
    op.drop_table("price_snapshots")
    op.drop_table("sync_state")
    op.drop_index(op.f("ix_symbols_symbol"), table_name="symbols")
    op.drop_index(op.f("ix_symbols_status"), table_name="symbols")
    op.drop_index(op.f("ix_symbols_quote_asset_code"), table_name="symbols")
    op.drop_index(op.f("ix_symbols_is_enabled"), table_name="symbols")
    op.drop_index(op.f("ix_symbols_base_asset_code"), table_name="symbols")
    op.drop_table("symbols")
    op.drop_index(op.f("ix_assets_code"), table_name="assets")
    op.drop_table("assets")
