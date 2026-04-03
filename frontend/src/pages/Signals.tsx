import { useSignalsFeed } from "@/lib/signals";
import { ScoreBadge, SignalActionBadge } from "@/components/badges";
import { cn } from "@/lib/utils";
import type { SignalAction, SignalType, SignalWithCompany } from "@/types/api";
import {
  ChevronDown,
  ChevronRight,
  Cpu,
  ExternalLink,
  Filter,
  Globe,
  Loader2,
  Minus,
  Package,
  RefreshCw,
  Rss,
  Share2,
  TrendingUp,
  UserCheck,
  Users,
  X,
} from "lucide-react";
import type { ComponentType } from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

// ── Constants ──────────────────────────────────────────────────────

const SIGNAL_TYPE_OPTIONS: { value: SignalType; label: string }[] = [
  { value: "hiring_surge", label: "Hiring Surge" },
  { value: "funding_round", label: "Funding Round" },
  { value: "technology_adoption", label: "Tech Adoption" },
  { value: "leadership_change", label: "Leadership Change" },
  { value: "expansion", label: "Expansion" },
  { value: "partnership", label: "Partnership" },
  { value: "product_launch", label: "Product Launch" },
];

const ACTION_OPTIONS: { value: SignalAction; label: string }[] = [
  { value: "notify_immediate", label: "Notify Now" },
  { value: "notify_digest", label: "Digest" },
  { value: "enrich_further", label: "Enrich" },
  { value: "ignore", label: "Ignore" },
];

const MEANINGFUL_SIGNAL_TYPES = SIGNAL_TYPE_OPTIONS.map((o) => o.value);

function signalTypesForApi(
  selectedUrlTypes: SignalType[],
  includeNoSignal: boolean,
): SignalType[] | undefined {
  if (selectedUrlTypes.length > 0) return selectedUrlTypes;
  if (!includeNoSignal) return MEANINGFUL_SIGNAL_TYPES;
  return undefined;
}

// ── Signal type metadata ──────────────────────────────────────────

type IconComponent = ComponentType<{ className?: string }>;
type SignalMeta = { label: string; Icon: IconComponent };

const SIGNAL_META: Record<SignalType, SignalMeta> = {
  hiring_surge:        { label: "Hiring Surge",      Icon: Users      },
  funding_round:       { label: "Funding Round",     Icon: TrendingUp },
  technology_adoption: { label: "Tech Adoption",     Icon: Cpu        },
  leadership_change:   { label: "Leadership Change", Icon: UserCheck  },
  expansion:           { label: "Expansion",         Icon: Globe      },
  partnership:         { label: "Partnership",       Icon: Share2     },
  product_launch:      { label: "Product Launch",    Icon: Package    },
  no_signal:           { label: "No Signal",         Icon: Minus      },
};

const SIGNAL_DOT: Record<SignalType, string> = {
  hiring_surge:        "bg-blue-400",
  funding_round:       "bg-emerald-400",
  technology_adoption: "bg-violet-400",
  leadership_change:   "bg-orange-400",
  expansion:           "bg-teal-400",
  partnership:         "bg-indigo-400",
  product_launch:      "bg-pink-400",
  no_signal:           "bg-gray-300",
};

const SIGNAL_PILL: Record<SignalType, string> = {
  hiring_surge:        "bg-blue-50 text-blue-700 ring-blue-200",
  funding_round:       "bg-emerald-50 text-emerald-700 ring-emerald-200",
  technology_adoption: "bg-violet-50 text-violet-700 ring-violet-200",
  leadership_change:   "bg-orange-50 text-orange-700 ring-orange-200",
  expansion:           "bg-teal-50 text-teal-700 ring-teal-200",
  partnership:         "bg-indigo-50 text-indigo-700 ring-indigo-200",
  product_launch:      "bg-pink-50 text-pink-700 ring-pink-200",
  no_signal:           "bg-gray-50 text-gray-500 ring-gray-200",
};

// ── Relative time ─────────────────────────────────────────────────

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(iso).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}

// ── Group by company ───────────────────────────────────────────────

type CompanyGroupData = {
  company_id: string;
  company_name: string;
  company_domain: string | null;
  signals: SignalWithCompany[];
  latestAt: string;
  topType: SignalType;
  uniqueTypes: SignalType[];
  maxScore: number | null;
};

function groupByCompany(signals: SignalWithCompany[]): CompanyGroupData[] {
  const map = new Map<string, CompanyGroupData>();

  for (const s of signals) {
    const key = String(s.company_id);
    if (!map.has(key)) {
      map.set(key, {
        company_id: key,
        company_name: s.company_name,
        company_domain: s.company_domain ?? null,
        signals: [],
        latestAt: s.created_at,
        topType: s.signal_type,
        uniqueTypes: [],
        maxScore: null,
      });
    }
    const g = map.get(key)!;
    g.signals.push(s);
    if (s.created_at > g.latestAt) {
      g.latestAt = s.created_at;
      g.topType = s.signal_type;
    }
    if (s.signal_type !== "no_signal" && !g.uniqueTypes.includes(s.signal_type)) {
      g.uniqueTypes.push(s.signal_type);
    }
    if (s.relevance_score != null) {
      g.maxScore = g.maxScore == null ? s.relevance_score : Math.max(g.maxScore, s.relevance_score);
    }
  }

  for (const g of map.values()) {
    g.signals.sort((a, b) => b.created_at.localeCompare(a.created_at));
  }

  return Array.from(map.values()).sort((a, b) => b.latestAt.localeCompare(a.latestAt));
}

// ── MultiCheckbox ─────────────────────────────────────────────────

function MultiCheckbox<T extends string>({
  label,
  options,
  selected,
  onChange,
}: {
  label: string;
  options: { value: T; label: string }[];
  selected: T[];
  onChange: (v: T[]) => void;
}) {
  function toggle(value: T) {
    onChange(selected.includes(value) ? selected.filter((v) => v !== value) : [...selected, value]);
  }
  return (
    <div>
      <p className="mb-2 text-xs font-medium text-muted-foreground uppercase tracking-wider">{label}</p>
      <div className="flex flex-wrap gap-1.5">
        {options.map((opt) => {
          const active = selected.includes(opt.value);
          return (
            <button
              key={opt.value}
              type="button"
              onClick={() => toggle(opt.value)}
              className={cn(
                "rounded-lg border px-2.5 py-1 text-xs font-medium transition-all duration-200",
                active
                  ? "border-primary bg-primary text-primary-foreground shadow-sm"
                  : "border-input bg-card text-muted-foreground hover:border-primary hover:text-primary",
              )}
            >
              {opt.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ── Signal detail row (nested inside company) ─────────────────────

function SignalRow({ signal, isLast }: { signal: SignalWithCompany; isLast: boolean }) {
  const [expanded, setExpanded] = useState(false);
  const meta = SIGNAL_META[signal.signal_type];
  const hasDetail = !!(signal.llm_summary || signal.source_url);

  return (
    <div className={cn("group/signal", !isLast && "border-b border-border/40")}>
      <button
        type="button"
        disabled={!hasDetail}
        className={cn(
          "w-full text-left transition-colors duration-150",
          hasDetail ? "cursor-pointer hover:bg-accent/30" : "cursor-default",
          expanded && "bg-accent/20",
        )}
        onClick={() => hasDetail && setExpanded((v) => !v)}
      >
        <div className="flex items-center gap-3 pl-10 pr-5 py-2.5">
          {/* Signal type pill */}
          <div
            className={cn(
              "inline-flex shrink-0 items-center gap-1.5 rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
              SIGNAL_PILL[signal.signal_type],
            )}
          >
            <meta.Icon className="h-3 w-3 shrink-0" />
            <span>{meta.label}</span>
          </div>

          {/* Flex fill */}
          <div className="flex-1" />

          {/* Score */}
          <div className="w-10 shrink-0 flex justify-end">
            {signal.relevance_score != null && <ScoreBadge score={signal.relevance_score} />}
          </div>

          {/* Action */}
          <div className="hidden w-20 shrink-0 justify-end sm:flex">
            {signal.action_taken && <SignalActionBadge action={signal.action_taken} />}
          </div>

          {/* Time */}
          <span className="w-14 shrink-0 text-right text-xs tabular-nums text-muted-foreground">
            {relativeTime(signal.created_at)}
          </span>

          {/* Chevron */}
          <ChevronDown
            className={cn(
              "h-3.5 w-3.5 shrink-0 text-muted-foreground/40 transition-transform duration-200",
              expanded && "rotate-180",
              !hasDetail && "invisible",
            )}
          />
        </div>
      </button>

      {/* Expanded detail */}
      {expanded && (
        <div className="border-t border-border/40 bg-muted/20 pl-10 pr-5 pb-4 pt-3">
          {signal.llm_summary && (
            <p className="text-sm leading-relaxed text-muted-foreground">{signal.llm_summary}</p>
          )}
          {signal.source_url && (
            <a
              href={signal.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-2 inline-flex items-center gap-1.5 text-xs font-medium text-primary transition-opacity hover:opacity-70"
            >
              {signal.source_title ?? "View source"}
              <ExternalLink className="h-3 w-3" />
            </a>
          )}
        </div>
      )}
    </div>
  );
}

// ── Company group ─────────────────────────────────────────────────

function CompanyGroup({ group }: { group: CompanyGroupData }) {
  const [expanded, setExpanded] = useState(false);
  const { company_id, company_name, company_domain, signals, latestAt, uniqueTypes, maxScore } = group;

  return (
    <div
      className={cn(
        "overflow-hidden rounded-xl border border-border bg-card transition-all duration-200",
        expanded ? "shadow-md" : "shadow-sm",
      )}
    >
      {/* Company header */}
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className={cn(
          "w-full text-left transition-colors duration-150 hover:bg-accent/20",
          expanded && "bg-accent/10",
        )}
      >
        <div className="flex items-center gap-4 px-5 py-4">
          {/* Expand indicator */}
          <ChevronRight
            className={cn(
              "h-4 w-4 shrink-0 text-muted-foreground/50 transition-transform duration-200",
              expanded && "rotate-90",
            )}
          />

          {/* Company info */}
          <div className="flex-1 min-w-0">
            <div className="flex items-baseline gap-2 flex-wrap">
              <Link
                to={`/companies/${company_id}`}
                onClick={(e) => e.stopPropagation()}
                className="font-semibold text-sm text-foreground hover:text-primary transition-colors truncate"
              >
                {company_name}
              </Link>
              {company_domain && (
                <span className="text-xs text-muted-foreground truncate hidden sm:inline">
                  {company_domain}
                </span>
              )}
            </div>

            {/* Signal type dots */}
            {uniqueTypes.length > 0 && (
              <div className="flex items-center gap-2.5 mt-1.5 flex-wrap">
                {uniqueTypes.slice(0, 5).map((type) => (
                  <span key={type} className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                    <span className={cn("h-1.5 w-1.5 rounded-full shrink-0", SIGNAL_DOT[type])} />
                    <span className="hidden md:inline">{SIGNAL_META[type].label}</span>
                  </span>
                ))}
                {uniqueTypes.length > 5 && (
                  <span className="text-xs text-muted-foreground">+{uniqueTypes.length - 5}</span>
                )}
              </div>
            )}
          </div>

          {/* Right-side meta */}
          <div className="flex items-center gap-2.5 shrink-0">
            <span className="inline-flex items-center rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium tabular-nums text-muted-foreground">
              {signals.length} signal{signals.length !== 1 ? "s" : ""}
            </span>
            {maxScore != null && <ScoreBadge score={maxScore} />}
            <span className="w-14 text-right text-xs tabular-nums text-muted-foreground shrink-0">
              {relativeTime(latestAt)}
            </span>
          </div>
        </div>
      </button>

      {/* Signals list */}
      {expanded && (
        <div className="border-t border-border/50">
          {/* Column headers */}
          <div className="flex items-center gap-3 pl-10 pr-5 py-1.5 bg-muted/30 border-b border-border/40">
            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Signal</span>
            <div className="flex-1" />
            <span className="w-10 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">Score</span>
            <span className="hidden sm:block w-20 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">Action</span>
            <span className="w-14 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">When</span>
            <span className="w-3.5" />
          </div>
          {signals.map((signal, i) => (
            <SignalRow key={signal.id} signal={signal} isLast={i === signals.length - 1} />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Skeleton ──────────────────────────────────────────────────────

function SkeletonRow() {
  return (
    <div className="animate-pulse overflow-hidden rounded-xl border border-border bg-card shadow-sm">
      <div className="flex items-center gap-4 px-5 py-4">
        <div className="h-4 w-4 rounded bg-muted shrink-0" />
        <div className="flex-1">
          <div className="h-4 w-40 rounded bg-muted mb-2" />
          <div className="flex gap-2">
            <div className="h-2 w-2 rounded-full bg-muted" />
            <div className="h-2.5 w-16 rounded bg-muted" />
            <div className="h-2 w-2 rounded-full bg-muted" />
            <div className="h-2.5 w-20 rounded bg-muted" />
          </div>
        </div>
        <div className="flex items-center gap-2.5 shrink-0">
          <div className="h-5 w-16 rounded-full bg-muted" />
          <div className="h-5 w-8 rounded bg-muted" />
          <div className="h-3 w-14 rounded bg-muted" />
        </div>
      </div>
    </div>
  );
}

// ── Empty state ───────────────────────────────────────────────────

function EmptyState({ hasFilters }: { hasFilters: boolean }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="rounded-2xl bg-muted p-5">
        <Rss className="h-8 w-8 text-muted-foreground/50" />
      </div>
      <h3 className="mt-5 text-base font-medium">
        {hasFilters ? "No signals match your filters" : "No signals yet"}
      </h3>
      <p className="mt-1.5 max-w-sm text-sm text-muted-foreground">
        {hasFilters
          ? "Try adjusting your filters."
          : "Signals will appear here once monitoring detects activity."}
      </p>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────

export default function Signals() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(false);

  // Company search (debounced)
  const urlCompany = searchParams.get("company") ?? "";
  const [companyInput, setCompanyInput] = useState(urlCompany);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const prevUrlCompany = useRef(urlCompany);
  useEffect(() => {
    if (urlCompany !== prevUrlCompany.current) {
      prevUrlCompany.current = urlCompany;
      setCompanyInput(urlCompany);
    }
  }, [urlCompany]);

  // Parse URL params
  const urlTypes = (searchParams.get("types") ?? "").split(",").filter(Boolean) as SignalType[];
  const urlActions = (searchParams.get("actions") ?? "").split(",").filter(Boolean) as SignalAction[];
  const rawMinScore = searchParams.get("min_score");
  const urlMinScore =
    rawMinScore !== null && !isNaN(Number(rawMinScore)) ? Number(rawMinScore) : null;
  const urlDateFrom = searchParams.get("date_from") ?? null;
  const urlDateTo = searchParams.get("date_to") ?? null;
  const includeNoSignal = searchParams.get("hide_no_signal") === "0";

  const hasFilters = !!(
    urlTypes.length ||
    urlActions.length ||
    urlMinScore !== null ||
    urlDateFrom ||
    urlDateTo ||
    urlCompany ||
    includeNoSignal
  );

  const updateParam = useCallback(
    (key: string, value: string | null) => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        if (value) next.set(key, value);
        else next.delete(key);
        return next;
      });
    },
    [setSearchParams],
  );

  useEffect(() => {
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => updateParam("company", companyInput || null), 300);
    return () => clearTimeout(debounceRef.current);
  }, [companyInput, updateParam]);

  function handleTypesChange(types: SignalType[]) {
    updateParam("types", types.length ? types.join(",") : null);
  }

  function handleActionsChange(actions: SignalAction[]) {
    updateParam("actions", actions.length ? actions.join(",") : null);
  }

  function clearFilters() {
    setSearchParams({});
    setCompanyInput("");
  }

  const { data, isLoading, isError, isFetchingNextPage, hasNextPage, fetchNextPage, isFetching } =
    useSignalsFeed(
      {
        signal_type: signalTypesForApi(urlTypes, includeNoSignal),
        action_taken: urlActions.length ? urlActions : undefined,
        min_score: urlMinScore,
        date_from: urlDateFrom,
        date_to: urlDateTo,
        company_search: urlCompany || null,
      },
      { refetchInterval: autoRefresh ? 30_000 : false },
    );

  const allSignals = data?.pages.flatMap((p) => p.items) ?? [];
  const totalCount = data?.pages[0]?.total ?? null;

  // Type distribution for quick-filter pills
  const typeCounts = allSignals.reduce<Partial<Record<SignalType, number>>>((acc, s) => {
    acc[s.signal_type] = (acc[s.signal_type] ?? 0) + 1;
    return acc;
  }, {});
  const topTypes = (Object.entries(typeCounts) as [SignalType, number][])
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5);

  const companyGroups = groupByCompany(allSignals);

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-3 animate-enter">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Signal Feed</h1>
          <p className="mt-0.5 text-sm text-muted-foreground">
            {totalCount !== null
              ? `${totalCount} signal${totalCount !== 1 ? "s" : ""} across ${companyGroups.length} compan${companyGroups.length !== 1 ? "ies" : "y"}`
              : "Buying signals and intent data across all monitored companies."}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {isFetching && !isLoading && (
            <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
          )}
          <button
            type="button"
            onClick={() => setAutoRefresh((v) => !v)}
            title={autoRefresh ? "Live — refreshes every 30s" : "Auto-refresh off"}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-lg border px-3 py-2 text-sm font-medium transition-all duration-200",
              autoRefresh
                ? "border-primary bg-primary/5 text-primary"
                : "border-input bg-card text-muted-foreground hover:bg-accent",
            )}
          >
            <RefreshCw className={cn("h-4 w-4", autoRefresh && "animate-spin [animation-duration:3s]")} />
            {autoRefresh ? "Live" : "Auto-refresh"}
          </button>
        </div>
      </div>

      {/* Type distribution pills (quick filters) */}
      {topTypes.length > 0 && (
        <div
          className="flex flex-wrap items-center gap-2 animate-enter"
          style={{ animationDelay: "40ms" }}
        >
          {topTypes.map(([type, count]) => {
            const meta = SIGNAL_META[type];
            const active = urlTypes.includes(type);
            return (
              <button
                key={type}
                type="button"
                onClick={() =>
                  handleTypesChange(
                    active ? urlTypes.filter((t) => t !== type) : [...urlTypes, type],
                  )
                }
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium transition-all duration-150",
                  active
                    ? "border-primary bg-primary text-primary-foreground"
                    : "border-input bg-card text-muted-foreground hover:border-foreground/30 hover:text-foreground",
                )}
              >
                <meta.Icon className="h-3 w-3" />
                <span className="tabular-nums">{count}</span>
                <span>{meta.label}</span>
              </button>
            );
          })}
        </div>
      )}

      {/* Search + filter bar */}
      <div
        className="flex flex-wrap items-center gap-3 animate-enter"
        style={{ animationDelay: "60ms" }}
      >
        <div className="relative min-w-[200px] max-w-sm flex-1">
          <input
            type="text"
            value={companyInput}
            onChange={(e) => setCompanyInput(e.target.value)}
            placeholder="Search company…"
            className="w-full rounded-lg border border-input bg-card py-2.5 pl-3 pr-8 text-sm shadow-sm outline-none transition-shadow placeholder:text-muted-foreground focus:ring-2 focus:ring-ring/40 focus:shadow-md"
          />
          {companyInput && (
            <button
              type="button"
              onClick={() => setCompanyInput("")}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
        <button
          type="button"
          onClick={() => setFiltersOpen((o) => !o)}
          className={cn(
            "inline-flex items-center gap-2 rounded-lg border px-3 py-2.5 text-sm font-medium shadow-sm transition-all duration-200",
            filtersOpen || hasFilters
              ? "border-primary bg-primary/5 text-primary"
              : "border-input bg-card text-muted-foreground hover:bg-accent",
          )}
        >
          <Filter className="h-4 w-4" />
          Filters
          {hasFilters && (
            <span className="rounded-full bg-primary px-1.5 py-0.5 text-xs leading-none text-primary-foreground">
              {[
                urlTypes.length > 0,
                urlActions.length > 0,
                urlMinScore !== null,
                !!urlDateFrom || !!urlDateTo,
                !!urlCompany,
                includeNoSignal,
              ].filter(Boolean).length}
            </span>
          )}
        </button>
        {hasFilters && (
          <button
            type="button"
            onClick={clearFilters}
            className="text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            Clear all
          </button>
        )}
      </div>

      {/* Filter panel */}
      {filtersOpen && (
        <div className="space-y-4 rounded-xl border border-border bg-card p-5 shadow-sm animate-enter">
          <label className="flex cursor-pointer items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={includeNoSignal}
              onChange={(e) => updateParam("hide_no_signal", e.target.checked ? "0" : null)}
              className="rounded border-input accent-primary"
            />
            <span>Include &quot;No signal&quot; rows</span>
          </label>
          <p className="text-xs text-muted-foreground">
            By default the feed hides non-buying classifications so you only see intent signals.
          </p>
          <MultiCheckbox
            label="Signal Type"
            options={SIGNAL_TYPE_OPTIONS}
            selected={urlTypes}
            onChange={handleTypesChange}
          />
          <MultiCheckbox
            label="Action Taken"
            options={ACTION_OPTIONS}
            selected={urlActions}
            onChange={handleActionsChange}
          />
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div>
              <label className="mb-1.5 block text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Min Score (0&ndash;100)
              </label>
              <input
                type="number"
                min={0}
                max={100}
                value={urlMinScore ?? ""}
                onChange={(e) => updateParam("min_score", e.target.value || null)}
                placeholder="e.g. 75"
                className="w-full rounded-lg border border-input bg-background px-3 py-2.5 text-sm outline-none transition-shadow focus:ring-2 focus:ring-ring/40"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium uppercase tracking-wider text-muted-foreground">
                From Date
              </label>
              <input
                type="date"
                value={urlDateFrom ?? ""}
                max={urlDateTo ?? undefined}
                onChange={(e) => updateParam("date_from", e.target.value || null)}
                className="w-full rounded-lg border border-input bg-background px-3 py-2.5 text-sm outline-none transition-shadow focus:ring-2 focus:ring-ring/40"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium uppercase tracking-wider text-muted-foreground">
                To Date
              </label>
              <input
                type="date"
                value={urlDateTo ?? ""}
                min={urlDateFrom ?? undefined}
                onChange={(e) => updateParam("date_to", e.target.value || null)}
                className="w-full rounded-lg border border-input bg-background px-3 py-2.5 text-sm outline-none transition-shadow focus:ring-2 focus:ring-ring/40"
              />
            </div>
          </div>
        </div>
      )}

      {/* Feed */}
      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <SkeletonRow key={i} />
          ))}
        </div>
      ) : isError ? (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <p className="text-sm text-destructive">Failed to load signals. Please try again.</p>
        </div>
      ) : allSignals.length === 0 ? (
        <EmptyState hasFilters={hasFilters} />
      ) : (
        <div className="space-y-2">
          {companyGroups.map((group) => (
            <CompanyGroup key={group.company_id} group={group} />
          ))}

          {/* Load more */}
          {hasNextPage && (
            <div className="flex justify-center pt-2">
              <button
                type="button"
                onClick={() => fetchNextPage()}
                disabled={isFetchingNextPage}
                className="inline-flex items-center gap-2 rounded-lg border border-input bg-card px-5 py-2.5 text-sm font-medium shadow-sm transition-all hover:bg-accent hover:shadow-md disabled:opacity-50"
              >
                {isFetchingNextPage && <Loader2 className="h-4 w-4 animate-spin" />}
                Load more
              </button>
            </div>
          )}

          {!hasNextPage && allSignals.length > 0 && (
            <p className="py-4 text-center text-xs text-muted-foreground">
              All {allSignals.length} signal{allSignals.length !== 1 ? "s" : ""} loaded
            </p>
          )}
        </div>
      )}
    </div>
  );
}
