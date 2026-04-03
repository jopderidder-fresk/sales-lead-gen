import { useDashboard } from "@/lib/dashboard";
import { useCompanies } from "@/lib/companies";
import { useSignalsByType } from "@/lib/analytics";
import { useUsageLimits } from "@/lib/settings";
import { useDiscoveryJobs } from "@/lib/discovery";
import { useAuth } from "@/context/auth";
import { cn } from "@/lib/utils";
import {
  SignalTypeBadge,
  ScoreBadge,
  LeadScoreBadge,
  StatusBadge,
} from "@/components/badges";
import type { CompanyStatus } from "@/types/api";
import {
  ArrowRight,
  BarChart3,
  Building2,
  Compass,
  Flame,
  Radio,
  Sun,
  Target,
  Users,
  Zap,
} from "lucide-react";
import { Link } from "react-router-dom";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
} from "recharts";

// ── Constants ────────────────────────────────────────────────────

const STAGE_LABELS: Record<Exclude<CompanyStatus, "archived">, string> = {
  discovered: "Discovered",
  enriched: "Enriched",
  monitoring: "Monitoring",
  qualified: "Qualified",
  pushed: "Pushed",
};

const STAGE_COLORS: Record<Exclude<CompanyStatus, "archived">, string> = {
  discovered: "#6B8AE0",
  enriched: "#A080D0",
  monitoring: "#4DBCD0",
  qualified: "#5DC090",
  pushed: "#3DAD80",
};

const SIGNAL_TYPE_COLORS: Record<string, string> = {
  hiring_surge: "#3b82f6",
  technology_adoption: "#8b5cf6",
  funding_round: "#22c55e",
  leadership_change: "#f97316",
  expansion: "#14b8a6",
  partnership: "#6366f1",
  product_launch: "#ec4899",
  no_signal: "#9ca3af",
};

const SIGNAL_TYPE_SHORT: Record<string, string> = {
  hiring_surge: "Hiring",
  technology_adoption: "Tech Adoption",
  funding_round: "Funding",
  leadership_change: "Leadership",
  expansion: "Expansion",
  partnership: "Partnership",
  product_launch: "Launch",
  no_signal: "None",
};

const TOOLTIP_STYLE = {
  borderRadius: "10px",
  border: "1px solid hsl(25 12% 88%)",
  background: "white",
  fontFamily: "DM Sans",
  boxShadow: "0 4px 16px rgba(0,0,0,0.08)",
};

const QUICK_ACTIONS = [
  { to: "/discovery", label: "Run Discovery", icon: Compass },
  {
    to: "/companies?min_score=75&sort=lead_score&order=desc",
    label: "Hot Leads",
    icon: Flame,
  },
  { to: "/companies?status=qualified", label: "Qualified", icon: Zap },
  { to: "/signals", label: "Signals Feed", icon: Radio },
  { to: "/icp", label: "Manage ICP", icon: Target },
  { to: "/analytics", label: "Analytics", icon: BarChart3 },
] as const;

// ── Helpers ──────────────────────────────────────────────────────

function getGreeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function formatWeek(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

// ── Sub-components ───────────────────────────────────────────────

function StatCard({
  label,
  value,
  subtitle,
  icon: Icon,
  delay = 0,
}: {
  label: string;
  value: number;
  subtitle?: string;
  icon: React.ComponentType<{ className?: string }>;
  delay?: number;
}) {
  return (
    <div
      className="group rounded-xl border border-border bg-card p-5 shadow-sm transition-all duration-300 hover:shadow-md hover:-translate-y-0.5 animate-enter"
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-muted-foreground">
          {label}
        </span>
        <div className="rounded-lg bg-muted p-2 transition-colors group-hover:bg-primary/10">
          <Icon className="h-4 w-4 text-muted-foreground transition-colors group-hover:text-primary" />
        </div>
      </div>
      <p className="mt-3 text-3xl font-bold tabular-nums tracking-tight">
        {value}
      </p>
      {subtitle && (
        <p
          className="mt-1 text-xs text-muted-foreground"
          style={{ fontFamily: '"DM Sans", system-ui, sans-serif' }}
        >
          {subtitle}
        </p>
      )}
    </div>
  );
}

function ConversionCard({
  label,
  rate,
}: {
  label: string;
  rate: number | null;
}) {
  const pct = rate ?? 0;
  return (
    <div className="rounded-xl border border-border bg-card px-4 py-3 shadow-sm">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-sm text-muted-foreground">{label}</span>
        <span
          className={cn(
            "text-sm font-semibold tabular-nums",
            rate == null
              ? "text-muted-foreground"
              : rate >= 50
                ? "text-green-600"
                : rate >= 25
                  ? "text-yellow-600"
                  : "text-red-600",
          )}
        >
          {rate != null ? `${rate}%` : "\u2014"}
        </span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <div
          className={cn(
            "h-full rounded-full transition-all duration-700",
            rate == null
              ? "bg-muted"
              : rate >= 50
                ? "bg-green-500"
                : rate >= 25
                  ? "bg-yellow-500"
                  : "bg-red-500",
          )}
          style={{ width: `${Math.min(100, pct)}%` }}
        />
      </div>
    </div>
  );
}

function UsageMeter({
  label,
  current,
  max,
}: {
  label: string;
  current: number;
  max: number;
}) {
  const pct = max > 0 ? (current / max) * 100 : 0;
  const color =
    pct >= 90 ? "bg-red-500" : pct >= 70 ? "bg-yellow-500" : "bg-green-500";
  const textColor =
    pct >= 90
      ? "text-red-600"
      : pct >= 70
        ? "text-yellow-600"
        : "text-muted-foreground";
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="text-xs text-muted-foreground">{label}</span>
        <span className={cn("text-xs font-medium tabular-nums", textColor)}>
          {current}/{max}
        </span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <div
          className={cn(
            "h-full rounded-full transition-all duration-700",
            color,
          )}
          style={{ width: `${Math.min(100, pct)}%` }}
        />
      </div>
    </div>
  );
}

// ── Skeleton ─────────────────────────────────────────────────────

function DashboardSkeleton() {
  return (
    <div className="animate-pulse space-y-6">
      <div className="h-14 w-72 rounded-xl bg-muted" />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {Array.from({ length: 5 }).map((_, i) => (
          <div
            key={i}
            className="h-28 rounded-xl border border-border bg-card"
          />
        ))}
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {Array.from({ length: 6 }).map((_, i) => (
          <div
            key={i}
            className="h-20 rounded-xl border border-border bg-card"
          />
        ))}
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="h-80 rounded-xl border border-border bg-card" />
        <div className="h-80 rounded-xl border border-border bg-card" />
      </div>
    </div>
  );
}

// ── Main ─────────────────────────────────────────────────────────

export default function Dashboard() {
  const { user } = useAuth();
  const { data, isLoading, isError } = useDashboard();
  const { data: topCompaniesData } = useCompanies({
    limit: 5,
    sort: "lead_score",
    order: "desc",
  });
  const { data: signalBreakdown } = useSignalsByType("7d");
  const { data: usage } = useUsageLimits();
  const { data: discoveryJobsData } = useDiscoveryJobs({ limit: 1 });

  if (isLoading) return <DashboardSkeleton />;

  if (isError || !data) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
        <p className="text-lg font-medium">Failed to load dashboard</p>
        <p className="text-sm">Please try again later.</p>
      </div>
    );
  }

  const { stats, funnel, timeline, conversions, recent_signals } = data;
  const topLeads = topCompaniesData?.items ?? [];
  const latestDiscovery = discoveryJobsData?.items[0] ?? null;

  const funnelData = funnel.stages.map((s) => ({
    name:
      STAGE_LABELS[s.stage as Exclude<CompanyStatus, "archived">] ?? s.stage,
    count: s.count,
    fill:
      STAGE_COLORS[s.stage as Exclude<CompanyStatus, "archived">] ?? "#6b7280",
  }));

  const timelineData = timeline.points.map((p) => ({
    week: formatWeek(p.week_start),
    count: p.count,
  }));

  return (
    <div className="space-y-6">
      {/* ── Header ──────────────────────────────────────── */}
      <div className="flex flex-col gap-3 animate-enter sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl tracking-tight">
            {getGreeting()}
            {user?.username ? `, ${user.username}` : ""}
          </h1>
          <p
            className="mt-1 text-sm text-muted-foreground"
            style={{ fontFamily: '"DM Sans", system-ui, sans-serif' }}
          >
            Pipeline overview &mdash; refreshes every 60 s
            {latestDiscovery && (
              <span className="ml-3 inline-flex items-center gap-1.5">
                <span
                  className={cn(
                    "inline-block h-1.5 w-1.5 rounded-full",
                    latestDiscovery.status === "completed"
                      ? "bg-green-500"
                      : latestDiscovery.status === "running"
                        ? "bg-blue-500 animate-pulse"
                        : latestDiscovery.status === "failed"
                          ? "bg-red-500"
                          : "bg-yellow-500",
                  )}
                />
                Last discovery {timeAgo(latestDiscovery.created_at)}
                {latestDiscovery.status === "completed" &&
                  latestDiscovery.companies_found > 0 && (
                    <span className="text-muted-foreground">
                      &mdash; found {latestDiscovery.companies_found}, added{" "}
                      {latestDiscovery.companies_added}
                    </span>
                  )}
              </span>
            )}
          </p>
        </div>
        <div className="flex gap-2">
          <Link
            to="/discovery"
            className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-sm transition-all duration-200 hover:bg-primary/90 hover:shadow-md active:scale-[0.98]"
          >
            <Compass className="h-3.5 w-3.5" />
            Run Discovery
          </Link>
          <Link
            to="/companies?min_score=75&sort=lead_score&order=desc"
            className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-4 py-2 text-sm font-medium shadow-sm transition-all duration-200 hover:bg-accent hover:shadow-md active:scale-[0.98]"
          >
            <Flame className="h-3.5 w-3.5" />
            Hot Leads
          </Link>
        </div>
      </div>

      {/* ── Stat Cards ──────────────────────────────────── */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <StatCard
          label="Total Companies"
          value={stats.total_companies}
          subtitle="Active in pipeline"
          icon={Building2}
          delay={60}
        />
        <StatCard
          label="Total Contacts"
          value={stats.total_contacts}
          subtitle="Across all companies"
          icon={Users}
          delay={120}
        />
        <StatCard
          label="Signals (7d)"
          value={stats.signals_last_7d}
          subtitle="Last 7 days"
          icon={Radio}
          delay={180}
        />
        <StatCard
          label="Hot Leads"
          value={stats.hot_leads}
          subtitle="Score ≥ 75"
          icon={Flame}
          delay={240}
        />
        <StatCard
          label="Warm Leads"
          value={stats.warm_leads}
          subtitle="Score 50–74"
          icon={Sun}
          delay={300}
        />
      </div>

      {/* ── Quick Actions ───────────────────────────────── */}
      <div
        className="animate-enter"
        style={{ animationDelay: "150ms" }}
      >
        <h2 className="mb-3 text-base tracking-tight">Quick Actions</h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          {QUICK_ACTIONS.map((action) => (
            <Link
              key={action.to}
              to={action.to}
              className="group flex flex-col items-center gap-2 rounded-xl border border-border bg-card p-4 text-center shadow-sm transition-all duration-200 hover:shadow-md hover:-translate-y-0.5 hover:bg-accent active:scale-[0.98]"
            >
              <action.icon className="h-5 w-5 text-muted-foreground transition-all duration-200 group-hover:scale-110 group-hover:text-foreground" />
              <span
                className="text-xs font-medium"
                style={{ fontFamily: '"DM Sans", system-ui, sans-serif' }}
              >
                {action.label}
              </span>
            </Link>
          ))}
        </div>
      </div>

      {/* ── Top Leads + Lead Funnel ─────────────────────── */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Top Leads */}
        <div
          className="rounded-xl border border-border bg-card p-5 shadow-sm animate-enter"
          style={{ animationDelay: "200ms" }}
        >
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-base tracking-tight">Top Leads</h2>
            <Link
              to="/companies?sort=lead_score&order=desc"
              className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
              style={{ fontFamily: '"DM Sans", system-ui, sans-serif' }}
            >
              View all <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
          {topLeads.length > 0 ? (
            <div className="space-y-1">
              {topLeads.map((company, i) => (
                <Link
                  key={company.id}
                  to={`/companies/${company.id}`}
                  className="flex items-center gap-3 rounded-lg px-3 py-2.5 transition-colors hover:bg-accent"
                >
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-bold tabular-nums text-muted-foreground">
                    {i + 1}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">
                      {company.name}
                    </p>
                    {company.industry && (
                      <p className="truncate text-xs text-muted-foreground">
                        {company.industry}
                      </p>
                    )}
                  </div>
                  <StatusBadge status={company.status} />
                  <LeadScoreBadge score={company.lead_score} />
                </Link>
              ))}
            </div>
          ) : (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No leads yet
            </p>
          )}
        </div>

        {/* Lead Funnel */}
        <div
          className="rounded-xl border border-border bg-card p-5 shadow-sm animate-enter"
          style={{ animationDelay: "260ms" }}
        >
          <h2 className="mb-4 text-base tracking-tight">Lead Funnel</h2>
          {funnelData.length > 0 ? (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart
                data={funnelData}
                layout="vertical"
                margin={{ top: 0, right: 20, bottom: 0, left: 80 }}
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                  horizontal={false}
                  stroke="hsl(25 12% 90%)"
                />
                <XAxis
                  type="number"
                  allowDecimals={false}
                  tick={{ fontSize: 12, fontFamily: "DM Sans" }}
                />
                <YAxis
                  type="category"
                  dataKey="name"
                  width={80}
                  tick={{ fontSize: 12, fontFamily: "DM Sans" }}
                />
                <Tooltip contentStyle={TOOLTIP_STYLE} />
                <Bar dataKey="count" radius={[0, 6, 6, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="py-10 text-center text-sm text-muted-foreground">
              No companies yet
            </p>
          )}
        </div>
      </div>

      {/* ── Discovery Timeline ──────────────────────────── */}
      <div
        className="rounded-xl border border-border bg-card p-5 shadow-sm animate-enter"
        style={{ animationDelay: "320ms" }}
      >
        <h2 className="mb-4 text-base tracking-tight">
          Leads Discovered &mdash; Last 8 Weeks
        </h2>
        {timelineData.length > 0 ? (
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart
              data={timelineData}
              margin={{ top: 0, right: 20, bottom: 0, left: 0 }}
            >
              <defs>
                <linearGradient
                  id="timelineGrad"
                  x1="0"
                  y1="0"
                  x2="0"
                  y2="1"
                >
                  <stop
                    offset="0%"
                    stopColor="hsl(310 7% 18%)"
                    stopOpacity={0.15}
                  />
                  <stop
                    offset="100%"
                    stopColor="hsl(310 7% 18%)"
                    stopOpacity={0}
                  />
                </linearGradient>
              </defs>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="hsl(25 12% 90%)"
              />
              <XAxis
                dataKey="week"
                tick={{ fontSize: 12, fontFamily: "DM Sans" }}
              />
              <YAxis
                allowDecimals={false}
                tick={{ fontSize: 12, fontFamily: "DM Sans" }}
              />
              <Tooltip contentStyle={TOOLTIP_STYLE} />
              <Area
                type="monotone"
                dataKey="count"
                stroke="hsl(310 7% 18%)"
                strokeWidth={2.5}
                fill="url(#timelineGrad)"
                dot={{
                  r: 4,
                  fill: "hsl(310 7% 18%)",
                  stroke: "white",
                  strokeWidth: 2,
                }}
                activeDot={{
                  r: 6,
                  fill: "hsl(36 90% 55%)",
                  stroke: "white",
                  strokeWidth: 2,
                }}
              />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <p className="py-10 text-center text-sm text-muted-foreground">
            No data yet
          </p>
        )}
      </div>

      {/* ── Bottom Grid: Conversions + Signal Mix + Usage ─ */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Conversion Rates */}
        <div
          className="space-y-3 animate-enter"
          style={{ animationDelay: "380ms" }}
        >
          <h2 className="text-base tracking-tight">Conversion Rates</h2>
          <ConversionCard
            label="Discovery → Enrichment"
            rate={conversions.discovery_to_enrichment}
          />
          <ConversionCard
            label="Enrichment → Qualified"
            rate={conversions.enrichment_to_qualified}
          />
          <ConversionCard
            label="Qualified → Pushed"
            rate={conversions.qualified_to_pushed}
          />
        </div>

        {/* Signal Distribution */}
        <div
          className="animate-enter"
          style={{ animationDelay: "420ms" }}
        >
          <h2 className="mb-3 text-base tracking-tight">
            Signal Mix &mdash; 7d
          </h2>
          <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
            {signalBreakdown &&
            signalBreakdown.breakdown.filter((s) => s.count > 0).length > 0 ? (
              <div className="space-y-2.5">
                {signalBreakdown.breakdown
                  .filter((s) => s.count > 0)
                  .sort((a, b) => b.count - a.count)
                  .slice(0, 6)
                  .map((s) => {
                    const maxCount = signalBreakdown.breakdown.reduce(
                      (m, x) => Math.max(m, x.count),
                      1,
                    );
                    return (
                      <div key={s.signal_type} className="space-y-1">
                        <div className="flex items-center justify-between">
                          <span
                            className="text-xs text-muted-foreground"
                            style={{
                              fontFamily: '"DM Sans", system-ui, sans-serif',
                            }}
                          >
                            {SIGNAL_TYPE_SHORT[s.signal_type] ?? s.signal_type}
                          </span>
                          <span className="text-xs font-medium tabular-nums">
                            {s.count}
                          </span>
                        </div>
                        <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
                          <div
                            className="h-full rounded-full transition-all duration-700"
                            style={{
                              width: `${(s.count / maxCount) * 100}%`,
                              backgroundColor:
                                SIGNAL_TYPE_COLORS[s.signal_type] ?? "#9ca3af",
                            }}
                          />
                        </div>
                      </div>
                    );
                  })}
                <div className="border-t border-border pt-2">
                  <div className="flex items-center justify-between">
                    <span
                      className="text-xs text-muted-foreground"
                      style={{
                        fontFamily: '"DM Sans", system-ui, sans-serif',
                      }}
                    >
                      Total
                    </span>
                    <span className="text-xs font-semibold tabular-nums">
                      {signalBreakdown.total}
                    </span>
                  </div>
                </div>
              </div>
            ) : (
              <p className="py-4 text-center text-xs text-muted-foreground">
                No signals this week
              </p>
            )}
          </div>
        </div>

        {/* Daily Usage */}
        <div
          className="animate-enter"
          style={{ animationDelay: "460ms" }}
        >
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-base tracking-tight">Daily Usage</h2>
            <Link
              to="/settings"
              className="text-xs font-medium text-primary hover:underline"
              style={{ fontFamily: '"DM Sans", system-ui, sans-serif' }}
            >
              Limits
            </Link>
          </div>
          <div className="space-y-4 rounded-xl border border-border bg-card p-4 shadow-sm">
            {usage ? (
              <>
                <UsageMeter
                  label="Discovery Runs"
                  current={usage.discovery_runs_today}
                  max={usage.max_discovery_runs_per_day}
                />
                <UsageMeter
                  label="Enrichments"
                  current={usage.enrichments_today}
                  max={usage.max_enrichments_per_day}
                />
                <UsageMeter
                  label="Scrapes"
                  current={usage.scrapes_today}
                  max={usage.max_scrapes_per_day}
                />
                <div className="border-t border-border pt-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted-foreground">
                      API Cost
                    </span>
                    <span
                      className={cn(
                        "text-xs font-medium tabular-nums",
                        usage.api_cost_today / usage.daily_api_cost_limit >= 0.9
                          ? "text-red-600"
                          : usage.api_cost_today /
                                usage.daily_api_cost_limit >=
                              0.7
                            ? "text-yellow-600"
                            : "text-muted-foreground",
                      )}
                    >
                      ${usage.api_cost_today.toFixed(2)} / $
                      {usage.daily_api_cost_limit.toFixed(2)}
                    </span>
                  </div>
                </div>
              </>
            ) : (
              <div className="space-y-3 animate-pulse">
                {Array.from({ length: 3 }).map((_, i) => (
                  <div key={i} className="space-y-1.5">
                    <div className="h-3 w-24 rounded bg-muted" />
                    <div className="h-1.5 w-full rounded-full bg-muted" />
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Recent Signals ──────────────────────────────── */}
      <div
        className="animate-enter"
        style={{ animationDelay: "500ms" }}
      >
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-base tracking-tight">Recent Signals</h2>
          <Link
            to="/signals"
            className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
            style={{ fontFamily: '"DM Sans", system-ui, sans-serif' }}
          >
            View all <ArrowRight className="h-3 w-3" />
          </Link>
        </div>

        {recent_signals.length > 0 ? (
          <div className="space-y-2">
            {recent_signals.map((sig, i) => (
              <Link
                key={sig.id}
                to={`/companies/${sig.company_id}`}
                className="flex items-center gap-3 rounded-xl border border-border bg-card px-4 py-3 shadow-sm transition-all duration-200 hover:shadow-md hover:-translate-y-px animate-enter-up"
                style={{ animationDelay: `${540 + i * 50}ms` }}
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">
                    {sig.company_name}
                  </p>
                </div>
                <SignalTypeBadge type={sig.signal_type} />
                <ScoreBadge score={sig.relevance_score} />
                <span
                  className="shrink-0 text-xs text-muted-foreground"
                  style={{ fontFamily: '"DM Sans", system-ui, sans-serif' }}
                >
                  {timeAgo(sig.created_at)}
                </span>
              </Link>
            ))}
          </div>
        ) : (
          <p className="py-8 text-center text-sm text-muted-foreground">
            No signals yet
          </p>
        )}
      </div>
    </div>
  );
}
