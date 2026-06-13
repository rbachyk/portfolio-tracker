"""add phase 6 portfolio snapshots

Revision ID: 20260613_0005
Revises: 20260612_0004
Create Date: 2026-06-13 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20260613_0005"
down_revision: str | None = "20260612_0004"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.create_table(
        "portfolio_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("base_asset_code", sa.String(length=32), nullable=False),
        sa.Column("total_equity", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("total_cost_basis", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("total_deposited", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("total_withdrawn", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("net_deposited", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column(
            "unrealized_pnl_including_rewards",
            sa.Numeric(precision=38, scale=18),
            nullable=False,
        ),
        sa.Column(
            "unrealized_pnl_excluding_rewards",
            sa.Numeric(precision=38, scale=18),
            nullable=False,
        ),
        sa.Column("realized_pnl", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("earn_rewards_value", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("asset_count", sa.Integer(), nullable=False),
        sa.Column("holdings", sa.JSON(), nullable=False),
        sa.Column("missing_price_assets", sa.JSON(), nullable=True),
        sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_portfolio_snapshots_base_asset_code"),
        "portfolio_snapshots",
        ["base_asset_code"],
    )
    op.create_index(
        op.f("ix_portfolio_snapshots_snapshot_at"),
        "portfolio_snapshots",
        ["snapshot_at"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_portfolio_snapshots_snapshot_at"), table_name="portfolio_snapshots")
    op.drop_index(
        op.f("ix_portfolio_snapshots_base_asset_code"),
        table_name="portfolio_snapshots",
    )
    op.drop_table("portfolio_snapshots")
