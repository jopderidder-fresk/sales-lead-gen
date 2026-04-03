import { useState } from "react";
import { cn } from "@/lib/utils";
import {
  useLeadsOverTime,
  useSignalsByType,
  useAPICosts,
  useConversionFunnel,
  useEnrichmentRates,
} from "@/lib/analytics";
import type {
  CompanyStatus,
  SignalType,
} from "@/types/api";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { Download, TrendingUp } from "lucide-react";

// ── Constants ────────────────────────────────────────────────────────

const RANGE_OPTIONS = [
  { label: "7 days", value: "7d" },
  { label: "30 days", value: "30d" },
  { label: "90 days", value: "90d" },
] as const;

const SIGNAL_TYPE_LABELS: Record<SignalType, string> = {
  hiring_surge: "Hiring Surge",
  technology_adoption: "Tech Adoption",
  funding_round: "Funding Round",
  leadership_change: "Leadership",
  expansion: "Expansion",
  partnership: "Partnership",
  product_launch: "Product Launch",
  no_signal: "No Signal",
};

const SIGNAL_TYPE_COLORS: Record<SignalType, string> = {
  hiring_surge: "#3b82f6",
  technology_adoption: "#a855f7",
  funding_round: "#22c55e",
  leadership_change: "#f97316",
  expansion: "#14b8a6",
  partnership: "#6366f1",
  product_launch: "#ec4899",
  no_signal: "#9ca3af",
};

const STAGE_LABELS: Record<Exclude<CompanyStatus, "archived">, string> = {
  discovered: "Discovered",
  enriched: "Enriched",
  monitoring: "Monitoring",
  qualified: "Qualified",
  pushed: "Pushed",
};

const STAGE_COLORS: Record<Exclude<CompanyStatus, "archived">, string> = {
  discovered: "#3b82f6",
  enriched: "#a855f7",
  monitoring: "#06b6d4",
  qualified: "#22c55e",
  pushed: "#10b981",
};

const PROVIDER_COLORS: Record<string, string> = {
  firecrawl: "#f97316",
  hunter: "#3b82f6",
  bedrijfsdata: "#22c55e",
  scrapin: "#a855f7",
  claude: "#06b6d4",
  anthropic: "#06b6d4",
};

function getProviderColor(provider: string): string {
  return PROVIDER_COLORS[provider.toLowerCase()] ?? "#6b7280";
}

// ── Formatters ───────────────────────────────────────────────────────

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function formatCurrency(val: number): string {
  return `€${val.toFixed(2)}`;
}

// ── CSV Export ────────────────────────────────────────────────────────

function downloadCSV(filename: string, headers: string[], rows: string[][]) {
  const csv = [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// ── Range Selector ───────────────────────────────────────────────────

function RangeSelector({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="flex gap-1 rounded-xl border border-border bg-card p-0.5 shadow-sm">
      {RANGE_OPTIONS.map((opt) => (
        <button
          key={opt.value}
          onClick={() => onChange(opt.value)}
          className={cn(
            "rounded-lg px-3 py-1.5 text-xs font-medium transition-all duration-200",
            value === opt.value
              ? "bg-primary text-primary-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground hover:bg-accent",
          )}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

// ── Metric Card ──────────────────────────────────────────────────────

function MetricCard({
  label,
  value,
  subtitle,
}: {
  label: string;
  value: string;
  subtitle?: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-sm transition-all duration-200 hover:shadow-md">
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      <p className="mt-1.5 text-2xl font-bold tabular-nums tracking-tight">{value}</p>
      {subtitle && (
        <p className="mt-0.5 text-xs text-muted-foreground">{subtitle}</p>
      )}
    </div>
  );
}

// ── Chart Card ───────────────────────────────────────────────────────

function ChartCard({
  title,
  children,
  onExport,
}: {
  title: string;
  children: React.ReactNode;
  onExport?: () => void;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-base tracking-tight">{title}</h2>
        {onExport && (
          <button
            onClick={onExport}
            className="flex items-center gap-1 rounded-lg px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
          >
            <Download className="h-3 w-3" />
            CSV
          </button>
        )}
      </div>
      {children}
    </div>
  );
}

// ── Skeleton ─────────────────────────────────────────────────────────

function AnalyticsSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            className="h-24 rounded-xl border border-border bg-card"
          />
        ))}
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            className="h-80 rounded-xl border border-border bg-card"
          />
        ))}
      </div>
    </div>
  );
}

// ── Main ─────────────────────────────────────────────────────────────

export default function Analytics() {
  const [range, setRange] = useState("30d");

  const leadsQuery = useLeadsOverTime(range);
  const signalsQuery = useSignalsByType(range);
  const costsQuery = useAPICosts(range);
  const funnelQuery = useConversionFunnel();
  const enrichmentQuery = useEnrichmentRates();

  const isLoading =
    leadsQuery.isLoading ||
    signalsQuery.isLoading ||
    costsQuery.isLoading ||
    funnelQuery.isLoading ||
    enrichmentQuery.isLoading;

  const isError =
    leadsQuery.isError &&
    signalsQuery.isError &&
    costsQuery.isError &&
    funnelQuery.isError &&
    enrichmentQuery.isError;

  if (isLoading) return <AnalyticsSkeleton />;

  if (isError) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
        <p className="text-lg font-medium">Failed to load analytics</p>
        <p className="text-sm">Please try again later.</p>
      </div>
    );
  }

  const leads = leadsQuery.data;
  const signals = signalsQuery.data;
  const costs = costsQuery.data;
  const funnel = funnelQuery.data;
  const enrichment = enrichmentQuery.data;

  // Prepare stacked bar chart data for API costs (pivot by date)
  const costsByDate = new Map<string, Record<string, number>>();
  const allProviders = new Set<string>();
  for (const p of costs?.points ?? []) {
    const day = formatDate(p.date);
    allProviders.add(p.provider);
    const entry = costsByDate.get(day) ?? {};
    entry[p.provider] = (entry[p.provider] ?? 0) + p.cost;
    costsByDate.set(day, entry);
  }
  const costChartData = [...costsByDate.entries()].map(([day, providers]) => ({
    day,
    ...providers,
  }));
  const providerList = [...allProviders];

  // Funnel data
  const funnelData = (funnel?.stages ?? []).map((s) => ({
    name: STAGE_LABELS[s.stage as Exclude<CompanyStatus, "archived">] ?? s.stage,
    count: s.count,
    percentage: s.percentage,
    fill: STAGE_COLORS[s.stage as Exclude<CompanyStatus, "archived">] ?? "#6b7280",
  }));

  // Pie chart data for signals
  const pieData = (signals?.breakdown ?? []).map((s) => ({
    name: SIGNAL_TYPE_LABELS[s.signal_type] ?? s.signal_type,
    value: s.count,
    fill: SIGNAL_TYPE_COLORS[s.signal_type] ?? "#6b7280",
  }));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl tracking-tight">Analytics</h1>
          <p className="text-sm text-muted-foreground" style={{ fontFamily: '"DM Sans", system-ui, sans-serif' }}>
            Performance metrics and ROI tracking
          </p>
        </div>
        <RangeSelector value={range} onChange={setRange} />
      </div>

      {/* Metric cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="Leads Discovered"
          value={String(leads?.total ?? 0)}
          subtitle={`in last ${range}`}
        />
        <MetricCard
          label="Signals Detected"
          value={String(signals?.total ?? 0)}
          subtitle={`in last ${range}`}
        />
        <MetricCard
          label="API Spend"
          value={formatCurrency(costs?.total_cost ?? 0)}
          subtitle={`in last ${range}`}
        />
        <MetricCard
          label="Cost per Lead"
          value={
            costs?.cost_per_lead != null
              ? formatCurrency(costs.cost_per_lead)
              : "—"
          }
          subtitle="qualified leads only"
        />
      </div>

      {/* Charts row 1: leads over time + signals by type */}
      <div className="grid gap-6 lg:grid-cols-2">
        <ChartCard
          title="Leads Discovered Over Time"
          onExport={() => {
            if (!leads) return;
            downloadCSV(
              "leads-over-time.csv",
              ["Date", "Count"],
              leads.points.map((p) => [formatDate(p.date), String(p.count)]),
            );
          }}
        >
          {(leads?.points.length ?? 0) > 0 ? (
            <ResponsiveContainer width="100%" height={260}>
              <LineChart
                data={leads!.points.map((p) => ({
                  date: formatDate(p.date),
                  count: p.count,
                }))}
                margin={{ top: 5, right: 20, bottom: 5, left: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                <YAxis allowDecimals={false} />
                <Tooltip
                  contentStyle={{
                    borderRadius: "10px",
                    border: "1px solid hsl(25 12% 88%)",
                    background: "white",
                    fontFamily: "DM Sans",
                    boxShadow: "0 4px 16px rgba(0,0,0,0.08)",
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="count"
                  name="Leads"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  dot={{ r: 3 }}
                  activeDot={{ r: 5 }}
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <p className="py-16 text-center text-sm text-muted-foreground">
              No leads data for this period
            </p>
          )}
        </ChartCard>

        <ChartCard title="Signals by Type">
          {pieData.length > 0 ? (
            <ResponsiveContainer width="100%" height={260}>
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
                  outerRadius={95}
                  paddingAngle={2}
                  dataKey="value"
                  label={({ name, percent }: { name?: string; percent?: number }) =>
                    `${name ?? ""} ${((percent ?? 0) * 100).toFixed(0)}%`
                  }
                  labelLine={false}
                >
                  {pieData.map((entry, i) => (
                    <Cell key={i} fill={entry.fill} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    borderRadius: "10px",
                    border: "1px solid hsl(25 12% 88%)",
                    background: "white",
                    fontFamily: "DM Sans",
                    boxShadow: "0 4px 16px rgba(0,0,0,0.08)",
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <p className="py-16 text-center text-sm text-muted-foreground">
              No signals data for this period
            </p>
          )}
        </ChartCard>
      </div>

      {/* Charts row 2: API costs + conversion funnel */}
      <div className="grid gap-6 lg:grid-cols-2">
        <ChartCard
          title="API Spend by Provider"
          onExport={() => {
            if (!costs) return;
            downloadCSV(
              "api-costs.csv",
              ["Date", "Provider", "Cost", "Credits"],
              costs.points.map((p) => [
                formatDate(p.date),
                p.provider,
                p.cost.toFixed(4),
                p.credits.toFixed(1),
              ]),
            );
          }}
        >
          {costChartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart
                data={costChartData}
                margin={{ top: 5, right: 20, bottom: 5, left: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="day" tick={{ fontSize: 11 }} />
                <YAxis tickFormatter={(v: number) => `€${v}`} />
                <Tooltip
                  formatter={(value) => formatCurrency(Number(value))}
                  contentStyle={{
                    borderRadius: "10px",
                    border: "1px solid hsl(25 12% 88%)",
                    background: "white",
                    fontFamily: "DM Sans",
                    boxShadow: "0 4px 16px rgba(0,0,0,0.08)",
                  }}
                />
                <Legend />
                {providerList.map((provider) => (
                  <Bar
                    key={provider}
                    dataKey={provider}
                    stackId="cost"
                    fill={getProviderColor(provider)}
                    radius={[2, 2, 0, 0]}
                  />
                ))}
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="py-16 text-center text-sm text-muted-foreground">
              No API cost data for this period
            </p>
          )}
        </ChartCard>

        <ChartCard title="Conversion Funnel">
          {funnelData.length > 0 ? (
            <div className="space-y-3 pt-2">
              {funnelData.map((stage) => (
                <div key={stage.name} className="space-y-1">
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-medium">{stage.name}</span>
                    <span className="tabular-nums text-muted-foreground">
                      {stage.count}{" "}
                      <span className="text-xs">({stage.percentage}%)</span>
                    </span>
                  </div>
                  <div className="h-2.5 w-full rounded-full bg-muted overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-500"
                      style={{
                        width: `${stage.percentage}%`,
                        backgroundColor: stage.fill,
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="py-16 text-center text-sm text-muted-foreground">
              No funnel data available
            </p>
          )}
        </ChartCard>
      </div>

      {/* Enrichment rates */}
      <ChartCard title="Enrichment Hit Rate by Provider">
        {(enrichment?.providers.length ?? 0) > 0 ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {enrichment!.providers.map((p) => (
              <div
                key={p.provider}
                className="rounded-xl border border-border bg-card p-4 shadow-sm"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium capitalize">
                    {p.provider}
                  </span>
                  <span
                    className={cn(
                      "text-sm font-bold tabular-nums",
                      p.rate >= 50
                        ? "text-green-600"
                        : p.rate >= 25
                          ? "text-yellow-600"
                          : "text-red-600",
                    )}
                  >
                    {p.rate}%
                  </span>
                </div>
                <div className="mt-2 h-2 w-full rounded-full bg-muted overflow-hidden">
                  <div
                    className={cn("h-full rounded-full", {
                      "bg-green-500": p.rate >= 50,
                      "bg-yellow-500": p.rate >= 25 && p.rate < 50,
                      "bg-red-500": p.rate < 25,
                    })}
                    style={{ width: `${Math.min(100, p.rate)}%` }}
                  />
                </div>
                <p className="mt-1.5 text-xs text-muted-foreground">
                  {p.successes} verified / {p.attempts} contacts
                </p>
              </div>
            ))}

            {/* Overall rate */}
            <div className="rounded-xl border-2 border-primary/20 bg-primary/5 p-4 shadow-sm">
              <div className="flex items-center gap-2">
                <TrendingUp className="h-4 w-4 text-primary" />
                <span className="text-sm font-semibold">Overall Rate</span>
              </div>
              <p className="mt-2 text-3xl font-bold tabular-nums text-primary">
                {enrichment!.overall_rate}%
              </p>
              <p className="mt-0.5 text-xs text-muted-foreground">
                across all providers
              </p>
            </div>
          </div>
        ) : (
          <p className="py-10 text-center text-sm text-muted-foreground">
            No enrichment data available yet
          </p>
        )}
      </ChartCard>
    </div>
  );
}
