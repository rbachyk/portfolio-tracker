import {
  Activity,
  ArrowLeftRight,
  BadgeDollarSign,
  CandlestickChart,
  Coins,
  Gauge,
  Layers,
  LineChart as LineChartIcon,
  LogOut,
  Moon,
  PiggyBank,
  RefreshCw,
  Settings as SettingsIcon,
  Sun,
  TerminalSquare,
  Wallet,
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
  SyncJob,
} from "./api";
import { AreaChart, ASSET_PALETTE, CASH_COLOR, DivergingBars, DonutChart, DonutSlice, OTHERS_COLOR, SeriesPoint } from "./charts";
import {
  APP_NAME,
  CASH_ASSETS,
  fmtCompact,
  fmtDate,
  fmtDateTime,
  fmtMoney,
  fmtPct,
  fmtPrice,
  fmtQty,
  QUOTE_ASSET,
  relativeTime,
  shortId,
  Sign,
  signOf,
  titleCase,
  toNumber,
} from "./format";
import { useTheme } from "./theme";
import {
  Badge,
  Button,
  ChartSkeleton,
  Column,
  DataState,
  EmptyState,
  Panel,
  ProgressBar,
  Resource,
  SimpleTable,
  SkeletonStack,
  SortableTable,
  StatTile,
} from "./ui";

type Page =
  | "overview"
  | "holdings"
  | "lots"
  | "earn"
  | "deposits"
  | "performance"
  | "settings"
  | "sync";

type NavItem = { id: Page; label: string; icon: ReactNode };

const NAV: Array<{ section: string; items: NavItem[] }> = [
  {
    section: "Portfolio",
    items: [
      { id: "overview", label: "Overview", icon: <Gauge size={18} /> },
      { id: "holdings", label: "Holdings", icon: <Wallet size={18} /> },
      { id: "lots", label: "Lots", icon: <Layers size={18} /> },
    ],
  },
  {
    section: "Cash flow",
    items: [
      { id: "earn", label: "Earn", icon: <PiggyBank size={18} /> },
      { id: "deposits", label: "Transfers", icon: <ArrowLeftRight size={18} /> },
    ],
  },
  {
    section: "Analytics",
    items: [{ id: "performance", label: "Performance", icon: <LineChartIcon size={18} /> }],
  },
  {
    section: "System",
    items: [
      { id: "sync", label: "Sync", icon: <Activity size={18} /> },
      { id: "settings", label: "Settings", icon: <SettingsIcon size={18} /> },
    ],
  },
];

const PAGE_META: Record<Page, { title: string; subtitle: string }> = {
  overview: { title: "Overview", subtitle: "Your portfolio at a glance" },
  holdings: { title: "Holdings", subtitle: "Per-asset positions and allocation" },
  lots: { title: "Lots", subtitle: "Open buy lots and cost basis (FIFO)" },
  earn: { title: "Simple Earn", subtitle: "Earn positions and reward history" },
  deposits: { title: "Transfers", subtitle: "Deposits, withdrawals and funding" },
  performance: { title: "Performance", subtitle: "Equity, drawdown and snapshots" },
  settings: { title: "Settings", subtitle: "Accounting, targets and account" },
  sync: { title: "Sync", subtitle: "Background jobs and reconciliation" },
};

const ALL_NAV = NAV.flatMap((group) => group.items);

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

  const meta = PAGE_META[page];

  return (
    <div className="app-shell">
      <Sidebar page={page} onNavigate={setPage} username={username} onLogout={handleLogout} />
      <main className="workspace">
        <Topbar
          meta={meta}
          api={api}
          reloadKey={reloadKey}
          onRefresh={() => setReloadKey((value) => value + 1)}
        />
        <div className="page">
          <Content page={page} api={api} reloadKey={reloadKey} />
        </div>
      </main>
      <BottomNav page={page} onNavigate={setPage} />
    </div>
  );
}

function Sidebar({
  page,
  onNavigate,
  username,
  onLogout,
}: {
  page: Page;
  onNavigate: (page: Page) => void;
  username: string | null;
  onLogout: () => void;
}) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="brand-mark">
          <CandlestickChart size={20} />
        </span>
        <div className="brand-text">
          <strong>{APP_NAME}</strong>
          <span>Spot · Earn · PnL</span>
        </div>
      </div>
      <nav className="nav">
        {NAV.map((group) => (
          <div className="nav-group" key={group.section}>
            <span className="nav-section">{group.section}</span>
            {group.items.map((item) => (
              <button
                className={item.id === page ? "nav-item active" : "nav-item"}
                key={item.id}
                onClick={() => onNavigate(item.id)}
                type="button"
              >
                {item.icon}
                <span>{item.label}</span>
              </button>
            ))}
          </div>
        ))}
      </nav>
      <div className="sidebar-foot">
        <div className="account">
          <span className="account-avatar">{(username || "A").slice(0, 1).toUpperCase()}</span>
          <div className="account-text">
            <strong>{username || "admin"}</strong>
            <span>Single-user access</span>
          </div>
        </div>
        <Button variant="ghost" onClick={onLogout} title="Sign out">
          <LogOut size={16} />
          Sign out
        </Button>
      </div>
    </aside>
  );
}

function BottomNav({ page, onNavigate }: { page: Page; onNavigate: (page: Page) => void }) {
  return (
    <nav className="bottom-nav">
      {ALL_NAV.map((item) => (
        <button
          className={item.id === page ? "bottom-item active" : "bottom-item"}
          key={item.id}
          onClick={() => onNavigate(item.id)}
          type="button"
          title={item.label}
        >
          {item.icon}
          <span>{item.label}</span>
        </button>
      ))}
    </nav>
  );
}

function Topbar({
  meta,
  api,
  reloadKey,
  onRefresh,
}: {
  meta: { title: string; subtitle: string };
  api: ApiClient;
  reloadKey: number;
  onRefresh: () => void;
}) {
  const { theme, toggle } = useTheme();
  const sync = useSyncPulse(api, reloadKey);

  return (
    <header className="topbar">
      <div className="topbar-title">
        <h1>{meta.title}</h1>
        <p>{meta.subtitle}</p>
      </div>
      <div className="topbar-actions">
        <SyncIndicator sync={sync} />
        <Button variant="icon" onClick={toggle} title="Toggle theme">
          {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
        </Button>
        <Button variant="icon" onClick={onRefresh} title="Refresh data">
          <RefreshCw size={18} />
        </Button>
      </div>
    </header>
  );
}

type SyncPulse = { running: boolean; lastCompleted: string | null; loaded: boolean };

function useSyncPulse(api: ApiClient, reloadKey: number): SyncPulse {
  const [pulse, setPulse] = useState<SyncPulse>({ running: false, lastCompleted: null, loaded: false });
  const [tick, setTick] = useState(0);

  useEffect(() => {
    const id = window.setInterval(() => setTick((value) => value + 1), 12000);
    return () => window.clearInterval(id);
  }, []);

  useEffect(() => {
    let cancelled = false;
    api
      .get<{ jobs: SyncJob[] }>("/sync/status")
      .then((data) => {
        if (cancelled) return;
        const running = data.jobs.some((job) => job.status === "running");
        const lastCompleted = data.jobs
          .map((job) => job.last_completed_at)
          .filter((value): value is string => Boolean(value))
          .sort()
          .at(-1) ?? null;
        setPulse({ running, lastCompleted, loaded: true });
      })
      .catch(() => {
        if (!cancelled) setPulse((prev) => ({ ...prev, loaded: true }));
      });
    return () => {
      cancelled = true;
    };
  }, [api, reloadKey, tick]);

  return pulse;
}

function SyncIndicator({ sync }: { sync: SyncPulse }) {
  if (!sync.loaded) return null;
  if (sync.running) {
    return (
      <span className="sync-pill running" title="A sync job is running">
        <span className="pulse-dot" />
        Syncing…
      </span>
    );
  }
  return (
    <span className="sync-pill" title={`Last completed ${fmtDateTime(sync.lastCompleted)}`}>
      <span className="pulse-dot idle" />
      Synced {relativeTime(sync.lastCompleted)}
    </span>
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

// ---------------------------------------------------------------------------
// Login
// ---------------------------------------------------------------------------
function LoginView({ api, onLogin }: { api: ApiClient; onLogin: (response: LoginResponse) => void }) {
  const { theme, toggle } = useTheme();
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
      <Button variant="icon" className="login-theme" onClick={toggle} title="Toggle theme">
        {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
      </Button>
      <div className="login-grid">
        <section className="login-pitch">
          <span className="brand-mark large">
            <CandlestickChart size={24} />
          </span>
          <h1>{APP_NAME}</h1>
          <p>
            Ledger-grade accounting for your Binance Spot portfolio — FIFO cost basis, realized and
            unrealized PnL, Simple Earn rewards, and reconciled snapshots.
          </p>
          <ul className="login-points">
            <li>
              <BadgeDollarSign size={16} /> Cost basis you can audit, lot by lot
            </li>
            <li>
              <PiggyBank size={16} /> Earn rewards folded into PnL
            </li>
            <li>
              <TerminalSquare size={16} /> Self-hosted, single-user, read-only keys
            </li>
          </ul>
        </section>
        <form className="login-panel" onSubmit={submit}>
          <div className="login-heading">
            <h2>Sign in</h2>
            <p>Access your private dashboard.</p>
          </div>
          <label>
            Username
            <input value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" />
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
          {error ? (
            <div className="state-block error" role="alert">
              {error}
            </div>
          ) : null}
          <Button variant="primary" disabled={isSubmitting} type="submit" className="full">
            {isSubmitting ? "Signing in…" : "Sign in"}
          </Button>
        </form>
      </div>
    </main>
  );
}

// ---------------------------------------------------------------------------
// Overview
// ---------------------------------------------------------------------------
function OverviewPage({ api, reloadKey }: PageProps) {
  const overview = useResource<Overview>(() => api.get("/portfolio/overview"), [api, reloadKey]);
  const holdings = useResource<{ holdings: Holding[] }>(() => api.get("/portfolio/holdings"), [api, reloadKey]);
  const equity = useResource<{ points: ChartPoint[] }>(
    () => api.get("/portfolio/performance/equity-curve?limit=180"),
    [api, reloadKey],
  );
  const earn = useResource<EarnDashboard>(() => api.get("/earn"), [api, reloadKey]);
  const deposits = useResource<CashFlows>(() => api.get("/deposits"), [api, reloadKey]);

  return (
    <DataState resource={overview} skeleton={<OverviewSkeleton />}>
      {(data) => {
        const dayChange = toNumber(data.change_24h);
        const daySign = signOf(dayChange);
        const dayBase = (toNumber(data.total_equity) ?? 0) - (dayChange ?? 0);
        const dayPct = dayChange !== null && dayBase > 0 ? dayChange / dayBase : null;
        const equitySeries = toSeries(equity.data?.points, "total_equity");
        const heldHoldings = holdings.data?.holdings ?? [];
        const cashValue = heldHoldings
          .filter((item) => CASH_ASSETS.has(item.asset_code))
          .reduce((sum, item) => sum + (toNumber(item.market_value) ?? 0), 0);

        return (
          <div className="page-stack">
            <section className="hero">
              <div className="hero-main">
                <div className="hero-head">
                  <span className="eyebrow">Total equity</span>
                  {dayChange !== null ? (
                    <Badge tone={daySign === "neg" ? "neg" : daySign === "pos" ? "pos" : "neutral"}>
                      {daySign === "neg" ? "▼" : "▲"} {fmtMoney(dayChange, { signed: true })}
                      {dayPct !== null ? ` · ${fmtPct(dayPct, { signed: true })}` : ""} · 24h
                    </Badge>
                  ) : null}
                </div>
                <div className="hero-value-row">
                  <strong className="hero-value">{fmtMoney(data.total_equity)}</strong>
                  <span className="hero-unit">{QUOTE_ASSET}</span>
                </div>
                <div className="hero-substats">
                  <HeroStat label="Deposited capital" value={fmtMoney(data.total_deposited_capital)} />
                  <HeroStat
                    label="Total PnL"
                    value={fmtMoney(data.total_pnl, { signed: true })}
                    sign={signOf(data.total_pnl)}
                    sub={fmtPct(data.total_pnl_pct, { signed: true })}
                  />
                  <HeroStat label="Assets" value={String(data.asset_count)} />
                  <HeroStat label="Last sync" value={relativeTime(data.last_sync_time)} />
                </div>
              </div>
              <div className="hero-chart">
                {equity.isLoading ? (
                  <ChartSkeleton height={180} />
                ) : (
                  <AreaChart
                    data={equitySeries}
                    height={180}
                    color={daySign === "neg" ? "var(--neg)" : "var(--pos)"}
                    formatX={fmtDate}
                    formatY={(value) => `${fmtMoney(value)} ${QUOTE_ASSET}`}
                    emptyLabel="Equity curve appears after the first snapshot"
                  />
                )}
              </div>
            </section>

            <div className="tile-grid">
              <StatTile
                label="Unrealized PnL"
                value={fmtMoney(data.unrealized_pnl, { signed: true })}
                unit={QUOTE_ASSET}
                sign={signOf(data.unrealized_pnl)}
                delta={fmtPct(data.unrealized_pnl_pct, { signed: true })}
              />
              <StatTile
                label="Realized PnL"
                value={fmtMoney(data.realized_pnl, { signed: true })}
                unit={QUOTE_ASSET}
                sign={signOf(data.realized_pnl)}
                delta={fmtPct(data.realized_pnl_pct, { signed: true })}
              />
              <StatTile
                label="Earn rewards"
                value={fmtMoney(data.earn_rewards_total_value)}
                unit={QUOTE_ASSET}
                hint="Lifetime reward value"
              />
              <StatTile
                label="Cash (stables)"
                value={fmtMoney(cashValue)}
                unit={QUOTE_ASSET}
                hint={`${fmtPct(
                  (toNumber(data.total_equity) ?? 0) > 0 ? cashValue / (toNumber(data.total_equity) ?? 1) : 0,
                )} of equity`}
              />
            </div>

            <div className="grid-2">
              <Panel title="Allocation" subtitle="Including USDT & stablecoins">
                <DonutChart
                  slices={buildAllocation(heldHoldings, { excludeCash: false })}
                  centerLabel="Total"
                  formatValue={(value) => fmtCompact(value)}
                />
              </Panel>
              <Panel title="Allocation" subtitle="Excluding USDT & stablecoins">
                <DonutChart
                  slices={buildAllocation(heldHoldings, { excludeCash: true })}
                  centerLabel="Invested"
                  formatValue={(value) => fmtCompact(value)}
                />
              </Panel>
            </div>

            <div className="grid-2">
              <Panel title="Unrealized PnL by asset" subtitle="Sorted by PnL · incl. Earn rewards">
                <DivergingBars
                  data={heldHoldings
                    .map((item) => ({
                      label: item.asset_code,
                      value: toNumber(item.unrealized_pnl_including_rewards) ?? 0,
                    }))
                    .sort((a, b) => b.value - a.value)}
                />
              </Panel>
              <Panel title="Cost basis vs market value" subtitle="Sorted by market value">
                <CostVsValue holdings={heldHoldings} />
              </Panel>
            </div>

            <div className="grid-2">
              <Panel title="Earn rewards over time">
                {earn.isLoading ? (
                  <ChartSkeleton />
                ) : (
                  <AreaChart
                    data={toSeries(earn.data?.rewards_over_time, "value")}
                    color="var(--brand)"
                    formatX={fmtDate}
                    formatY={(value) => `${fmtMoney(value)} ${QUOTE_ASSET}`}
                    emptyLabel="No reward history yet"
                  />
                )}
              </Panel>
              <Panel title="Deposits over time">
                {deposits.isLoading ? (
                  <ChartSkeleton />
                ) : (
                  <AreaChart
                    data={toSeries(deposits.data?.deposits_over_time, "amount")}
                    color="var(--info)"
                    formatX={fmtDate}
                    formatY={(value) => `${fmtMoney(value)} ${QUOTE_ASSET}`}
                    emptyLabel="No deposits recorded"
                  />
                )}
              </Panel>
            </div>
          </div>
        );
      }}
    </DataState>
  );
}

function HeroStat({ label, value, sign, sub }: { label: string; value: string; sign?: Sign; sub?: string }) {
  return (
    <div className="hero-stat">
      <span>{label}</span>
      <strong className={sign ? `pnl-${sign}` : undefined}>
        {value}
        {sub ? <em className={sign ? `pnl-${sign}` : undefined}> {sub}</em> : null}
      </strong>
    </div>
  );
}

function CostVsValue({ holdings }: { holdings: Holding[] }) {
  const visible = holdings
    .filter((item) => toNumber(item.market_value))
    .sort((a, b) => (toNumber(b.market_value) ?? 0) - (toNumber(a.market_value) ?? 0));
  if (visible.length === 0) return <EmptyState message="No holdings to compare." />;
  const max = Math.max(
    ...visible.flatMap((item) => [toNumber(item.cost_basis) ?? 0, toNumber(item.market_value) ?? 0]),
    1,
  );
  return (
    <div className="cost-value">
      <div className="list-scroll">
        <div className="cost-value-rows">
          {visible.map((item) => {
            const cost = toNumber(item.cost_basis) ?? 0;
            const value = toNumber(item.market_value) ?? 0;
            return (
              <div className="cost-value-row" key={item.asset_code}>
                <span className="cost-value-asset">{item.asset_code}</span>
                <div className="cost-value-bars">
                  <span className="cv-bar cost" style={{ width: `${(cost / max) * 100}%` }} />
                  <span className="cv-bar value" style={{ width: `${(value / max) * 100}%` }} />
                </div>
                <strong className={`pnl-${signOf(value - cost)}`}>{fmtCompact(value - cost)}</strong>
              </div>
            );
          })}
        </div>
      </div>
      <div className="cv-legend">
        <span>
          <i className="cv-dot cost" /> Cost basis
        </span>
        <span>
          <i className="cv-dot value" /> Market value
        </span>
      </div>
    </div>
  );
}

function OverviewSkeleton() {
  return (
    <div className="page-stack">
      <div className="skeleton-hero" />
      <div className="tile-grid">
        {Array.from({ length: 4 }).map((_, index) => (
          <div className="skeleton-tile" key={index} />
        ))}
      </div>
      <div className="grid-2">
        <Panel title="Allocation">
          <ChartSkeleton height={200} />
        </Panel>
        <Panel title="Allocation">
          <ChartSkeleton height={200} />
        </Panel>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Holdings
// ---------------------------------------------------------------------------
function HoldingsPage({ api, reloadKey }: PageProps) {
  const resource = useResource<{ holdings: Holding[] }>(() => api.get("/portfolio/holdings"), [api, reloadKey]);
  return (
    <DataState resource={resource}>
      {(data) => {
        const totalValue = data.holdings.reduce((sum, item) => sum + (toNumber(item.market_value) ?? 0), 0);
        const totalCost = data.holdings.reduce((sum, item) => sum + (toNumber(item.cost_basis) ?? 0), 0);
        const totalPnl = data.holdings.reduce(
          (sum, item) => sum + (toNumber(item.unrealized_pnl_including_rewards) ?? 0),
          0,
        );
        return (
          <div className="page-stack">
            <div className="tile-grid">
              <StatTile label="Market value" value={fmtMoney(totalValue)} unit={QUOTE_ASSET} />
              <StatTile label="Cost basis" value={fmtMoney(totalCost)} unit={QUOTE_ASSET} />
              <StatTile
                label="Unrealized PnL"
                value={fmtMoney(totalPnl, { signed: true })}
                unit={QUOTE_ASSET}
                sign={signOf(totalPnl)}
                delta={fmtPct(totalCost > 0 ? totalPnl / totalCost : 0, { signed: true })}
              />
              <StatTile label="Assets" value={String(data.holdings.length)} />
            </div>
            <Panel title="Holdings" subtitle="Sorted by market value">
              <SortableTable
                caption={`Values in ${QUOTE_ASSET}`}
                columns={[
                  "Asset",
                  { label: "Total qty", align: "right" },
                  { label: "Avg buy", align: "right" },
                  { label: "Price", align: "right" },
                  { label: "Cost basis", align: "right" },
                  { label: "Value", align: "right" },
                  { label: "Unrealized PnL", align: "right" },
                  { label: "Rewards", align: "right" },
                  { label: "Allocation", align: "right" },
                  { label: "Target", align: "right" },
                ]}
                rows={data.holdings.map((item) => ({
                  key: item.asset_code,
                  cells: [
                    <AssetCell code={item.asset_code} spot={item.spot_quantity} earn={item.earn_quantity} />,
                    <span className="num">{fmtQty(item.total_quantity)}</span>,
                    <span className="num">{fmtPrice(item.average_buy_price)}</span>,
                    <span className="num">{fmtPrice(item.current_price)}</span>,
                    <span className="num">{fmtMoney(item.cost_basis)}</span>,
                    <span className="num strong">{fmtMoney(item.market_value)}</span>,
                    <PnlCell value={item.unrealized_pnl_including_rewards} pct={item.unrealized_pnl_pct} />,
                    <span className="num muted">{fmtMoney(item.earn_rewards_value)}</span>,
                    <AllocationCell pct={item.allocation_pct} />,
                    <TargetCell target={item.target_pct} diff={item.target_difference_pct} />,
                  ],
                  sortValues: [
                    item.asset_code,
                    toNumber(item.total_quantity),
                    toNumber(item.average_buy_price),
                    toNumber(item.current_price),
                    toNumber(item.cost_basis),
                    toNumber(item.market_value),
                    toNumber(item.unrealized_pnl_including_rewards),
                    toNumber(item.earn_rewards_value),
                    toNumber(item.allocation_pct),
                    toNumber(item.target_pct),
                  ],
                }))}
              />
            </Panel>
          </div>
        );
      }}
    </DataState>
  );
}

function AssetCell({ code, spot, earn }: { code: string; spot: string; earn: string }) {
  const earnQty = toNumber(earn) ?? 0;
  return (
    <div className="asset-cell">
      <span className="asset-badge" style={{ background: colorForAsset(code) }}>
        {code.slice(0, 3)}
      </span>
      <div className="asset-meta">
        <strong>{code}</strong>
        {earnQty > 0 ? <span className="muted">Spot {fmtQty(spot)} · Earn {fmtQty(earn)}</span> : null}
      </div>
    </div>
  );
}

function PnlCell({ value, pct }: { value: string | number | null; pct: string | number | null }) {
  const sign = signOf(value);
  return (
    <span className={`num pnl-${sign}`}>
      {fmtMoney(value, { signed: true })}
      <span className="pnl-pct"> {fmtPct(pct, { signed: true })}</span>
    </span>
  );
}

function AllocationCell({ pct }: { pct: string | number | null }) {
  const fraction = Math.min(Math.max(toNumber(pct) ?? 0, 0), 1);
  return (
    <div className="alloc-cell">
      <div className="alloc-track">
        <span style={{ width: `${fraction * 100}%` }} />
      </div>
      <span className="num">{fmtPct(pct)}</span>
    </div>
  );
}

function TargetCell({ target, diff }: { target: string | number | null; diff: string | number | null }) {
  if (toNumber(target) === null) return <span className="muted">—</span>;
  const sign = signOf(diff);
  return (
    <span className="num">
      {fmtPct(target)}
      <span className={`pnl-pct pnl-${sign}`}> {fmtPct(diff, { signed: true })}</span>
    </span>
  );
}

// ---------------------------------------------------------------------------
// Lots
// ---------------------------------------------------------------------------
function LotsPage({ api, reloadKey }: PageProps) {
  const resource = useResource<{ lots: Lot[] }>(() => api.get("/lots"), [api, reloadKey]);
  return (
    <DataState resource={resource}>
      {(data) => {
        const totalCost = data.lots.reduce((sum, lot) => sum + (toNumber(lot.cost_basis) ?? 0), 0);
        const totalPnl = data.lots.reduce((sum, lot) => sum + (toNumber(lot.unrealized_pnl) ?? 0), 0);
        return (
          <div className="page-stack">
            <div className="tile-grid">
              <StatTile label="Open lots" value={String(data.lots.length)} />
              <StatTile label="Cost basis" value={fmtMoney(totalCost)} unit={QUOTE_ASSET} />
              <StatTile
                label="Unrealized PnL"
                value={fmtMoney(totalPnl, { signed: true })}
                unit={QUOTE_ASSET}
                sign={signOf(totalPnl)}
              />
            </div>
            <Panel title="Open lots" subtitle="FIFO buy lots with remaining quantity">
              <SortableTable
                caption={`Values in ${QUOTE_ASSET}`}
                pageSize={25}
                columns={[
                  "Asset",
                  "Buy date",
                  { label: "Bought", align: "right" },
                  { label: "Remaining", align: "right" },
                  { label: "Buy price", align: "right" },
                  { label: "Price", align: "right" },
                  { label: "Cost basis", align: "right" },
                  { label: "Value", align: "right" },
                  { label: "Unrealized PnL", align: "right" },
                  "Source",
                ]}
                rows={data.lots.map((lot) => ({
                  key: String(lot.id),
                  cells: [
                    <span className="asset-tag">{lot.asset_code}</span>,
                    <span className="num">{fmtDate(lot.buy_date)}</span>,
                    <span className="num">{fmtQty(lot.quantity_bought)}</span>,
                    <span className="num">{fmtQty(lot.remaining_quantity)}</span>,
                    <span className="num">{fmtPrice(lot.buy_price)}</span>,
                    <span className="num">{fmtPrice(lot.current_price)}</span>,
                    <span className="num">{fmtMoney(lot.cost_basis)}</span>,
                    <span className="num">{fmtMoney(lot.current_value)}</span>,
                    <PnlCell value={lot.unrealized_pnl} pct={lot.unrealized_pnl_pct} />,
                    lot.is_reward ? <Badge tone="brand">Earn reward</Badge> : <Badge tone="neutral">Trade</Badge>,
                  ],
                  sortValues: [
                    lot.asset_code,
                    lot.buy_date,
                    toNumber(lot.quantity_bought),
                    toNumber(lot.remaining_quantity),
                    toNumber(lot.buy_price),
                    toNumber(lot.current_price),
                    toNumber(lot.cost_basis),
                    toNumber(lot.current_value),
                    toNumber(lot.unrealized_pnl),
                    lot.is_reward ? "Earn reward" : "Trade",
                  ],
                }))}
              />
            </Panel>
          </div>
        );
      }}
    </DataState>
  );
}

// ---------------------------------------------------------------------------
// Earn
// ---------------------------------------------------------------------------
function EarnPage({ api, reloadKey }: PageProps) {
  const resource = useResource<EarnDashboard>(() => api.get("/earn"), [api, reloadKey]);
  return (
    <DataState resource={resource}>
      {(data) => {
        const positionsValue = data.positions.reduce((sum, item) => sum + (toNumber(item.value) ?? 0), 0);
        const rewardsValue = data.reward_totals.reduce((sum, item) => sum + (toNumber(item.value) ?? 0), 0);
        return (
          <div className="page-stack">
            <div className="tile-grid">
              <StatTile label="Earn balance" value={fmtMoney(positionsValue)} unit={QUOTE_ASSET} />
              <StatTile label="Reward value" value={fmtMoney(rewardsValue)} unit={QUOTE_ASSET} hint="Lifetime" />
              <StatTile label="Positions" value={String(data.positions.length)} />
              <StatTile label="Reward events" value={String(data.rewards.length)} />
            </div>
            <Panel title="Earn rewards over time">
              <AreaChart
                data={toSeries(data.rewards_over_time, "value")}
                color="var(--brand)"
                formatX={fmtDate}
                formatY={(value) => `${fmtMoney(value)} ${QUOTE_ASSET}`}
                emptyLabel="No reward history yet"
              />
            </Panel>
            <div className="grid-2">
              <Panel title="Earn positions">
                <SimpleTable
                  caption={`Values in ${QUOTE_ASSET}`}
                  columns={["Asset", "Product", { label: "Amount", align: "right" }, { label: "Value", align: "right" }, "Auto"]}
                  rows={data.positions.map((item) => [
                    <span className="asset-tag">{item.asset_code}</span>,
                    titleCase(item.product_type),
                    <span className="num">{fmtQty(item.amount)}</span>,
                    <span className="num">{fmtMoney(item.value)}</span>,
                    item.auto_subscribe === null ? (
                      <Badge tone="neutral">Unknown</Badge>
                    ) : item.auto_subscribe ? (
                      <Badge tone="pos">On</Badge>
                    ) : (
                      <Badge tone="neutral">Off</Badge>
                    ),
                  ])}
                />
              </Panel>
              <Panel title="Rewards by asset">
                <SimpleTable
                  caption={`Values in ${QUOTE_ASSET}`}
                  columns={["Asset", { label: "Quantity", align: "right" }, { label: "Value", align: "right" }]}
                  rows={data.reward_totals.map((item) => [
                    <span className="asset-tag">{item.asset_code}</span>,
                    <span className="num">{fmtQty(item.quantity)}</span>,
                    <span className="num">{fmtMoney(item.value)}</span>,
                  ])}
                />
              </Panel>
            </div>
            <Panel title="Recent rewards">
              <SimpleTable
                caption={`Values in ${QUOTE_ASSET}`}
                pageSize={25}
                columns={["Asset", "Product", "Type", { label: "Amount", align: "right" }, { label: "Value", align: "right" }, "Rewarded"]}
                rows={data.rewards.map((item) => [
                  <span className="asset-tag">{item.asset_code}</span>,
                  titleCase(item.product_type),
                  item.reward_type ? titleCase(item.reward_type) : "Reward",
                  <span className="num">{fmtQty(item.amount)}</span>,
                  <span className="num">{fmtMoney(item.value)}</span>,
                  <span className="num">{fmtDateTime(item.rewarded_at)}</span>,
                ])}
              />
            </Panel>
            <div className="grid-2">
              <Panel title="Subscriptions">
                <SimpleTable
                  pageSize={15}
                  columns={["Asset", "Product", { label: "Amount", align: "right" }, "Date"]}
                  rows={data.subscriptions.map((item) => [
                    <span className="asset-tag">{item.asset_code}</span>,
                    titleCase(item.product_type),
                    <span className="num">{fmtQty(item.amount)}</span>,
                    <span className="num">{fmtDateTime(item.subscribed_at || null)}</span>,
                  ])}
                />
              </Panel>
              <Panel title="Redemptions">
                <SimpleTable
                  pageSize={15}
                  columns={["Asset", "Product", { label: "Amount", align: "right" }, "Date"]}
                  rows={data.redemptions.map((item) => [
                    <span className="asset-tag">{item.asset_code}</span>,
                    titleCase(item.product_type),
                    <span className="num">{fmtQty(item.amount)}</span>,
                    <span className="num">{fmtDateTime(item.redeemed_at || null)}</span>,
                  ])}
                />
              </Panel>
            </div>
          </div>
        );
      }}
    </DataState>
  );
}

// ---------------------------------------------------------------------------
// Deposits / transfers
// ---------------------------------------------------------------------------
function DepositsPage({ api, reloadKey }: PageProps) {
  const resource = useResource<CashFlows>(() => api.get("/deposits"), [api, reloadKey]);
  return (
    <DataState resource={resource}>
      {(data) => {
        const totalDeposited = data.deposits.reduce((sum, item) => sum + (toNumber(item.amount) ?? 0), 0);
        const totalWithdrawn = data.withdrawals.reduce((sum, item) => sum + (toNumber(item.amount) ?? 0), 0);
        return (
          <div className="page-stack">
            <div className="tile-grid">
              <StatTile label="Deposits" value={String(data.deposits.length)} hint="On-chain records" />
              <StatTile label="Withdrawals" value={String(data.withdrawals.length)} />
              <StatTile label="P2P orders" value={String(data.p2p_orders.length)} />
              <StatTile label="Transfers" value={String(data.funding_transfers.length)} />
            </div>
            <Panel title="Deposits over time">
              <AreaChart
                data={toSeries(data.deposits_over_time, "amount")}
                color="var(--info)"
                formatX={fmtDate}
                formatY={(value) => fmtCompact(value)}
                emptyLabel="No deposits recorded"
              />
            </Panel>
            <div className="grid-2">
              <Panel title="Deposits">
                <SimpleTable
                  pageSize={15}
                  columns={["Asset", { label: "Amount", align: "right" }, "Network", "Completed", "Tx"]}
                  rows={data.deposits.map((item) => [
                    <span className="asset-tag">{item.asset_code}</span>,
                    <span className="num">{fmtQty(item.amount)}</span>,
                    item.network || "—",
                    <span className="num">{fmtDateTime(item.completed_at)}</span>,
                    <span className="mono muted">{shortId(item.tx_id)}</span>,
                  ])}
                />
              </Panel>
              <Panel title="Withdrawals">
                <SimpleTable
                  pageSize={15}
                  columns={["Asset", { label: "Amount", align: "right" }, { label: "Fee", align: "right" }, "Network", "Completed"]}
                  rows={data.withdrawals.map((item) => [
                    <span className="asset-tag">{item.asset_code}</span>,
                    <span className="num">{fmtQty(item.amount)}</span>,
                    <span className="num muted">{fmtQty(item.transaction_fee)}</span>,
                    item.network || "—",
                    <span className="num">{fmtDateTime(item.completed_at)}</span>,
                  ])}
                />
              </Panel>
            </div>
            <div className="grid-2">
              <Panel title="P2P orders">
                <SimpleTable
                  pageSize={15}
                  columns={["Side", "Asset", { label: "Amount", align: "right" }, { label: "Fiat", align: "right" }, "Status", "Created"]}
                  rows={data.p2p_orders.map((item) => [
                    <Badge tone={item.trade_type?.toUpperCase() === "BUY" ? "pos" : "neg"}>{titleCase(item.trade_type)}</Badge>,
                    <span className="asset-tag">{item.asset_code}</span>,
                    <span className="num">{fmtQty(item.amount)}</span>,
                    <span className="num">{`${fmtCompact(item.total_price)} ${item.fiat_code || ""}`}</span>,
                    item.order_status ? titleCase(item.order_status) : "—",
                    <span className="num">{fmtDateTime(item.order_created_at)}</span>,
                  ])}
                />
              </Panel>
              <Panel title="Funding transfers">
                <SimpleTable
                  pageSize={15}
                  columns={["Type", "Asset", { label: "Amount", align: "right" }, "Status", "Date"]}
                  rows={data.funding_transfers.map((item) => [
                    titleCase(item.transfer_type),
                    <span className="asset-tag">{item.asset_code}</span>,
                    <span className="num">{fmtQty(item.amount)}</span>,
                    item.status ? titleCase(item.status) : "—",
                    <span className="num">{fmtDateTime(item.transferred_at)}</span>,
                  ])}
                />
              </Panel>
            </div>
            <p className="footnote">
              Deposited capital totals {fmtMoney(totalDeposited)} {QUOTE_ASSET}-equivalent in;{" "}
              {fmtMoney(totalWithdrawn)} out. Manual corrections live under Settings.
            </p>
          </div>
        );
      }}
    </DataState>
  );
}

// ---------------------------------------------------------------------------
// Performance
// ---------------------------------------------------------------------------
function PerformancePage({ api, reloadKey }: PageProps) {
  const snapshots = useResource<{ snapshots: Snapshot[] }>(() => api.get("/portfolio/snapshots?limit=365"), [api, reloadKey]);
  const equity = useResource<{ points: ChartPoint[] }>(
    () => api.get("/portfolio/performance/equity-curve?limit=365"),
    [api, reloadKey],
  );
  const drawdown = useResource<{ points: ChartPoint[] }>(
    () => api.get("/portfolio/performance/drawdown?limit=365"),
    [api, reloadKey],
  );

  const drawdownPoints = drawdown.data?.points ?? [];
  const currentDrawdown = drawdownPoints.at(-1)?.drawdown_pct ?? null;
  const maxDrawdown = drawdownPoints.reduce<number | null>((min, point) => {
    const value = toNumber(point.drawdown_pct);
    if (value === null) return min;
    return min === null ? value : Math.min(min, value);
  }, null);

  return (
    <div className="page-stack">
      <div className="tile-grid">
        <StatTile
          label="Current drawdown"
          value={fmtPct(currentDrawdown)}
          sign={signOf(currentDrawdown)}
        />
        <StatTile label="Max drawdown" value={fmtPct(maxDrawdown)} sign={signOf(maxDrawdown)} />
        <StatTile label="Snapshots" value={String(snapshots.data?.snapshots.length ?? 0)} />
      </div>
      <div className="grid-2">
        <Panel title="Equity curve">
          {equity.isLoading ? (
            <ChartSkeleton />
          ) : (
            <AreaChart
              data={toSeries(equity.data?.points, "total_equity")}
              color="var(--pos)"
              formatX={fmtDate}
              formatY={(value) => `${fmtMoney(value)} ${QUOTE_ASSET}`}
            />
          )}
        </Panel>
        <Panel title="Equity excluding net deposits" subtitle="Pure investment performance">
          {equity.isLoading ? (
            <ChartSkeleton />
          ) : (
            <AreaChart
              data={toSeries(equity.data?.points, "equity_excluding_net_deposits")}
              color="var(--brand)"
              formatX={fmtDate}
              formatY={(value) => `${fmtMoney(value)} ${QUOTE_ASSET}`}
            />
          )}
        </Panel>
      </div>
      <Panel title="Drawdown" subtitle="Decline from peak equity">
        {drawdown.isLoading ? (
          <ChartSkeleton />
        ) : (
          <AreaChart
            data={toSeries(drawdown.data?.points, "drawdown")}
            color="var(--neg)"
            formatX={fmtDate}
            formatY={(value) => fmtCompact(value)}
          />
        )}
      </Panel>
      <Panel title="Snapshots">
        <DataState resource={snapshots}>
          {(data) => (
            <SimpleTable
              caption={`Values in ${QUOTE_ASSET}`}
              pageSize={20}
              columns={[
                "Snapshot",
                { label: "Equity", align: "right" },
                { label: "Cost basis", align: "right" },
                { label: "Realized", align: "right" },
                { label: "Rewards", align: "right" },
                { label: "Assets", align: "right" },
              ]}
              rows={data.snapshots.map((item) => [
                <span className="num">{fmtDateTime(item.snapshot_at)}</span>,
                <span className="num strong">{fmtMoney(item.total_equity)}</span>,
                <span className="num">{fmtMoney(item.total_cost_basis)}</span>,
                <span className={`num pnl-${signOf(item.realized_pnl)}`}>{fmtMoney(item.realized_pnl, { signed: true })}</span>,
                <span className="num muted">{fmtMoney(item.earn_rewards_value)}</span>,
                <span className="num">{item.asset_count}</span>,
              ])}
            />
          )}
        </DataState>
      </Panel>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------
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
  const [showRefreshCta, setShowRefreshCta] = useState(false);

  function announce(message: string) {
    setError(null);
    setSaveMessage(message);
  }

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
        full_reconciliation_interval_seconds: Number(form.get("full_reconciliation_interval_seconds")),
      });
      announce("Settings saved.");
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
        asset_code: String(form.get("asset_code") || "").toUpperCase(),
        target_pct: Number(form.get("target_pct")) / 100,
        is_enabled: true,
      });
      announce("Target allocation saved.");
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
        new_password: String(form.get("new_password") || ""),
      });
      announce("Password changed.");
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
      const adjustedAt = String(form.get("manual_adjusted_at") || "");
      await api.post("/manual-adjustments", {
        asset_code: String(form.get("manual_asset_code") || "").toUpperCase(),
        quantity: String(form.get("manual_quantity") || "0"),
        quote_asset_code: String(form.get("manual_quote_asset_code") || "USDT").toUpperCase(),
        quote_quantity: String(form.get("manual_quote_quantity") || "0"),
        reason: String(form.get("manual_reason") || ""),
        adjusted_at: adjustedAt ? new Date(adjustedAt).toISOString() : null,
      });
      announce("Adjustment saved. Rebuild lots so it affects PnL.");
      setShowRefreshCta(true);
      event.currentTarget.reset();
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }

  async function runAccountingRefresh() {
    setError(null);
    try {
      await api.post("/sync/run", { job_name: "accounting_refresh" });
      announce("Accounting refresh started. Track it on the Sync page.");
      setShowRefreshCta(false);
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }

  return (
    <DataState resource={resource}>
      {(data) => (
        <div className="page-stack">
          <div className="status-strip">
            <Badge tone={data.binance_api_configured ? "pos" : "warn"}>
              Binance API {data.binance_api_configured ? "configured" : "not configured"}
            </Badge>
            <Badge tone="neutral">Cost basis · {String(data.settings.cost_basis_method || "FIFO")}</Badge>
            <Badge tone="neutral">Base · {String(data.settings.portfolio_base_asset || "USDT")}</Badge>
          </div>
          {error ? <div className="state-block error">{error}</div> : null}
          {saveMessage ? (
            <div className="state-block success">
              <span>{saveMessage}</span>
              {showRefreshCta ? (
                <Button variant="primary" onClick={runAccountingRefresh}>
                  <RefreshCw size={15} /> Rebuild lots now
                </Button>
              ) : null}
            </div>
          ) : null}

          <div className="grid-2">
            <Panel title="Portfolio settings" subtitle="Accounting and sync cadence">
              <form className="form-grid" onSubmit={saveSettings}>
                <Field label="Base currency">
                  <input name="portfolio_base_asset" defaultValue={String(data.settings.portfolio_base_asset || "USDT")} />
                </Field>
                <Field label="Cost basis method">
                  <select name="cost_basis_method" defaultValue={String(data.settings.cost_basis_method || "FIFO")}>
                    <option value="FIFO">FIFO</option>
                    <option disabled>LIFO (soon)</option>
                    <option disabled>HIFO (soon)</option>
                    <option disabled>Average (soon)</option>
                  </select>
                </Field>
                <label className="check-row">
                  <input
                    name="include_earn_rewards_in_pnl"
                    type="checkbox"
                    defaultChecked={Boolean(data.settings.include_earn_rewards_in_pnl)}
                  />
                  Include Earn rewards in PnL by default
                </label>
                <div className="field-pair">
                  <Field label="Price sync (s)">
                    <input min="60" name="price_sync_interval_seconds" type="number" defaultValue={Number(data.settings.price_sync_interval_seconds || 300)} />
                  </Field>
                  <Field label="Records sync (s)">
                    <input min="300" name="records_sync_interval_seconds" type="number" defaultValue={Number(data.settings.records_sync_interval_seconds || 1800)} />
                  </Field>
                </div>
                <div className="field-pair">
                  <Field label="Snapshot (s)">
                    <input min="300" name="snapshot_interval_seconds" type="number" defaultValue={Number(data.settings.snapshot_interval_seconds || 3600)} />
                  </Field>
                  <Field label="Reconciliation (s)">
                    <input min="3600" name="full_reconciliation_interval_seconds" type="number" defaultValue={Number(data.settings.full_reconciliation_interval_seconds || 86400)} />
                  </Field>
                </div>
                <Button variant="primary" type="submit">Save settings</Button>
              </form>
            </Panel>
            <Panel title="Security" subtitle="Change your dashboard password">
              <form className="form-grid" onSubmit={changePassword}>
                <Field label="Current password">
                  <input name="current_password" type="password" autoComplete="current-password" />
                </Field>
                <Field label="New password" hint="At least 12 characters">
                  <input minLength={12} name="new_password" type="password" autoComplete="new-password" />
                </Field>
                <Button variant="primary" type="submit">Change password</Button>
              </form>
            </Panel>
          </div>

          <div className="grid-2">
            <Panel title="Target allocations" subtitle="Drives the holdings drift column">
              <SimpleTable
                columns={["Asset", { label: "Target", align: "right" }, "Enabled"]}
                rows={data.target_allocations.map((item) => [
                  <span className="asset-tag">{item.asset_code}</span>,
                  <span className="num">{fmtPct(item.target_pct)}</span>,
                  item.is_enabled ? <Badge tone="pos">Yes</Badge> : <Badge tone="neutral">No</Badge>,
                ])}
              />
              <form className="inline-form" onSubmit={saveTarget}>
                <input name="asset_code" placeholder="BTC" aria-label="Asset" />
                <input name="target_pct" min="0" max="100" step="0.01" type="number" placeholder="Target %" aria-label="Target percent" />
                <Button variant="secondary" type="submit">Add</Button>
              </form>
            </Panel>
            <Panel title="Manual adjustment" subtitle="Backfill capital or correct balances">
              <form className="form-grid" onSubmit={createManualAdjustment}>
                <div className="field-pair">
                  <Field label="Asset">
                    <input name="manual_asset_code" placeholder="BTC" />
                  </Field>
                  <Field label="Quantity">
                    <input name="manual_quantity" step="any" type="number" placeholder="0.00" />
                  </Field>
                </div>
                <div className="field-pair">
                  <Field label="Quote asset">
                    <input name="manual_quote_asset_code" defaultValue="USDT" />
                  </Field>
                  <Field label="Quote quantity">
                    <input name="manual_quote_quantity" step="any" type="number" defaultValue="0" />
                  </Field>
                </div>
                <Field label="Reason">
                  <input name="manual_reason" placeholder="Older P2P capital correction" />
                </Field>
                <Field label="Adjusted at">
                  <input name="manual_adjusted_at" type="datetime-local" />
                </Field>
                <Button variant="primary" type="submit">Save adjustment</Button>
              </form>
            </Panel>
          </div>

          <Panel title="Recent manual adjustments">
            <SimpleTable
              pageSize={10}
              columns={["Asset", { label: "Quantity", align: "right" }, { label: "Quote", align: "right" }, "Reason", "Adjusted"]}
              rows={(manualAdjustments.data?.manual_adjustments || []).map((item) => [
                <span className="asset-tag">{item.asset_code}</span>,
                <span className="num">{fmtQty(item.quantity)}</span>,
                <span className="num">{`${fmtCompact(item.quote_quantity)} ${item.quote_asset_code || ""}`}</span>,
                item.reason || "—",
                <span className="num">{fmtDateTime(item.adjusted_at)}</span>,
              ])}
            />
          </Panel>
        </div>
      )}
    </DataState>
  );
}

function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
      {hint ? <span className="field-hint">{hint}</span> : null}
    </label>
  );
}

// ---------------------------------------------------------------------------
// Sync
// ---------------------------------------------------------------------------
const SYNC_JOBS: Array<{ id: string; label: string; description: string }> = [
  { id: "market_sync", label: "Market sync", description: "Prices & exchange info" },
  { id: "records_sync", label: "Records sync", description: "Trades, deposits, Earn" },
  { id: "accounting_refresh", label: "Accounting refresh", description: "Rebuild lots & PnL" },
  { id: "full_reconciliation", label: "Full reconciliation", description: "Everything, from scratch" },
];

function SyncPage({ api, reloadKey }: PageProps) {
  const [runMessage, setRunMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const resource = useResource<{ jobs: SyncJob[] }>(() => api.get("/sync/status"), [api, reloadKey, runMessage, tick]);

  const jobs = resource.data?.jobs ?? [];
  const anyRunning = jobs.some((job) => job.status === "running");

  useEffect(() => {
    if (!anyRunning) return;
    const id = window.setInterval(() => setTick((value) => value + 1), 5000);
    return () => window.clearInterval(id);
  }, [anyRunning]);

  async function runJob(jobName: string) {
    setError(null);
    setRunMessage(null);
    try {
      await api.post("/sync/run", { job_name: jobName });
      setRunMessage(`${titleCase(jobName)} started.`);
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }

  function jobStatus(id: string): SyncJob | undefined {
    return jobs.find((job) => job.job_name === id);
  }

  return (
    <div className="page-stack">
      <div className="job-grid">
        {SYNC_JOBS.map((job) => {
          const status = jobStatus(job.id);
          const running = status?.status === "running";
          return (
            <div className="job-card" key={job.id}>
              <div className="job-card-head">
                <strong>{job.label}</strong>
                <SyncStatusBadge status={status?.status} />
              </div>
              <p>{job.description}</p>
              <Button variant={running ? "secondary" : "primary"} disabled={running} onClick={() => runJob(job.id)}>
                <RefreshCw size={15} className={running ? "spin" : undefined} />
                {running ? "Running…" : "Run"}
              </Button>
            </div>
          );
        })}
      </div>
      {error ? <div className="state-block error">{error}</div> : null}
      {runMessage ? <div className="state-block success">{runMessage}</div> : null}
      <Panel title="Job status" subtitle={anyRunning ? "Auto-refreshing every 5s" : "Background sync jobs"}>
        <DataState resource={resource}>
          {(data) => (
            <SimpleTable
              columns={["Job", "Status", "Progress", "Started", "Completed", "Detail"]}
              rows={data.jobs.map((item) => [
                titleCase(item.job_name),
                <SyncStatusBadge status={item.status} />,
                syncProgress(item),
                <span className="num">{fmtDateTime(item.last_started_at)}</span>,
                <span className="num">{fmtDateTime(item.last_completed_at)}</span>,
                <span className="muted">{item.error_message || item.progress_message || "—"}</span>,
              ])}
            />
          )}
        </DataState>
      </Panel>
    </div>
  );
}

function SyncStatusBadge({ status }: { status?: string }) {
  if (status === "running") return <Badge tone="info">Running</Badge>;
  if (status === "success") return <Badge tone="pos">Success</Badge>;
  if (status === "error" || status === "failed") return <Badge tone="neg">Failed</Badge>;
  return <Badge tone="neutral">{status ? titleCase(status) : "Idle"}</Badge>;
}

function syncProgress(job: SyncJob): ReactNode {
  if (job.progress_total === null || job.progress_total === undefined) {
    return <span className="muted">—</span>;
  }
  if (job.progress_total === 0) {
    return <span className="muted">{job.progress_message || "0 / 0"}</span>;
  }
  return <ProgressBar value={job.progress_current || 0} max={job.progress_total} />;
}

// ---------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------
type PageProps = { api: ApiClient; reloadKey: number };

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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, error, isLoading };
}

function xOf(point: ChartPoint): string {
  return point.date || point.snapshot_at || "";
}

function toSeries(points: ChartPoint[] | undefined, valueKey: keyof ChartPoint): SeriesPoint[] {
  if (!points) return [];
  return points.map((point) => ({ x: xOf(point), y: toNumber(point[valueKey] as string) ?? 0 }));
}

function colorForAsset(code: string): string {
  if (CASH_ASSETS.has(code)) return CASH_COLOR;
  let hash = 0;
  for (let i = 0; i < code.length; i += 1) hash = (hash * 31 + code.charCodeAt(i)) >>> 0;
  return ASSET_PALETTE[hash % ASSET_PALETTE.length];
}

function buildAllocation(holdings: Holding[], { excludeCash }: { excludeCash: boolean }): DonutSlice[] {
  const filtered = holdings
    .filter((item) => (toNumber(item.market_value) ?? 0) > 0)
    .filter((item) => (excludeCash ? !CASH_ASSETS.has(item.asset_code) : true))
    .sort((a, b) => (toNumber(b.market_value) ?? 0) - (toNumber(a.market_value) ?? 0));

  const top = filtered.slice(0, 8);
  const rest = filtered.slice(8);
  const slices: DonutSlice[] = top.map((item) => ({
    label: item.asset_code,
    value: toNumber(item.market_value) ?? 0,
    color: colorForAsset(item.asset_code),
  }));
  if (rest.length > 0) {
    slices.push({
      label: `+${rest.length} others`,
      value: rest.reduce((sum, item) => sum + (toNumber(item.market_value) ?? 0), 0),
      color: OTHERS_COLOR,
    });
  }
  return slices;
}

function apiErrorMessage(err: unknown): string {
  if (err && typeof err === "object" && "message" in err) {
    return String((err as { message: string }).message);
  }
  return "Request failed";
}
