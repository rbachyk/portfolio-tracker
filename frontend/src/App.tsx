import {
  Activity,
  BarChart3,
  BriefcaseBusiness,
  Coins,
  Download,
  Gauge,
  LineChart as LineChartIcon,
  Lock,
  LogOut,
  RefreshCw,
  Settings as SettingsIcon,
  ShieldCheck,
  Target,
  Wallet
} from "lucide-react";
import { FormEvent, ReactNode, useEffect, useMemo, useState } from "react";

import {
  ApiClient,
  CashFlows,
  ChartPoint,
  EarnDashboard,
  Holding,
  LoginResponse,
  Lot,
  Overview,
  SettingsPayload,
  Snapshot,
  SyncJob
} from "./api";

type Page =
  | "overview"
  | "holdings"
  | "lots"
  | "earn"
  | "deposits"
  | "performance"
  | "settings"
  | "sync";

const pages: Array<{ id: Page; label: string; icon: ReactNode }> = [
  { id: "overview", label: "Overview", icon: <Gauge size={18} /> },
  { id: "holdings", label: "Holdings", icon: <BriefcaseBusiness size={18} /> },
  { id: "lots", label: "Lots", icon: <Coins size={18} /> },
  { id: "earn", label: "Earn", icon: <Wallet size={18} /> },
  { id: "deposits", label: "Deposits", icon: <Download size={18} /> },
  { id: "performance", label: "Performance", icon: <LineChartIcon size={18} /> },
  { id: "settings", label: "Settings", icon: <SettingsIcon size={18} /> },
  { id: "sync", label: "Sync Status", icon: <Activity size={18} /> }
];

export default function App() {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem("access_token"));
  const [username, setUsername] = useState<string | null>(() => localStorage.getItem("username"));
  const [page, setPage] = useState<Page>("overview");
  const [reloadKey, setReloadKey] = useState(0);
  const api = useMemo(() => new ApiClient(() => token), [token]);

  function handleLogin(response: LoginResponse) {
    localStorage.setItem("access_token", response.access_token);
    localStorage.setItem("username", response.username);
    setToken(response.access_token);
    setUsername(response.username);
  }

  function handleLogout() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("username");
    setToken(null);
    setUsername(null);
  }

  if (!token) {
    return <LoginView api={api} onLogin={handleLogin} />;
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <ShieldCheck size={24} />
          <div>
            <strong>Binance Spot</strong>
            <span>Portfolio Tracker</span>
          </div>
        </div>
        <nav className="nav-list">
          {pages.map((item) => (
            <button
              className={item.id === page ? "nav-item active" : "nav-item"}
              key={item.id}
              onClick={() => setPage(item.id)}
              type="button"
              title={item.label}
            >
              {item.icon}
              <span>{item.label}</span>
            </button>
          ))}
        </nav>
      </aside>
      <main className="workspace">
        <header className="topbar">
          <div>
            <span className="eyebrow">Authenticated as {username || "admin"}</span>
            <h1>{pages.find((item) => item.id === page)?.label}</h1>
          </div>
          <div className="topbar-actions">
            <button
              className="icon-button"
              onClick={() => setReloadKey((value) => value + 1)}
              title="Refresh data"
              type="button"
            >
              <RefreshCw size={18} />
            </button>
            <button className="icon-button" onClick={handleLogout} title="Log out" type="button">
              <LogOut size={18} />
            </button>
          </div>
        </header>
        <Content page={page} api={api} reloadKey={reloadKey} />
      </main>
    </div>
  );
}

function LoginView({ api, onLogin }: { api: ApiClient; onLogin: (response: LoginResponse) => void }) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);
    try {
      const response = await api.post<LoginResponse>("/auth/login", { username, password });
      onLogin(response);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="login-screen">
      <form className="login-panel" onSubmit={submit}>
        <div className="login-heading">
          <Lock size={26} />
          <div>
            <h1>Portfolio Login</h1>
            <p>Single-user access for the local dashboard.</p>
          </div>
        </div>
        <label>
          Username
          <input value={username} onChange={(event) => setUsername(event.target.value)} />
        </label>
        <label>
          Password
          <input
            autoComplete="current-password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>
        {error ? <div className="error">{error}</div> : null}
        <button className="primary-button" disabled={isSubmitting} type="submit">
          {isSubmitting ? "Signing in" : "Sign in"}
        </button>
      </form>
    </main>
  );
}

function Content({ page, api, reloadKey }: { page: Page; api: ApiClient; reloadKey: number }) {
  if (page === "overview") return <OverviewPage api={api} reloadKey={reloadKey} />;
  if (page === "holdings") return <HoldingsPage api={api} reloadKey={reloadKey} />;
  if (page === "lots") return <LotsPage api={api} reloadKey={reloadKey} />;
  if (page === "earn") return <EarnPage api={api} reloadKey={reloadKey} />;
  if (page === "deposits") return <DepositsPage api={api} reloadKey={reloadKey} />;
  if (page === "performance") return <PerformancePage api={api} reloadKey={reloadKey} />;
  if (page === "settings") return <SettingsPage api={api} reloadKey={reloadKey} />;
  return <SyncPage api={api} reloadKey={reloadKey} />;
}

function OverviewPage({ api, reloadKey }: PageProps) {
  const overview = useResource<Overview>(() => api.get("/portfolio/overview"), [api, reloadKey]);
  const holdings = useResource<{ holdings: Holding[] }>(
    () => api.get("/portfolio/holdings"),
    [api, reloadKey]
  );
  const equity = useResource<{ points: ChartPoint[] }>(
    () => api.get("/portfolio/performance/equity-curve?limit=180"),
    [api, reloadKey]
  );
  const earn = useResource<EarnDashboard>(() => api.get("/earn"), [api, reloadKey]);
  const deposits = useResource<CashFlows>(() => api.get("/deposits"), [api, reloadKey]);

  return (
    <DataState resource={overview}>
      {(data) => (
        <section className="page-stack">
          <div className="metric-grid">
            <MetricCard label="Total equity" value={money(data.total_equity)} />
            <MetricCard label="Deposited capital" value={money(data.total_deposited_capital)} />
            <MetricCard label="Total PnL" value={money(data.total_pnl)} tone={tone(data.total_pnl)} />
            <MetricCard label="Total PnL %" value={percent(data.total_pnl_pct)} tone={tone(data.total_pnl)} />
            <MetricCard label="24h change" value={money(data.change_24h)} tone={tone(data.change_24h)} />
            <MetricCard label="Earn rewards" value={money(data.earn_rewards_total_value)} />
            <MetricCard label="Assets" value={String(data.asset_count)} />
            <MetricCard label="Last sync" value={dateTime(data.last_sync_time)} />
          </div>
          <div className="dashboard-grid two">
            <Panel title="Total Equity Curve">
              <LineChart points={equity.data?.points || []} valueKey="total_equity" />
            </Panel>
            <Panel title="Allocation">
              <AllocationChart holdings={holdings.data?.holdings || []} />
            </Panel>
            <Panel title="PnL By Symbol">
              <BarChart
                points={(holdings.data?.holdings || []).map((item) => ({
                  label: item.asset_code,
                  value: Number(item.unrealized_pnl_including_rewards)
                }))}
              />
            </Panel>
            <Panel title="Earn Rewards Over Time">
              <LineChart points={earn.data?.rewards_over_time || []} valueKey="value" />
            </Panel>
            <Panel title="Deposits Over Time">
              <LineChart points={deposits.data?.deposits_over_time || []} valueKey="amount" />
            </Panel>
            <Panel title="Cost Basis vs Market Value">
              <GroupedBars holdings={holdings.data?.holdings || []} />
            </Panel>
          </div>
        </section>
      )}
    </DataState>
  );
}

function HoldingsPage({ api, reloadKey }: PageProps) {
  const resource = useResource<{ holdings: Holding[] }>(
    () => api.get("/portfolio/holdings"),
    [api, reloadKey]
  );
  return (
    <DataState resource={resource}>
      {(data) => (
        <Panel title="Holdings">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Asset</th>
                  <th>Total qty</th>
                  <th>Spot qty</th>
                  <th>Earn qty</th>
                  <th>Avg buy</th>
                  <th>Price</th>
                  <th>Cost basis</th>
                  <th>Market value</th>
                  <th>Unrealized PnL</th>
                  <th>Rewards</th>
                  <th>Allocation</th>
                  <th>Target</th>
                  <th>Diff</th>
                </tr>
              </thead>
              <tbody>
                {data.holdings.map((item) => (
                  <tr key={item.asset_code}>
                    <td className="asset-cell">{item.asset_code}</td>
                    <td>{quantity(item.total_quantity)}</td>
                    <td>{quantity(item.spot_quantity)}</td>
                    <td>{quantity(item.earn_quantity)}</td>
                    <td>{money(item.average_buy_price)}</td>
                    <td>{money(item.current_price)}</td>
                    <td>{money(item.cost_basis)}</td>
                    <td>{money(item.market_value)}</td>
                    <td className={tone(item.unrealized_pnl_including_rewards)}>
                      {money(item.unrealized_pnl_including_rewards)}
                      <span className="muted"> {percent(item.unrealized_pnl_pct)}</span>
                    </td>
                    <td>
                      {quantity(item.earn_rewards_quantity)}
                      <span className="muted"> / {money(item.earn_rewards_value)}</span>
                    </td>
                    <td>{percent(item.allocation_pct)}</td>
                    <td>{percent(item.target_pct)}</td>
                    <td className={tone(item.target_difference_pct)}>
                      {percent(item.target_difference_pct)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}
    </DataState>
  );
}

function LotsPage({ api, reloadKey }: PageProps) {
  const resource = useResource<{ lots: Lot[] }>(() => api.get("/lots"), [api, reloadKey]);
  return (
    <DataState resource={resource}>
      {(data) => (
        <Panel title="Buy Transactions And Open Lots">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Asset</th>
                  <th>Buy date</th>
                  <th>Bought</th>
                  <th>Remaining</th>
                  <th>Buy price</th>
                  <th>Current price</th>
                  <th>Cost basis</th>
                  <th>Current value</th>
                  <th>Unrealized PnL</th>
                  <th>Source trade</th>
                  <th>Fee</th>
                  <th>Mode</th>
                </tr>
              </thead>
              <tbody>
                {data.lots.map((item) => (
                  <tr key={item.id}>
                    <td className="asset-cell">{item.asset_code}</td>
                    <td>{dateTime(item.buy_date)}</td>
                    <td>{quantity(item.quantity_bought)}</td>
                    <td>{quantity(item.remaining_quantity)}</td>
                    <td>{money(item.buy_price)}</td>
                    <td>{money(item.current_price)}</td>
                    <td>{money(item.cost_basis)}</td>
                    <td>{money(item.current_value)}</td>
                    <td className={tone(item.unrealized_pnl)}>
                      {money(item.unrealized_pnl)}
                      <span className="muted"> {percent(item.unrealized_pnl_pct)}</span>
                    </td>
                    <td>{item.source_trade_id || item.source_type}</td>
                    <td>{item.fee ? `${quantity(item.fee.amount)} ${item.fee.asset_code}` : "None"}</td>
                    <td>{item.is_reward ? "Reward excluded toggle" : "Market movement"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}
    </DataState>
  );
}

function EarnPage({ api, reloadKey }: PageProps) {
  const resource = useResource<EarnDashboard>(() => api.get("/earn"), [api, reloadKey]);
  return (
    <DataState resource={resource}>
      {(data) => (
        <section className="page-stack">
          <div className="dashboard-grid two">
            <Panel title="Earn Positions">
              <SimpleTable
                columns={["Asset", "Product", "Amount", "Value", "Auto-subscribe"]}
                rows={data.positions.map((item) => [
                  item.asset_code,
                  item.product_type,
                  quantity(item.amount),
                  money(item.value),
                  item.auto_subscribe === null ? "Unknown" : item.auto_subscribe ? "On" : "Off"
                ])}
              />
            </Panel>
            <Panel title="Rewards By Asset">
              <SimpleTable
                columns={["Asset", "Quantity", "Value"]}
                rows={data.reward_totals.map((item) => [
                  item.asset_code,
                  quantity(item.quantity),
                  money(item.value)
                ])}
              />
            </Panel>
          </div>
          <Panel title="Earn Rewards Over Time">
            <LineChart points={data.rewards_over_time} valueKey="value" />
          </Panel>
          <Panel title="Recent Rewards">
            <SimpleTable
              columns={["Asset", "Product", "Type", "Amount", "Value", "Rewarded"]}
              rows={data.rewards.map((item) => [
                item.asset_code,
                item.product_type,
                item.reward_type || "Reward",
                quantity(item.amount),
                money(item.value),
                dateTime(item.rewarded_at)
              ])}
            />
          </Panel>
          <div className="dashboard-grid two">
            <Panel title="Subscriptions">
              <SimpleTable
                columns={["Asset", "Product", "Amount", "Subscribed"]}
                rows={data.subscriptions.map((item) => [
                  item.asset_code,
                  item.product_type,
                  quantity(item.amount),
                  dateTime(item.subscribed_at || null)
                ])}
              />
            </Panel>
            <Panel title="Redemptions">
              <SimpleTable
                columns={["Asset", "Product", "Amount", "Redeemed"]}
                rows={data.redemptions.map((item) => [
                  item.asset_code,
                  item.product_type,
                  quantity(item.amount),
                  dateTime(item.redeemed_at || null)
                ])}
              />
            </Panel>
          </div>
        </section>
      )}
    </DataState>
  );
}

function DepositsPage({ api, reloadKey }: PageProps) {
  const resource = useResource<CashFlows>(() => api.get("/deposits"), [api, reloadKey]);
  return (
    <DataState resource={resource}>
      {(data) => (
        <section className="page-stack">
          <Panel title="Deposits Over Time">
            <LineChart points={data.deposits_over_time} valueKey="amount" />
          </Panel>
          <div className="dashboard-grid two">
            <Panel title="Deposits">
              <SimpleTable
                columns={["Asset", "Amount", "Network", "Completed", "Tx"]}
                rows={data.deposits.map((item) => [
                  item.asset_code,
                  quantity(item.amount),
                  item.network || "Unknown",
                  dateTime(item.completed_at),
                  shortId(item.tx_id)
                ])}
              />
            </Panel>
            <Panel title="Withdrawals">
              <SimpleTable
                columns={["Asset", "Amount", "Fee", "Network", "Completed"]}
                rows={data.withdrawals.map((item) => [
                  item.asset_code,
                  quantity(item.amount),
                  quantity(item.transaction_fee),
                  item.network || "Unknown",
                  dateTime(item.completed_at)
                ])}
              />
            </Panel>
          </div>
        </section>
      )}
    </DataState>
  );
}

function PerformancePage({ api, reloadKey }: PageProps) {
  const snapshots = useResource<{ snapshots: Snapshot[] }>(
    () => api.get("/portfolio/snapshots?limit=365"),
    [api, reloadKey]
  );
  const equity = useResource<{ points: ChartPoint[] }>(
    () => api.get("/portfolio/performance/equity-curve?limit=365"),
    [api, reloadKey]
  );
  const drawdown = useResource<{ points: ChartPoint[] }>(
    () => api.get("/portfolio/performance/drawdown?limit=365"),
    [api, reloadKey]
  );

  return (
    <section className="page-stack">
      <div className="dashboard-grid two">
        <Panel title="Equity Curve">
          <LineChart points={equity.data?.points || []} valueKey="total_equity" />
        </Panel>
        <Panel title="Equity Excluding Deposits">
          <LineChart points={equity.data?.points || []} valueKey="equity_excluding_net_deposits" />
        </Panel>
        <Panel title="Drawdown Curve">
          <LineChart points={drawdown.data?.points || []} valueKey="drawdown" />
        </Panel>
        <Panel title="Portfolio Snapshots">
          <SimpleTable
            columns={["Snapshot", "Equity", "Cost basis", "Rewards", "Assets"]}
            rows={(snapshots.data?.snapshots || []).map((item) => [
              dateTime(item.snapshot_at),
              money(item.total_equity),
              money(item.total_cost_basis),
              money(item.earn_rewards_value),
              String(item.asset_count)
            ])}
          />
        </Panel>
      </div>
    </section>
  );
}

function SettingsPage({ api, reloadKey }: PageProps) {
  const resource = useResource<SettingsPayload>(() => api.get("/settings"), [api, reloadKey]);
  const manualAdjustments = useResource<{
    manual_adjustments: Array<{
      asset_code: string;
      quantity: string;
      quote_asset_code: string | null;
      quote_quantity: string;
      reason: string | null;
      adjusted_at: string;
    }>;
  }>(() => api.get("/manual-adjustments"), [api, reloadKey]);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function saveSettings(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setError(null);
    setSaveMessage(null);
    try {
      await api.patch("/settings", {
        portfolio_base_asset: String(form.get("portfolio_base_asset") || "USDT"),
        cost_basis_method: String(form.get("cost_basis_method") || "FIFO"),
        include_earn_rewards_in_pnl: form.get("include_earn_rewards_in_pnl") === "on",
        price_sync_interval_seconds: Number(form.get("price_sync_interval_seconds")),
        records_sync_interval_seconds: Number(form.get("records_sync_interval_seconds")),
        snapshot_interval_seconds: Number(form.get("snapshot_interval_seconds")),
        full_reconciliation_interval_seconds: Number(form.get("full_reconciliation_interval_seconds"))
      });
      setSaveMessage("Settings saved");
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }

  async function saveTarget(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setError(null);
    setSaveMessage(null);
    try {
      await api.post("/settings/target-allocations", {
        asset_code: String(form.get("asset_code") || ""),
        target_pct: Number(form.get("target_pct")) / 100,
        is_enabled: true
      });
      setSaveMessage("Target allocation saved");
      event.currentTarget.reset();
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }

  async function changePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setError(null);
    setSaveMessage(null);
    try {
      await api.post("/auth/change-password", {
        current_password: String(form.get("current_password") || ""),
        new_password: String(form.get("new_password") || "")
      });
      setSaveMessage("Password changed");
      event.currentTarget.reset();
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }

  async function createManualAdjustment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setError(null);
    setSaveMessage(null);
    try {
      await api.post("/manual-adjustments", {
        asset_code: String(form.get("manual_asset_code") || ""),
        quantity: String(form.get("manual_quantity") || "0"),
        quote_asset_code: String(form.get("manual_quote_asset_code") || "USDT"),
        quote_quantity: String(form.get("manual_quote_quantity") || "0"),
        reason: String(form.get("manual_reason") || "")
      });
      setSaveMessage("Manual adjustment saved. Run accounting refresh to rebuild lots.");
      event.currentTarget.reset();
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }

  return (
    <DataState resource={resource}>
      {(data) => (
        <section className="page-stack">
          <div className="status-strip">
            <span className={data.binance_api_configured ? "status-good" : "status-warn"}>
              Binance API {data.binance_api_configured ? "configured" : "not configured"}
            </span>
            <span>Cost basis: {String(data.settings.cost_basis_method || "FIFO")}</span>
            <span>Base: {String(data.settings.portfolio_base_asset || "USDT")}</span>
          </div>
          {error ? <div className="error">{error}</div> : null}
          {saveMessage ? <div className="success">{saveMessage}</div> : null}
          <div className="dashboard-grid two">
            <Panel title="Portfolio Settings">
              <form className="form-grid" onSubmit={saveSettings}>
                <label>
                  Base currency
                  <input
                    name="portfolio_base_asset"
                    defaultValue={String(data.settings.portfolio_base_asset || "USDT")}
                  />
                </label>
                <label>
                  Cost basis method
                  <select name="cost_basis_method" defaultValue={String(data.settings.cost_basis_method || "FIFO")}>
                    <option>FIFO</option>
                    <option disabled>LIFO</option>
                    <option disabled>HIFO</option>
                    <option disabled>AVERAGE</option>
                  </select>
                </label>
                <label className="check-row">
                  <input
                    name="include_earn_rewards_in_pnl"
                    type="checkbox"
                    defaultChecked={Boolean(data.settings.include_earn_rewards_in_pnl)}
                  />
                  Include Earn rewards in PnL by default
                </label>
                <label>
                  Price sync seconds
                  <input
                    min="60"
                    name="price_sync_interval_seconds"
                    type="number"
                    defaultValue={Number(data.settings.price_sync_interval_seconds || 300)}
                  />
                </label>
                <label>
                  Records sync seconds
                  <input
                    min="300"
                    name="records_sync_interval_seconds"
                    type="number"
                    defaultValue={Number(data.settings.records_sync_interval_seconds || 1800)}
                  />
                </label>
                <label>
                  Snapshot seconds
                  <input
                    min="300"
                    name="snapshot_interval_seconds"
                    type="number"
                    defaultValue={Number(data.settings.snapshot_interval_seconds || 3600)}
                  />
                </label>
                <label>
                  Full reconciliation seconds
                  <input
                    min="3600"
                    name="full_reconciliation_interval_seconds"
                    type="number"
                    defaultValue={Number(data.settings.full_reconciliation_interval_seconds || 86400)}
                  />
                </label>
                <button className="primary-button compact" type="submit">
                  Save settings
                </button>
              </form>
            </Panel>
            <Panel title="Password">
              <form className="form-grid" onSubmit={changePassword}>
                <label>
                  Current password
                  <input name="current_password" type="password" />
                </label>
                <label>
                  New password
                  <input minLength={12} name="new_password" type="password" />
                </label>
                <button className="primary-button compact" type="submit">
                  Change password
                </button>
              </form>
            </Panel>
          </div>
          <div className="dashboard-grid two">
            <Panel title="Target Allocations">
              <SimpleTable
                columns={["Asset", "Target", "Enabled"]}
                rows={data.target_allocations.map((item) => [
                  item.asset_code,
                  percent(item.target_pct),
                  item.is_enabled ? "Yes" : "No"
                ])}
              />
            </Panel>
            <Panel title="Add Target">
              <form className="form-grid" onSubmit={saveTarget}>
                <label>
                  Asset
                  <input name="asset_code" placeholder="BTC" />
                </label>
                <label>
                  Target %
                  <input name="target_pct" min="0" max="100" step="0.01" type="number" />
                </label>
                <button className="primary-button compact" type="submit">
                  Save target
                </button>
              </form>
            </Panel>
          </div>
          <div className="dashboard-grid two">
            <Panel title="Manual Asset Adjustment">
              <form className="form-grid" onSubmit={createManualAdjustment}>
                <label>
                  Asset
                  <input name="manual_asset_code" placeholder="BTC" />
                </label>
                <label>
                  Quantity
                  <input name="manual_quantity" step="any" type="number" />
                </label>
                <label>
                  Quote asset
                  <input name="manual_quote_asset_code" defaultValue="USDT" />
                </label>
                <label>
                  Quote quantity
                  <input name="manual_quote_quantity" step="any" type="number" defaultValue="0" />
                </label>
                <label>
                  Reason
                  <input name="manual_reason" placeholder="Opening balance correction" />
                </label>
                <button className="primary-button compact" type="submit">
                  Save adjustment
                </button>
              </form>
            </Panel>
            <Panel title="Recent Manual Adjustments">
              <SimpleTable
                columns={["Asset", "Quantity", "Quote", "Reason", "Adjusted"]}
                rows={(manualAdjustments.data?.manual_adjustments || []).map((item) => [
                  item.asset_code,
                  quantity(item.quantity),
                  `${compact(item.quote_quantity)} ${item.quote_asset_code || ""}`,
                  item.reason || "",
                  dateTime(item.adjusted_at)
                ])}
              />
            </Panel>
          </div>
        </section>
      )}
    </DataState>
  );
}

function SyncPage({ api, reloadKey }: PageProps) {
  const [runMessage, setRunMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const resource = useResource<{ jobs: SyncJob[] }>(() => api.get("/sync/status"), [api, reloadKey, runMessage]);
  const jobButtons = ["market_sync", "records_sync", "accounting_refresh", "full_reconciliation"];

  async function runJob(jobName: string) {
    setError(null);
    setRunMessage(null);
    try {
      await api.post("/sync/run", { job_name: jobName });
      setRunMessage(`${jobName} finished`);
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }

  return (
    <section className="page-stack">
      <Panel title="Run Sync">
        <div className="button-row">
          {jobButtons.map((jobName) => (
            <button className="secondary-button" key={jobName} onClick={() => runJob(jobName)} type="button">
              <RefreshCw size={16} />
              {jobName.replaceAll("_", " ")}
            </button>
          ))}
        </div>
        {error ? <div className="error">{error}</div> : null}
        {runMessage ? <div className="success">{runMessage}</div> : null}
      </Panel>
      <DataState resource={resource}>
        {(data) => (
          <Panel title="Sync Status">
            <SimpleTable
              columns={["Job", "Status", "Started", "Completed", "Error"]}
              rows={data.jobs.map((item) => [
                item.job_name,
                item.status,
                dateTime(item.last_started_at),
                dateTime(item.last_completed_at),
                item.error_message || ""
              ])}
            />
          </Panel>
        )}
      </DataState>
    </section>
  );
}

type PageProps = {
  api: ApiClient;
  reloadKey: number;
};

type Resource<T> = {
  data: T | null;
  error: string | null;
  isLoading: boolean;
};

function useResource<T>(load: () => Promise<T>, deps: unknown[]): Resource<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setError(null);
    load()
      .then((value) => {
        if (!cancelled) setData(value);
      })
      .catch((err) => {
        if (!cancelled) setError(apiErrorMessage(err));
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, deps);

  return { data, error, isLoading };
}

function DataState<T>({ resource, children }: { resource: Resource<T>; children: (data: T) => ReactNode }) {
  if (resource.isLoading) return <div className="loading">Loading</div>;
  if (resource.error) return <div className="error">{resource.error}</div>;
  if (!resource.data) return <div className="empty">No data</div>;
  return <>{children(resource.data)}</>;
}

function MetricCard({ label, value, tone: toneName }: { label: string; value: string; tone?: string }) {
  return (
    <div className="metric-card">
      <span>{label}</span>
      <strong className={toneName || ""}>{value}</strong>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="panel">
      <div className="panel-heading">
        <h2>{title}</h2>
      </div>
      {children}
    </section>
  );
}

function SimpleTable({ columns, rows }: { columns: string[]; rows: string[][] }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column}>{column}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td className="muted" colSpan={columns.length}>
                No records
              </td>
            </tr>
          ) : (
            rows.map((row, rowIndex) => (
              <tr key={`${row.join("|")}-${rowIndex}`}>
                {row.map((cell, cellIndex) => (
                  <td key={`${cell}-${cellIndex}`}>{cell}</td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

function LineChart({ points, valueKey }: { points: ChartPoint[]; valueKey: keyof ChartPoint }) {
  const values = points.map((point) => Number(point[valueKey] || 0));
  if (values.length === 0) return <div className="empty chart-empty">No chart data</div>;
  const width = 640;
  const height = 220;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const coordinates = values.map((value, index) => {
    const x = values.length === 1 ? width / 2 : (index / (values.length - 1)) * width;
    const y = height - ((value - min) / span) * (height - 24) - 12;
    return `${x},${y}`;
  });

  return (
    <svg className="chart" viewBox={`0 0 ${width} ${height}`} role="img">
      <polyline points={coordinates.join(" ")} fill="none" stroke="#2563eb" strokeWidth="3" />
      <line x1="0" y1={height - 12} x2={width} y2={height - 12} stroke="#d7dde8" />
      <text x="0" y="16" className="chart-label">
        {compact(max)}
      </text>
      <text x="0" y={height - 20} className="chart-label">
        {compact(min)}
      </text>
    </svg>
  );
}

function BarChart({ points }: { points: Array<{ label: string; value: number }> }) {
  if (points.length === 0) return <div className="empty chart-empty">No chart data</div>;
  const max = Math.max(...points.map((point) => Math.abs(point.value)), 1);
  return (
    <div className="bar-list">
      {points.slice(0, 12).map((point) => (
        <div className="bar-row" key={point.label}>
          <span>{point.label}</span>
          <div className="bar-track">
            <div
              className={point.value >= 0 ? "bar positive-bg" : "bar negative-bg"}
              style={{ width: `${Math.max((Math.abs(point.value) / max) * 100, 2)}%` }}
            />
          </div>
          <strong className={point.value >= 0 ? "positive" : "negative"}>{compact(point.value)}</strong>
        </div>
      ))}
    </div>
  );
}

function AllocationChart({ holdings }: { holdings: Holding[] }) {
  const visible = holdings.filter((item) => Number(item.market_value) > 0).slice(0, 10);
  if (visible.length === 0) return <div className="empty chart-empty">No allocation data</div>;
  return (
    <div className="allocation-list">
      {visible.map((item) => (
        <div className="allocation-row" key={item.asset_code}>
          <span>{item.asset_code}</span>
          <div className="bar-track">
            <div className="bar allocation-bg" style={{ width: `${Number(item.allocation_pct) * 100}%` }} />
          </div>
          <strong>{percent(item.allocation_pct)}</strong>
        </div>
      ))}
    </div>
  );
}

function GroupedBars({ holdings }: { holdings: Holding[] }) {
  const visible = holdings.slice(0, 10);
  if (visible.length === 0) return <div className="empty chart-empty">No holding data</div>;
  const max = Math.max(...visible.flatMap((item) => [Number(item.cost_basis), Number(item.market_value)]), 1);
  return (
    <div className="grouped-bars">
      {visible.map((item) => (
        <div className="grouped-row" key={item.asset_code}>
          <span>{item.asset_code}</span>
          <div className="dual-bars">
            <div className="mini-bar cost" style={{ width: `${(Number(item.cost_basis) / max) * 100}%` }} />
            <div className="mini-bar value" style={{ width: `${(Number(item.market_value) / max) * 100}%` }} />
          </div>
        </div>
      ))}
      <div className="legend">
        <span><i className="cost-dot" />Cost basis</span>
        <span><i className="value-dot" />Market value</span>
      </div>
    </div>
  );
}

function money(value: string | number | null | undefined) {
  if (value === null || value === undefined) return "N/A";
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "N/A";
  return `${compact(numeric)} USDT`;
}

function quantity(value: string | number | null | undefined) {
  if (value === null || value === undefined) return "0";
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "0";
  return numeric.toLocaleString(undefined, { maximumFractionDigits: 8 });
}

function percent(value: string | number | null | undefined) {
  if (value === null || value === undefined) return "N/A";
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "N/A";
  return `${(numeric * 100).toLocaleString(undefined, { maximumFractionDigits: 2 })}%`;
}

function compact(value: string | number | null | undefined) {
  if (value === null || value === undefined) return "N/A";
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "N/A";
  return numeric.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function dateTime(value: string | null | undefined) {
  if (!value) return "Never";
  return new Date(value).toLocaleString();
}

function shortId(value: string | null | undefined) {
  if (!value) return "";
  if (value.length <= 14) return value;
  return `${value.slice(0, 6)}...${value.slice(-6)}`;
}

function tone(value: string | number | null | undefined) {
  const numeric = Number(value || 0);
  if (numeric > 0) return "positive";
  if (numeric < 0) return "negative";
  return "";
}

function apiErrorMessage(err: unknown) {
  if (err && typeof err === "object" && "message" in err) {
    return String((err as { message: string }).message);
  }
  return "Request failed";
}
