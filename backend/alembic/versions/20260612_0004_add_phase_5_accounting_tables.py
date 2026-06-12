"""add phase 5 accounting tables

Revision ID: 20260612_0004
Revises: 20260612_0003
Create Date: 2026-06-12 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20260612_0004"
down_revision: str | None = "20260612_0003"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.create_table(
        "ledger_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("external_id", sa.String(length=256), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("source_table", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=True),
        sa.Column("asset_code", sa.String(length=32), nullable=False),
        sa.Column("quote_asset_code", sa.String(length=32), nullable=True),
        sa.Column("quantity", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("quote_quantity", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=38, scale=18), nullable=True),
        sa.Column("fee_asset_code", sa.String(length=32), nullable=True),
        sa.Column("fee_amount", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
    )
    op.create_index(op.f("ix_ledger_events_asset_code"), "ledger_events", ["asset_code"])
    op.create_index(op.f("ix_ledger_events_event_time"), "ledger_events", ["event_time"])
    op.create_index(op.f("ix_ledger_events_event_type"), "ledger_events", ["event_type"])
    op.create_index(op.f("ix_ledger_events_external_id"), "ledger_events", ["external_id"])
    op.create_index(op.f("ix_ledger_events_fee_asset_code"), "ledger_events", ["fee_asset_code"])
    op.create_index(
        op.f("ix_ledger_events_quote_asset_code"), "ledger_events", ["quote_asset_code"]
    )
    op.create_index(op.f("ix_ledger_events_source_id"), "ledger_events", ["source_id"])
    op.create_index(op.f("ix_ledger_events_source_table"), "ledger_events", ["source_table"])
    op.create_index(op.f("ix_ledger_events_symbol"), "ledger_events", ["symbol"])

    op.create_table(
        "lots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_ledger_event_id", sa.Integer(), nullable=False),
        sa.Column("asset_code", sa.String(length=32), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=True),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("original_quantity", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("remaining_quantity", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("unit_cost", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("total_cost_basis", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("realized_pnl", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("is_reward", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["source_ledger_event_id"], ["ledger_events.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_lots_asset_code"), "lots", ["asset_code"])
    op.create_index(op.f("ix_lots_is_reward"), "lots", ["is_reward"])
    op.create_index(op.f("ix_lots_opened_at"), "lots", ["opened_at"])
    op.create_index(op.f("ix_lots_source_ledger_event_id"), "lots", ["source_ledger_event_id"])
    op.create_index(op.f("ix_lots_source_type"), "lots", ["source_type"])
    op.create_index(op.f("ix_lots_symbol"), "lots", ["symbol"])


def downgrade() -> None:
    op.drop_index(op.f("ix_lots_symbol"), table_name="lots")
    op.drop_index(op.f("ix_lots_source_type"), table_name="lots")
    op.drop_index(op.f("ix_lots_source_ledger_event_id"), table_name="lots")
    op.drop_index(op.f("ix_lots_opened_at"), table_name="lots")
    op.drop_index(op.f("ix_lots_is_reward"), table_name="lots")
    op.drop_index(op.f("ix_lots_asset_code"), table_name="lots")
    op.drop_table("lots")
    op.drop_index(op.f("ix_ledger_events_symbol"), table_name="ledger_events")
    op.drop_index(op.f("ix_ledger_events_source_table"), table_name="ledger_events")
    op.drop_index(op.f("ix_ledger_events_source_id"), table_name="ledger_events")
    op.drop_index(op.f("ix_ledger_events_quote_asset_code"), table_name="ledger_events")
    op.drop_index(op.f("ix_ledger_events_fee_asset_code"), table_name="ledger_events")
    op.drop_index(op.f("ix_ledger_events_external_id"), table_name="ledger_events")
    op.drop_index(op.f("ix_ledger_events_event_type"), table_name="ledger_events")
    op.drop_index(op.f("ix_ledger_events_event_time"), table_name="ledger_events")
    op.drop_index(op.f("ix_ledger_events_asset_code"), table_name="ledger_events")
    op.drop_table("ledger_events")
