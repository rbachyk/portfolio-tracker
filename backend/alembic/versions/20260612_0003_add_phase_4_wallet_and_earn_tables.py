"""add phase 4 wallet and earn tables

Revision ID: 20260612_0003
Revises: 20260612_0002
Create Date: 2026-06-12 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20260612_0003"
down_revision: str | None = "20260612_0002"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.create_table(
        "deposits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("raw_event_id", sa.Integer(), nullable=False),
        sa.Column("external_id", sa.String(length=256), nullable=False),
        sa.Column("asset_code", sa.String(length=32), nullable=False),
        sa.Column("amount", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("network", sa.String(length=64), nullable=True),
        sa.Column("status", sa.Integer(), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("address_tag", sa.String(length=256), nullable=True),
        sa.Column("tx_id", sa.String(length=512), nullable=True),
        sa.Column("transfer_type", sa.Integer(), nullable=True),
        sa.Column("wallet_type", sa.Integer(), nullable=True),
        sa.Column("inserted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["raw_event_id"], ["raw_binance_events.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
    )
    op.create_index(op.f("ix_deposits_asset_code"), "deposits", ["asset_code"])
    op.create_index(op.f("ix_deposits_completed_at"), "deposits", ["completed_at"])
    op.create_index(op.f("ix_deposits_external_id"), "deposits", ["external_id"])
    op.create_index(op.f("ix_deposits_inserted_at"), "deposits", ["inserted_at"])
    op.create_index(op.f("ix_deposits_network"), "deposits", ["network"])
    op.create_index(op.f("ix_deposits_status"), "deposits", ["status"])
    op.create_index(op.f("ix_deposits_tx_id"), "deposits", ["tx_id"])

    op.create_table(
        "withdrawals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("raw_event_id", sa.Integer(), nullable=False),
        sa.Column("external_id", sa.String(length=256), nullable=False),
        sa.Column("asset_code", sa.String(length=32), nullable=False),
        sa.Column("amount", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("transaction_fee", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("network", sa.String(length=64), nullable=True),
        sa.Column("status", sa.Integer(), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("tx_id", sa.String(length=512), nullable=True),
        sa.Column("withdraw_order_id", sa.String(length=256), nullable=True),
        sa.Column("transfer_type", sa.Integer(), nullable=True),
        sa.Column("wallet_type", sa.Integer(), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["raw_event_id"], ["raw_binance_events.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
    )
    op.create_index(op.f("ix_withdrawals_applied_at"), "withdrawals", ["applied_at"])
    op.create_index(op.f("ix_withdrawals_asset_code"), "withdrawals", ["asset_code"])
    op.create_index(op.f("ix_withdrawals_completed_at"), "withdrawals", ["completed_at"])
    op.create_index(op.f("ix_withdrawals_external_id"), "withdrawals", ["external_id"])
    op.create_index(op.f("ix_withdrawals_network"), "withdrawals", ["network"])
    op.create_index(op.f("ix_withdrawals_status"), "withdrawals", ["status"])
    op.create_index(op.f("ix_withdrawals_tx_id"), "withdrawals", ["tx_id"])
    op.create_index(
        op.f("ix_withdrawals_withdraw_order_id"), "withdrawals", ["withdraw_order_id"]
    )

    op.create_table(
        "earn_positions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("raw_event_id", sa.Integer(), nullable=False),
        sa.Column("external_id", sa.String(length=256), nullable=False),
        sa.Column("product_type", sa.String(length=32), nullable=False),
        sa.Column("product_id", sa.String(length=128), nullable=True),
        sa.Column("asset_code", sa.String(length=32), nullable=False),
        sa.Column("amount", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("auto_subscribe", sa.Boolean(), nullable=True),
        sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["raw_event_id"], ["raw_binance_events.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
    )
    op.create_index(op.f("ix_earn_positions_asset_code"), "earn_positions", ["asset_code"])
    op.create_index(op.f("ix_earn_positions_external_id"), "earn_positions", ["external_id"])
    op.create_index(op.f("ix_earn_positions_product_id"), "earn_positions", ["product_id"])
    op.create_index(op.f("ix_earn_positions_product_type"), "earn_positions", ["product_type"])

    _create_earn_history_table(
        "earn_subscriptions",
        id_column_name="purchase_id",
        time_column_name="subscribed_at",
    )
    _create_earn_history_table(
        "earn_redemptions",
        id_column_name="redeem_id",
        time_column_name="redeemed_at",
    )

    op.create_table(
        "earn_rewards",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("raw_event_id", sa.Integer(), nullable=False),
        sa.Column("external_id", sa.String(length=256), nullable=False),
        sa.Column("product_type", sa.String(length=32), nullable=False),
        sa.Column("product_id", sa.String(length=128), nullable=True),
        sa.Column("asset_code", sa.String(length=32), nullable=False),
        sa.Column("reward_type", sa.String(length=64), nullable=True),
        sa.Column("amount", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("cost_basis_mode", sa.String(length=32), nullable=False),
        sa.Column("source_endpoint", sa.String(length=128), nullable=False),
        sa.Column("rewarded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["raw_event_id"], ["raw_binance_events.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
    )
    op.create_index(op.f("ix_earn_rewards_asset_code"), "earn_rewards", ["asset_code"])
    op.create_index(op.f("ix_earn_rewards_external_id"), "earn_rewards", ["external_id"])
    op.create_index(op.f("ix_earn_rewards_product_id"), "earn_rewards", ["product_id"])
    op.create_index(op.f("ix_earn_rewards_product_type"), "earn_rewards", ["product_type"])
    op.create_index(op.f("ix_earn_rewards_reward_type"), "earn_rewards", ["reward_type"])
    op.create_index(op.f("ix_earn_rewards_rewarded_at"), "earn_rewards", ["rewarded_at"])


def downgrade() -> None:
    op.drop_index(op.f("ix_earn_rewards_rewarded_at"), table_name="earn_rewards")
    op.drop_index(op.f("ix_earn_rewards_reward_type"), table_name="earn_rewards")
    op.drop_index(op.f("ix_earn_rewards_product_type"), table_name="earn_rewards")
    op.drop_index(op.f("ix_earn_rewards_product_id"), table_name="earn_rewards")
    op.drop_index(op.f("ix_earn_rewards_external_id"), table_name="earn_rewards")
    op.drop_index(op.f("ix_earn_rewards_asset_code"), table_name="earn_rewards")
    op.drop_table("earn_rewards")
    _drop_earn_history_table(
        "earn_redemptions",
        id_column_name="redeem_id",
        time_column_name="redeemed_at",
    )
    _drop_earn_history_table(
        "earn_subscriptions",
        id_column_name="purchase_id",
        time_column_name="subscribed_at",
    )
    op.drop_index(op.f("ix_earn_positions_product_type"), table_name="earn_positions")
    op.drop_index(op.f("ix_earn_positions_product_id"), table_name="earn_positions")
    op.drop_index(op.f("ix_earn_positions_external_id"), table_name="earn_positions")
    op.drop_index(op.f("ix_earn_positions_asset_code"), table_name="earn_positions")
    op.drop_table("earn_positions")
    op.drop_index(op.f("ix_withdrawals_withdraw_order_id"), table_name="withdrawals")
    op.drop_index(op.f("ix_withdrawals_tx_id"), table_name="withdrawals")
    op.drop_index(op.f("ix_withdrawals_status"), table_name="withdrawals")
    op.drop_index(op.f("ix_withdrawals_network"), table_name="withdrawals")
    op.drop_index(op.f("ix_withdrawals_external_id"), table_name="withdrawals")
    op.drop_index(op.f("ix_withdrawals_completed_at"), table_name="withdrawals")
    op.drop_index(op.f("ix_withdrawals_asset_code"), table_name="withdrawals")
    op.drop_index(op.f("ix_withdrawals_applied_at"), table_name="withdrawals")
    op.drop_table("withdrawals")
    op.drop_index(op.f("ix_deposits_tx_id"), table_name="deposits")
    op.drop_index(op.f("ix_deposits_status"), table_name="deposits")
    op.drop_index(op.f("ix_deposits_network"), table_name="deposits")
    op.drop_index(op.f("ix_deposits_inserted_at"), table_name="deposits")
    op.drop_index(op.f("ix_deposits_external_id"), table_name="deposits")
    op.drop_index(op.f("ix_deposits_completed_at"), table_name="deposits")
    op.drop_index(op.f("ix_deposits_asset_code"), table_name="deposits")
    op.drop_table("deposits")


def _create_earn_history_table(
    table_name: str,
    *,
    id_column_name: str,
    time_column_name: str,
) -> None:
    op.create_table(
        table_name,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("raw_event_id", sa.Integer(), nullable=False),
        sa.Column("external_id", sa.String(length=256), nullable=False),
        sa.Column("product_type", sa.String(length=32), nullable=False),
        sa.Column(id_column_name, sa.String(length=128), nullable=True),
        sa.Column("product_id", sa.String(length=128), nullable=True),
        sa.Column("asset_code", sa.String(length=32), nullable=False),
        sa.Column("amount", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("source_endpoint", sa.String(length=128), nullable=False),
        sa.Column(time_column_name, sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["raw_event_id"], ["raw_binance_events.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
    )
    op.create_index(op.f(f"ix_{table_name}_asset_code"), table_name, ["asset_code"])
    op.create_index(op.f(f"ix_{table_name}_external_id"), table_name, ["external_id"])
    op.create_index(op.f(f"ix_{table_name}_{id_column_name}"), table_name, [id_column_name])
    op.create_index(op.f(f"ix_{table_name}_product_id"), table_name, ["product_id"])
    op.create_index(op.f(f"ix_{table_name}_product_type"), table_name, ["product_type"])
    op.create_index(op.f(f"ix_{table_name}_{time_column_name}"), table_name, [time_column_name])


def _drop_earn_history_table(
    table_name: str,
    *,
    id_column_name: str,
    time_column_name: str,
) -> None:
    op.drop_index(op.f(f"ix_{table_name}_{time_column_name}"), table_name=table_name)
    op.drop_index(op.f(f"ix_{table_name}_product_type"), table_name=table_name)
    op.drop_index(op.f(f"ix_{table_name}_product_id"), table_name=table_name)
    op.drop_index(op.f(f"ix_{table_name}_{id_column_name}"), table_name=table_name)
    op.drop_index(op.f(f"ix_{table_name}_external_id"), table_name=table_name)
    op.drop_index(op.f(f"ix_{table_name}_asset_code"), table_name=table_name)
    op.drop_table(table_name)
