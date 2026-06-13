export type ApiError = {
  status: number;
  message: string;
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api";

export class ApiClient {
  constructor(private readonly getToken: () => string | null) {}

  async get<T>(path: string): Promise<T> {
    return this.request<T>(path, { method: "GET" });
  }

  async post<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>(path, {
      method: "POST",
      body: body === undefined ? undefined : JSON.stringify(body)
    });
  }

  async patch<T>(path: string, body: unknown): Promise<T> {
    return this.request<T>(path, { method: "PATCH", body: JSON.stringify(body) });
  }

  async delete<T>(path: string): Promise<T> {
    return this.request<T>(path, { method: "DELETE" });
  }

  private async request<T>(path: string, init: RequestInit): Promise<T> {
    const token = this.getToken();
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...init.headers
      }
    });

    if (!response.ok) {
      let message = response.statusText;
      try {
        const payload = await response.json();
        message = typeof payload.detail === "string" ? payload.detail : JSON.stringify(payload.detail);
      } catch {
        message = response.statusText;
      }
      throw { status: response.status, message } satisfies ApiError;
    }

    if (response.status === 204) {
      return undefined as T;
    }
    return (await response.json()) as T;
  }
}

export type LoginResponse = {
  access_token: string;
  token_type: string;
  expires_at: string;
  username: string;
};

export type Overview = {
  snapshot: Snapshot | null;
  total_equity: string;
  total_deposited_capital: string;
  total_pnl: string;
  total_pnl_pct: string | null;
  change_24h: string | null;
  earn_rewards_total_value: string;
  asset_count: number;
  last_sync_time: string | null;
};

export type Snapshot = {
  id: number;
  base_asset: string;
  snapshot_at: string;
  total_equity: string;
  total_cost_basis: string;
  total_deposited: string;
  total_withdrawn: string;
  net_deposited: string;
  unrealized_pnl_including_rewards: string;
  unrealized_pnl_excluding_rewards: string;
  realized_pnl: string;
  earn_rewards_value: string;
  asset_count: number;
  holdings: Holding[];
};

export type Holding = {
  asset_code: string;
  total_quantity: string;
  spot_quantity: string;
  earn_quantity: string;
  accounting_quantity: string;
  average_buy_price: string | null;
  current_price: string | null;
  cost_basis: string;
  market_value: string;
  unrealized_pnl_including_rewards: string;
  unrealized_pnl_excluding_rewards: string;
  unrealized_pnl_pct: string | null;
  earn_rewards_quantity: string;
  earn_rewards_value: string;
  allocation_pct: string;
  target_pct: string | null;
  target_difference_pct: string | null;
};

export type Lot = {
  id: number;
  asset_code: string;
  symbol: string | null;
  buy_date: string;
  quantity_bought: string;
  remaining_quantity: string;
  buy_price: string;
  current_price: string | null;
  cost_basis: string;
  current_value: string | null;
  unrealized_pnl: string | null;
  unrealized_pnl_pct: string | null;
  realized_pnl: string;
  source_type: string;
  source_trade_id: string | null;
  fee: { asset_code: string; amount: string } | null;
  is_reward: boolean;
};

export type EarnDashboard = {
  positions: EarnPosition[];
  reward_totals: RewardTotal[];
  rewards_over_time: ChartPoint[];
  rewards: EarnReward[];
  subscriptions: EarnMovement[];
  redemptions: EarnMovement[];
};

export type EarnPosition = {
  asset_code: string;
  product_type: string;
  product_id: string | null;
  amount: string;
  auto_subscribe: boolean | null;
  value: string | null;
  snapshot_at: string;
};

export type RewardTotal = {
  asset_code: string;
  quantity: string;
  value: string;
};

export type EarnReward = {
  asset_code: string;
  product_type: string;
  reward_type: string | null;
  amount: string;
  value: string | null;
  rewarded_at: string | null;
  cost_basis_mode: string;
};

export type EarnMovement = {
  asset_code: string;
  product_type: string;
  product_id: string | null;
  amount: string;
  subscribed_at?: string | null;
  redeemed_at?: string | null;
};

export type CashFlows = {
  deposits: Deposit[];
  withdrawals: Withdrawal[];
  p2p_orders: P2POrder[];
  funding_transfers: FundingTransfer[];
  deposits_over_time: ChartPoint[];
};

export type Deposit = {
  asset_code: string;
  amount: string;
  network: string | null;
  status: number | null;
  tx_id: string | null;
  inserted_at: string | null;
  completed_at: string | null;
};

export type Withdrawal = Deposit & {
  transaction_fee: string;
  applied_at: string | null;
};

export type P2POrder = {
  order_number: string;
  trade_type: string;
  asset_code: string;
  fiat_code: string | null;
  amount: string;
  total_price: string;
  unit_price: string | null;
  commission: string;
  order_status: string | null;
  pay_method_name: string | null;
  order_created_at: string | null;
};

export type FundingTransfer = {
  tran_id: string;
  transfer_type: string;
  asset_code: string;
  amount: string;
  status: string | null;
  transferred_at: string | null;
};

export type ChartPoint = {
  date?: string;
  snapshot_at?: string;
  amount?: string;
  value?: string;
  total_equity?: string;
  net_deposited?: string;
  equity_excluding_net_deposits?: string;
  drawdown?: string;
  drawdown_pct?: string | null;
};

export type SyncJob = {
  job_name: string;
  status: string;
  last_started_at: string | null;
  last_completed_at: string | null;
  error_message: string | null;
  progress_current: number | null;
  progress_total: number | null;
  progress_message: string | null;
  updated_at: string;
};

export type SettingsPayload = {
  settings: Record<string, string | number | boolean>;
  target_allocations: Array<{ asset_code: string; target_pct: string; is_enabled: boolean }>;
  binance_api_configured: boolean;
};
