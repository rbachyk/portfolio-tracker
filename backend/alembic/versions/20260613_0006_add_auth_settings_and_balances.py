"""add auth settings and balance tables

Revision ID: 20260613_0006
Revises: 20260613_0005
Create Date: 2026-06-13 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20260613_0006"
down_revision: str | None = "20260613_0005"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=128), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )
    op.create_index(op.f("ix_users_username"), "users", ["username"])

    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("value", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_index(op.f("ix_settings_key"), "settings", ["key"])

    op.create_table(
        "target_allocations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("asset_code", sa.String(length=32), nullable=False),
        sa.Column("target_pct", sa.Numeric(precision=18, scale=10), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asset_code"),
    )
    op.create_index(op.f("ix_target_allocations_asset_code"), "target_allocations", ["asset_code"])
    op.create_index(op.f("ix_target_allocations_is_enabled"), "target_allocations", ["is_enabled"])

    op.create_table(
        "spot_balances",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("raw_event_id", sa.Integer(), nullable=True),
        sa.Column("asset_code", sa.String(length=32), nullable=False),
        sa.Column("free", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("locked", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("total", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["raw_event_id"], ["raw_binance_events.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asset_code"),
    )
    op.create_index(op.f("ix_spot_balances_asset_code"), "spot_balances", ["asset_code"])
    op.create_index(op.f("ix_spot_balances_snapshot_at"), "spot_balances", ["snapshot_at"])

    op.create_table(
        "manual_adjustments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("external_id", sa.String(length=256), nullable=False),
        sa.Column("asset_code", sa.String(length=32), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=True),
        sa.Column("quote_asset_code", sa.String(length=32), nullable=True),
        sa.Column("quantity", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("quote_quantity", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=38, scale=18), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("adjusted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
    )
    op.create_index(
        op.f("ix_manual_adjustments_external_id"),
        "manual_adjustments",
        ["external_id"],
    )
    op.create_index(op.f("ix_manual_adjustments_asset_code"), "manual_adjustments", ["asset_code"])
    op.create_index(op.f("ix_manual_adjustments_symbol"), "manual_adjustments", ["symbol"])
    op.create_index(
        op.f("ix_manual_adjustments_quote_asset_code"),
        "manual_adjustments",
        ["quote_asset_code"],
    )
    op.create_index(
        op.f("ix_manual_adjustments_adjusted_at"),
        "manual_adjustments",
        ["adjusted_at"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_manual_adjustments_adjusted_at"), table_name="manual_adjustments")
    op.drop_index(op.f("ix_manual_adjustments_quote_asset_code"), table_name="manual_adjustments")
    op.drop_index(op.f("ix_manual_adjustments_symbol"), table_name="manual_adjustments")
    op.drop_index(op.f("ix_manual_adjustments_asset_code"), table_name="manual_adjustments")
    op.drop_index(op.f("ix_manual_adjustments_external_id"), table_name="manual_adjustments")
    op.drop_table("manual_adjustments")
    op.drop_index(op.f("ix_spot_balances_snapshot_at"), table_name="spot_balances")
    op.drop_index(op.f("ix_spot_balances_asset_code"), table_name="spot_balances")
    op.drop_table("spot_balances")
    op.drop_index(op.f("ix_target_allocations_is_enabled"), table_name="target_allocations")
    op.drop_index(op.f("ix_target_allocations_asset_code"), table_name="target_allocations")
    op.drop_table("target_allocations")
    op.drop_index(op.f("ix_settings_key"), table_name="settings")
    op.drop_table("settings")
    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_table("users")
