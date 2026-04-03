import { cn } from "@/lib/utils";
import type {
  CompanyStatus,
  DiscoveryJobStatus,
  EmailStatus,
  ScrapeJobStatus,
  SignalAction,
  SignalType,
} from "@/types/api";

const badgeBase =
  "inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset";

// ── Company status ───────────────────────────────────────────────────────────

export const STATUS_COLORS: Record<CompanyStatus, string> = {
  discovered: "bg-blue-50 text-blue-700 ring-blue-200",
  enriched: "bg-purple-50 text-purple-700 ring-purple-200",
  monitoring: "bg-cyan-50 text-cyan-700 ring-cyan-200",
  qualified: "bg-green-50 text-green-700 ring-green-200",
  pushed: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  archived: "bg-gray-50 text-gray-600 ring-gray-200",
};

export function StatusBadge({ status }: { status: CompanyStatus }) {
  return (
    <span className={cn(badgeBase, "capitalize", STATUS_COLORS[status])}>
      {status}
    </span>
  );
}

// ── ICP score ────────────────────────────────────────────────────────────────

export function ScoreBadge({ score }: { score: number | null }) {
  if (score == null) return <span className="text-muted-foreground">&mdash;</span>;
  const color =
    score >= 75
      ? "bg-green-50 text-green-700 ring-green-200"
      : score >= 50
        ? "bg-yellow-50 text-yellow-700 ring-yellow-200"
        : score >= 25
          ? "bg-orange-50 text-orange-700 ring-orange-200"
          : "bg-gray-50 text-gray-600 ring-gray-200";
  return (
    <span className={cn(badgeBase, "tabular-nums", color)}>
      {score.toFixed(0)}
    </span>
  );
}

// ── Lead score (with gradient bar) ──────────────────────────────────────────

export function LeadScoreBadge({ score }: { score: number | null }) {
  if (score == null) return <span className="text-muted-foreground">&mdash;</span>;
  const color =
    score >= 75
      ? "bg-green-500"
      : score >= 50
        ? "bg-yellow-500"
        : score >= 25
          ? "bg-orange-500"
          : "bg-gray-400";
  const textColor =
    score >= 75
      ? "text-green-700"
      : score >= 50
        ? "text-yellow-700"
        : score >= 25
          ? "text-orange-700"
          : "text-gray-500";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-12 rounded-full bg-muted overflow-hidden">
        <div
          className={cn("h-full rounded-full transition-all duration-500", color)}
          style={{ width: `${Math.min(100, Math.max(0, score))}%` }}
        />
      </div>
      <span className={cn("text-xs font-medium tabular-nums", textColor)}>
        {score.toFixed(0)}
      </span>
    </div>
  );
}

// ── Email status ─────────────────────────────────────────────────────────────

const EMAIL_STATUS_COLORS: Record<EmailStatus, string> = {
  verified: "bg-green-50 text-green-700 ring-green-200",
  "catch-all": "bg-yellow-50 text-yellow-700 ring-yellow-200",
  unverified: "bg-gray-50 text-gray-600 ring-gray-200",
};

const EMAIL_STATUS_LABELS: Record<EmailStatus, string> = {
  verified: "Verified",
  "catch-all": "Catch-all",
  unverified: "Unverified",
};

export function EmailStatusBadge({ status }: { status: EmailStatus | null }) {
  if (!status) return null;
  return (
    <span className={cn(badgeBase, EMAIL_STATUS_COLORS[status])}>
      {EMAIL_STATUS_LABELS[status]}
    </span>
  );
}

// ── Signal type ──────────────────────────────────────────────────────────────

const SIGNAL_TYPE_COLORS: Record<SignalType, string> = {
  hiring_surge: "bg-blue-50 text-blue-700 ring-blue-200",
  technology_adoption: "bg-purple-50 text-purple-700 ring-purple-200",
  funding_round: "bg-green-50 text-green-700 ring-green-200",
  leadership_change: "bg-orange-50 text-orange-700 ring-orange-200",
  expansion: "bg-teal-50 text-teal-700 ring-teal-200",
  partnership: "bg-indigo-50 text-indigo-700 ring-indigo-200",
  product_launch: "bg-pink-50 text-pink-700 ring-pink-200",
  no_signal: "bg-gray-50 text-gray-600 ring-gray-200",
};

const SIGNAL_TYPE_LABELS: Record<SignalType, string> = {
  hiring_surge: "Hiring Surge",
  technology_adoption: "Tech Adoption",
  funding_round: "Funding Round",
  leadership_change: "Leadership Change",
  expansion: "Expansion",
  partnership: "Partnership",
  product_launch: "Product Launch",
  no_signal: "No Signal",
};

export function SignalTypeBadge({ type }: { type: SignalType }) {
  return (
    <span className={cn(badgeBase, SIGNAL_TYPE_COLORS[type])}>
      {SIGNAL_TYPE_LABELS[type]}
    </span>
  );
}

// ── Signal action ────────────────────────────────────────────────────────────

const SIGNAL_ACTION_COLORS: Record<SignalAction, string> = {
  notify_immediate: "bg-red-50 text-red-700 ring-red-200",
  notify_digest: "bg-yellow-50 text-yellow-700 ring-yellow-200",
  enrich_further: "bg-blue-50 text-blue-700 ring-blue-200",
  ignore: "bg-gray-50 text-gray-600 ring-gray-200",
};

const SIGNAL_ACTION_LABELS: Record<SignalAction, string> = {
  notify_immediate: "Notify Now",
  notify_digest: "Digest",
  enrich_further: "Enrich",
  ignore: "Ignore",
};

export function SignalActionBadge({ action }: { action: SignalAction | null }) {
  if (!action) return null;
  return (
    <span className={cn(badgeBase, SIGNAL_ACTION_COLORS[action])}>
      {SIGNAL_ACTION_LABELS[action]}
    </span>
  );
}

// ── Scrape job status ────────────────────────────────────────────────────────

const SCRAPE_STATUS_COLORS: Record<ScrapeJobStatus, string> = {
  pending: "bg-yellow-50 text-yellow-700 ring-yellow-200",
  running: "bg-blue-50 text-blue-700 ring-blue-200",
  completed: "bg-green-50 text-green-700 ring-green-200",
  failed: "bg-red-50 text-red-700 ring-red-200",
};

export function ScrapeJobStatusBadge({ status }: { status: ScrapeJobStatus }) {
  return (
    <span className={cn(badgeBase, "capitalize", SCRAPE_STATUS_COLORS[status])}>
      {status}
    </span>
  );
}

// ── Discovery job status ──────────────────────────────────────────────────────

const DISCOVERY_STATUS_COLORS: Record<DiscoveryJobStatus, string> = {
  pending: "bg-yellow-50 text-yellow-700 ring-yellow-200",
  running: "bg-blue-50 text-blue-700 ring-blue-200",
  completed: "bg-green-50 text-green-700 ring-green-200",
  failed: "bg-red-50 text-red-700 ring-red-200",
};

export function DiscoveryJobStatusBadge({ status }: { status: DiscoveryJobStatus }) {
  return (
    <span className={cn(badgeBase, "capitalize", DISCOVERY_STATUS_COLORS[status])}>
      {status}
    </span>
  );
}
