import { CustomSelect } from "@/components/Select";
import {
  useCRMStatusSync,
  useCompanyContacts,
  useCompanyDetail,
  useCompanyEnrichmentJobs,
  useCompanyScrapeJobs,
  useCompanySignals,
  usePushToCRM,
  useTriggerContacts,
  useTriggerEnrichment,
  useTriggerLinkedInScrape,
  useTriggerPipeline,
  useTriggerScrape,
} from "@/lib/companyDetail";
import { useUpdateCompany, useDeleteCompany } from "@/lib/companies";
import { useHasActiveICP } from "@/lib/icp";
import {
  EmailStatusBadge,
  LeadScoreBadge,
  ScoreBadge,
  ScrapeJobStatusBadge,
  SignalActionBadge,
  SignalTypeBadge,
  StatusBadge,
} from "@/components/badges";
import { cn } from "@/lib/utils";
import type { CompanyDetailResponse, CompanyInfo, CompanyStatus, SignalType } from "@/types/api";
import {
  Building2,
  Check,
  ChevronLeft,
  ChevronRight,
  ClipboardCopy,
  ExternalLink,
  Loader2,
  Pencil,
  RefreshCw,
  Trash2,
  X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

function usePrevious<T>(value: T): T | undefined {
  const ref = useRef<T>(undefined);
  useEffect(() => { ref.current = value; }, [value]);
  return ref.current;
}

// ── Constants ─────────────────────────────────────────────────────────────────

const STATUS_OPTIONS: { value: CompanyStatus; label: string }[] = [
  { value: "discovered", label: "Discovered" },
  { value: "enriched", label: "Enriched" },
  { value: "monitoring", label: "Monitoring" },
  { value: "qualified", label: "Qualified" },
  { value: "pushed", label: "Pushed" },
];

type Tab = "overview" | "business-details" | "company-info" | "contacts" | "signals" | "scrape-jobs";
const TABS: { value: Tab; label: string }[] = [
  { value: "overview", label: "Overview" },
  { value: "business-details", label: "Business Details" },
  { value: "company-info", label: "Company Info" },
  { value: "contacts", label: "Contacts" },
  { value: "signals", label: "Signals" },
  { value: "scrape-jobs", label: "Scrape Jobs" },
];

const PAGE_SIZE = 10;

const MEANINGFUL_SIGNAL_TYPES: SignalType[] = [
  "hiring_surge",
  "technology_adoption",
  "funding_round",
  "leadership_change",
  "expansion",
  "partnership",
  "product_launch",
];

// ── Helpers ──────────────────────────────────────────────────────────────────

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-GB", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// ── CopyButton ───────────────────────────────────────────────────────────────

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  function handleCopy() {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }).catch(() => {});
  }

  return (
    <button
      type="button"
      onClick={handleCopy}
      title={copied ? "Copied!" : "Copy to clipboard"}
      className="ml-1 inline-flex items-center text-muted-foreground transition-colors hover:text-foreground"
    >
      {copied ? (
        <Check className="h-3.5 w-3.5 text-green-600" />
      ) : (
        <ClipboardCopy className="h-3.5 w-3.5" />
      )}
    </button>
  );
}

// ── Pagination ───────────────────────────────────────────────────────────────

function Pagination({
  offset,
  limit,
  total,
  onOffsetChange,
}: {
  offset: number;
  limit: number;
  total: number;
  onOffsetChange: (offset: number) => void;
}) {
  if (total === 0) return null;
  const page = Math.floor(offset / limit) + 1;
  const totalPages = Math.ceil(total / limit);

  return (
    <div className="flex flex-wrap items-center justify-between gap-2 pt-2 text-sm text-muted-foreground">
      <span>
        {offset + 1}–{Math.min(offset + limit, total)} of {total}
      </span>
      <div className="flex items-center gap-1">
        <button
          type="button"
          disabled={page <= 1}
          onClick={() => onOffsetChange(Math.max(0, offset - limit))}
          className="inline-flex items-center rounded-md border border-input px-2 py-1 disabled:opacity-40"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
        <span className="px-2">
          {page} / {totalPages}
        </span>
        <button
          type="button"
          disabled={page >= totalPages}
          onClick={() => onOffsetChange(offset + limit)}
          className="inline-flex items-center rounded-md border border-input px-2 py-1 disabled:opacity-40"
        >
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

// ── Edit modal ────────────────────────────────────────────────────────────────

function EditModal({
  company,
  onClose,
}: {
  company: {
    id: number;
    industry: string | null;
    size: string | null;
    location: string | null;
    phone: string | null;
    email: string | null;
    kvk_number: string | null;
    address: string | null;
    postal_code: string | null;
    city: string | null;
    province: string | null;
    linkedin_url: string | null;
    website_url: string | null;
    status: CompanyStatus;
  };
  onClose: () => void;
}) {
  const update = useUpdateCompany();
  const [form, setForm] = useState({
    industry: company.industry ?? "",
    size: company.size ?? "",
    location: company.location ?? "",
    phone: company.phone ?? "",
    email: company.email ?? "",
    kvk_number: company.kvk_number ?? "",
    address: company.address ?? "",
    postal_code: company.postal_code ?? "",
    city: company.city ?? "",
    province: company.province ?? "",
    linkedin_url: company.linkedin_url ?? "",
    website_url: company.website_url ?? "",
    status: company.status,
  });

  // Close on Escape
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      await update.mutateAsync({
        id: company.id,
        industry: form.industry || null,
        size: form.size || null,
        location: form.location || null,
        phone: form.phone || null,
        email: form.email || null,
        kvk_number: form.kvk_number || null,
        address: form.address || null,
        postal_code: form.postal_code || null,
        city: form.city || null,
        province: form.province || null,
        linkedin_url: form.linkedin_url || null,
        website_url: form.website_url || null,
        status: form.status,
      });
      onClose();
    } catch {
      // Mutation error is surfaced via update.isError in the UI below
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      role="dialog"
      aria-modal="true"
      aria-labelledby="edit-modal-title"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-xl border border-border bg-card p-6 shadow-sm shadow-xl max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 id="edit-modal-title" className="text-lg font-semibold">Edit Company</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium">Industry</label>
            <input
              type="text"
              value={form.industry}
              onChange={(e) => setForm((f) => ({ ...f, industry: e.target.value }))}
              placeholder="e.g. SaaS, FinTech"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">Size</label>
            <input
              type="text"
              value={form.size}
              onChange={(e) => setForm((f) => ({ ...f, size: e.target.value }))}
              placeholder="e.g. 50-200"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">Location</label>
            <input
              type="text"
              value={form.location}
              onChange={(e) => setForm((f) => ({ ...f, location: e.target.value }))}
              placeholder="e.g. Amsterdam, NL"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">Phone</label>
            <input
              type="text"
              value={form.phone}
              onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))}
              placeholder="e.g. +31 20 123 4567"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">Email</label>
            <input
              type="email"
              value={form.email}
              onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
              placeholder="e.g. info@company.nl"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">KvK Number</label>
            <input
              type="text"
              value={form.kvk_number}
              onChange={(e) => setForm((f) => ({ ...f, kvk_number: e.target.value }))}
              placeholder="e.g. 12345678"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">Address</label>
            <input
              type="text"
              value={form.address}
              onChange={(e) => setForm((f) => ({ ...f, address: e.target.value }))}
              placeholder="e.g. Keizersgracht 1"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-sm font-medium">Postal Code</label>
              <input
                type="text"
                value={form.postal_code}
                onChange={(e) => setForm((f) => ({ ...f, postal_code: e.target.value }))}
                placeholder="e.g. 1015AB"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">City</label>
              <input
                type="text"
                value={form.city}
                onChange={(e) => setForm((f) => ({ ...f, city: e.target.value }))}
                placeholder="e.g. Amsterdam"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">Province</label>
            <input
              type="text"
              value={form.province}
              onChange={(e) => setForm((f) => ({ ...f, province: e.target.value }))}
              placeholder="e.g. Noord-Holland"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">LinkedIn URL</label>
            <input
              type="url"
              value={form.linkedin_url}
              onChange={(e) => setForm((f) => ({ ...f, linkedin_url: e.target.value }))}
              placeholder="e.g. https://linkedin.com/company/..."
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">Website URL</label>
            <input
              type="url"
              value={form.website_url}
              onChange={(e) => setForm((f) => ({ ...f, website_url: e.target.value }))}
              placeholder="e.g. https://www.company.nl"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">Status</label>
            <CustomSelect
              options={STATUS_OPTIONS}
              value={form.status}
              onChange={(v) =>
                setForm((f) => ({ ...f, status: String(v) as CompanyStatus }))
              }
            />
          </div>

          {update.isError && (
            <p className="text-sm text-destructive">Failed to update. Please try again.</p>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-input px-4 py-2 text-sm hover:bg-accent"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={update.isPending}
              className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-60 hover:opacity-90"
            >
              {update.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
              Save
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Monitor toggle ──────────────────────────────────────────────────────────────

function MonitorToggle({ company }: { company: { id: number; monitor: boolean; monitor_pinned: boolean; icp_score: number | null } }) {
  const update = useUpdateCompany();
  const isAuto = !company.monitor_pinned && company.icp_score !== null && company.icp_score >= 85;

  function handleToggle() {
    update.mutate({
      id: company.id,
      monitor: !company.monitor,
    });
  }

  return (
    <button
      type="button"
      onClick={handleToggle}
      disabled={update.isPending}
      title={
        company.monitor
          ? company.monitor_pinned
            ? "Monitoring (manually enabled) — click to disable"
            : "Monitoring (auto-enabled, ICP 85+) — click to pin off"
          : "Not monitoring — click to enable"
      }
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium transition-colors",
        company.monitor
          ? "bg-emerald-100 text-emerald-800 hover:bg-emerald-200"
          : "bg-muted text-muted-foreground hover:bg-accent",
      )}
    >
      {update.isPending ? (
        <Loader2 className="h-3 w-3 animate-spin" />
      ) : (
        <span className={cn("inline-block h-2 w-2 rounded-full", company.monitor ? "bg-emerald-500" : "bg-gray-400")} />
      )}
      {company.monitor ? "Monitoring" : "Not Monitored"}
      {isAuto && !company.monitor_pinned && (
        <span className="text-[10px] opacity-70">auto</span>
      )}
    </button>
  );
}

// ── Score bar ──────────────────────────────────────────────────────────────────

function ScoreBar({ label, value, weight }: { label: string; value: number; weight: number }) {
  const color =
    value >= 75
      ? "bg-green-500"
      : value >= 50
        ? "bg-yellow-500"
        : value >= 25
          ? "bg-orange-500"
          : "bg-gray-400";

  return (
    <div className="flex items-center gap-3">
      <span className="w-32 shrink-0 text-sm text-muted-foreground">
        {label} <span className="text-xs">({weight}%)</span>
      </span>
      <div className="flex-1 h-2 rounded-full bg-muted overflow-hidden">
        <div
          className={cn("h-full rounded-full transition-all", color)}
          style={{ width: `${Math.min(100, Math.max(0, value))}%` }}
        />
      </div>
      <span className="w-8 text-right text-sm font-medium tabular-nums">
        {value.toFixed(0)}
      </span>
    </div>
  );
}

// ── Overview tab ─────────────────────────────────────────────────────────────

function OverviewTab({
  company,
  onTabChange,
}: {
  company: ReturnType<typeof useCompanyDetail>["data"];
  onTabChange: (tab: Tab) => void;
}) {
  const contactsQuery = useCompanyContacts(company!.id, { limit: 3 });
  const [hideNoSignal, setHideNoSignal] = useState(true);
  const signalsQuery = useCompanySignals(company!.id, {
    limit: 3,
    signal_type: hideNoSignal ? MEANINGFUL_SIGNAL_TYPES : undefined,
  });

  return (
    <div className="space-y-6">
      {/* Stats */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard
          label="Contacts"
          value={company!.contacts_count}
          onClick={() => onTabChange("contacts")}
        />
        <StatCard
          label="Signals"
          value={company!.signals_count}
          onClick={() => onTabChange("signals")}
        />
        <StatCard
          label="Last Signal"
          value={formatDate(company!.latest_signal_at)}
          onClick={() => onTabChange("signals")}
        />
      </div>

      {/* Lead Score Breakdown */}
      {company!.score_breakdown && (
        <section>
          <h3 className="mb-2 font-medium">Lead Score Breakdown</h3>
          <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
            <div className="mb-3 flex items-center justify-between">
              <span className="text-sm text-muted-foreground">
                Composite Score
              </span>
              <span className="text-2xl font-bold">
                {company!.lead_score?.toFixed(0) ?? "—"}
              </span>
            </div>
            <div className="space-y-2">
              <ScoreBar label="ICP Fit" value={company!.score_breakdown.icp_fit} weight={30} />
              <ScoreBar label="Signal Strength" value={company!.score_breakdown.signal_strength} weight={35} />
              <ScoreBar label="Contact Quality" value={company!.score_breakdown.contact_quality} weight={20} />
              <ScoreBar label="Recency" value={company!.score_breakdown.recency} weight={15} />
            </div>
            {company!.score_updated_at && (
              <p className="mt-3 text-xs text-muted-foreground">
                Last calculated: {formatDateTime(company!.score_updated_at)}
              </p>
            )}
          </div>
        </section>
      )}

      {/* Recent contacts */}
      <section>
        <div className="mb-2 flex items-center justify-between">
          <h3 className="font-medium">Recent Contacts</h3>
          {(contactsQuery.data?.total ?? 0) > 3 && (
            <button
              type="button"
              onClick={() => onTabChange("contacts")}
              className="text-sm text-primary hover:underline"
            >
              View all
            </button>
          )}
        </div>
        {contactsQuery.isLoading ? (
          <LoadingRows count={3} />
        ) : contactsQuery.data?.items.length === 0 ? (
          <p className="text-sm text-muted-foreground">No contacts yet.</p>
        ) : (
          <div className="space-y-2">
            {contactsQuery.data?.items.map((c) => (
              <div
                key={c.id}
                className="flex items-start justify-between rounded-md border border-border bg-card p-3"
              >
                <div>
                  <p className="font-medium">{c.name}</p>
                  {c.title && (
                    <p className="text-sm text-muted-foreground">{c.title}</p>
                  )}
                  {c.email && (
                    <p className="flex items-center text-sm text-muted-foreground">
                      {c.email}
                      <CopyButton text={c.email} />
                    </p>
                  )}
                </div>
                {c.email_status && <EmailStatusBadge status={c.email_status} />}
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Recent signals */}
      <section>
        <div className="mb-2 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <h3 className="font-medium">Recent Signals</h3>
            <label className="inline-flex cursor-pointer items-center gap-1.5 text-xs">
              <input
                type="checkbox"
                checked={hideNoSignal}
                onChange={(e) => setHideNoSignal(e.target.checked)}
                className="h-3.5 w-3.5 rounded border-input accent-primary"
              />
              <span className="text-muted-foreground">Hide &ldquo;No Signal&rdquo;</span>
            </label>
          </div>
          {(signalsQuery.data?.total ?? 0) > 3 && (
            <button
              type="button"
              onClick={() => onTabChange("signals")}
              className="text-sm text-primary hover:underline"
            >
              View all
            </button>
          )}
        </div>
        {signalsQuery.isLoading ? (
          <LoadingRows count={3} />
        ) : signalsQuery.data?.items.length === 0 ? (
          <p className="text-sm text-muted-foreground">No signals yet.</p>
        ) : (
          <div className="space-y-2">
            {signalsQuery.data?.items.map((s) => (
              <div
                key={s.id}
                className="rounded-md border border-border bg-card p-3"
              >
                <div className="mb-1 flex flex-wrap items-center gap-2">
                  <SignalTypeBadge type={s.signal_type} />
                  {s.relevance_score != null && (
                    <ScoreBadge score={s.relevance_score} />
                  )}
                  {s.action_taken && <SignalActionBadge action={s.action_taken} />}
                  <span className="ml-auto text-xs text-muted-foreground">
                    {formatDate(s.created_at)}
                  </span>
                </div>
                {s.llm_summary && (
                  <p className="text-sm text-muted-foreground">{s.llm_summary}</p>
                )}
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function StatCard({
  label,
  value,
  onClick,
}: {
  label: string;
  value: string | number;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-xl border border-border bg-card p-4 shadow-sm text-left transition-colors hover:bg-accent/50"
    >
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="mt-1 text-2xl font-semibold">{value}</p>
    </button>
  );
}

// ── Business Details tab ─────────────────────────────────────────────────────

function BusinessDetailsTab({ company }: { company: CompanyDetailResponse }) {
  const bd = company.bedrijfsdata;

  const hasRegistration = company.kvk_number || company.organization_type || company.founded_year || bd?.btwnummer || bd?.vestigingstype;
  const hasAddress = company.address || company.postal_code || company.city || company.province || company.country || bd?.gemeente || bd?.coordinaten;
  const hasContact = company.phone || company.email || company.website_url;
  const hasSocial = company.linkedin_url || company.facebook_url || company.twitter_url || bd?.youtube_link || bd?.instagram_link || bd?.pinterest_link;
  const hasTech = bd?.cms || bd?.website_analytics || bd?.cdn || bd?.advertentienetwerken || bd?.caching_server || bd?.webshop || bd?.emailprovider || bd?.apps;
  const hasAnything = hasRegistration || hasAddress || hasContact || hasSocial || hasTech || bd?.bedrijfsprofiel || bd?.sbi_codes;

  if (!hasAnything) {
    return <EmptyState message="No business details available yet. Import a Bedrijfsdata Excel or run discovery to populate." />;
  }

  const socialLinks: { label: string; url: string }[] = [];
  if (company.linkedin_url) socialLinks.push({ label: "LinkedIn", url: company.linkedin_url });
  if (company.facebook_url) socialLinks.push({ label: "Facebook", url: company.facebook_url });
  if (company.twitter_url) socialLinks.push({ label: "Twitter / X", url: company.twitter_url });
  if (bd?.youtube_link) socialLinks.push({ label: "YouTube", url: bd.youtube_link });
  if (bd?.instagram_link) socialLinks.push({ label: "Instagram", url: bd.instagram_link });
  if (bd?.pinterest_link) socialLinks.push({ label: "Pinterest", url: bd.pinterest_link });

  const techItems: { label: string; value: string }[] = [];
  if (bd?.cms) techItems.push({ label: "CMS", value: bd.cms });
  if (bd?.website_analytics) techItems.push({ label: "Analytics", value: bd.website_analytics });
  if (bd?.cdn) techItems.push({ label: "CDN", value: bd.cdn });
  if (bd?.advertentienetwerken) techItems.push({ label: "Ad Networks", value: bd.advertentienetwerken });
  if (bd?.caching_server) techItems.push({ label: "Caching", value: bd.caching_server });
  if (bd?.webshop) techItems.push({ label: "Webshop", value: bd.webshop });
  if (bd?.emailprovider) techItems.push({ label: "Email Provider", value: bd.emailprovider });

  return (
    <div className="space-y-6">
      {/* Registration & Legal */}
      {hasRegistration && (
        <section className="rounded-xl border border-border bg-card p-5 shadow-sm">
          <h3 className="mb-3 font-medium">Registration & Legal</h3>
          <div className="grid grid-cols-1 gap-x-8 gap-y-2 text-sm sm:grid-cols-2 lg:grid-cols-3">
            {company.kvk_number && <DetailRow label="KvK Number" value={company.kvk_number} />}
            {bd?.btwnummer && <DetailRow label="BTW Number" value={bd.btwnummer} />}
            {company.organization_type && <DetailRow label="Organization Type" value={company.organization_type} />}
            {bd?.vestigingstype && <DetailRow label="Establishment Type" value={bd.vestigingstype} />}
            {company.founded_year && <DetailRow label="Founded" value={String(company.founded_year)} />}
            {company.employee_count != null && <DetailRow label="Employees" value={String(company.employee_count)} />}
            {company.size && <DetailRow label="Employee Range" value={company.size} />}
          </div>
        </section>
      )}

      {/* Address */}
      {hasAddress && (
        <section className="rounded-xl border border-border bg-card p-5 shadow-sm">
          <h3 className="mb-3 font-medium">Address</h3>
          <div className="grid grid-cols-1 gap-x-8 gap-y-2 text-sm sm:grid-cols-2 lg:grid-cols-3">
            {company.address && <DetailRow label="Street" value={company.address} />}
            {company.postal_code && <DetailRow label="Postal Code" value={company.postal_code} />}
            {company.city && <DetailRow label="City" value={company.city} />}
            {bd?.gemeente && <DetailRow label="Municipality" value={bd.gemeente} />}
            {company.province && <DetailRow label="Province" value={company.province} />}
            {company.country && <DetailRow label="Country" value={company.country} />}
            {bd?.coordinaten && <DetailRow label="Coordinates" value={bd.coordinaten} />}
          </div>
        </section>
      )}

      {/* Contact */}
      {hasContact && (
        <section className="rounded-xl border border-border bg-card p-5 shadow-sm">
          <h3 className="mb-3 font-medium">Contact Information</h3>
          <div className="grid grid-cols-1 gap-x-8 gap-y-2 text-sm sm:grid-cols-2">
            {company.phone && (
              <div className="flex items-center gap-1">
                <span className="text-muted-foreground">Phone:</span>
                <span>{company.phone}</span>
                <CopyButton text={company.phone} />
              </div>
            )}
            {company.email && (
              <div className="flex items-center gap-1">
                <span className="text-muted-foreground">Email:</span>
                <span>{company.email}</span>
                <CopyButton text={company.email} />
              </div>
            )}
            {company.website_url && (
              <div>
                <span className="text-muted-foreground">Website: </span>
                <a href={company.website_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-primary hover:underline">
                  {company.website_url} <ExternalLink className="h-3 w-3" />
                </a>
              </div>
            )}
          </div>
        </section>
      )}

      {/* Social Media */}
      {hasSocial && socialLinks.length > 0 && (
        <section className="rounded-xl border border-border bg-card p-5 shadow-sm">
          <h3 className="mb-3 font-medium">Social Media</h3>
          <div className="flex flex-wrap gap-3">
            {socialLinks.map((link) => (
              <a
                key={link.label}
                href={link.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 rounded-lg border border-input bg-background px-3 py-1.5 text-sm font-medium hover:bg-accent"
              >
                {link.label}
                <ExternalLink className="h-3 w-3" />
              </a>
            ))}
          </div>
        </section>
      )}

      {/* Tech Stack */}
      {hasTech && (
        <section className="rounded-xl border border-border bg-card p-5 shadow-sm">
          <h3 className="mb-3 font-medium">Technology Stack</h3>
          {techItems.length > 0 && (
            <div className="mb-4 grid grid-cols-1 gap-x-8 gap-y-2 text-sm sm:grid-cols-2 lg:grid-cols-3">
              {techItems.map((item) => (
                <DetailRow key={item.label} label={item.label} value={item.value} />
              ))}
            </div>
          )}
          {bd?.apps && (
            <div>
              <p className="mb-2 text-xs uppercase tracking-wide text-muted-foreground">All Detected Technologies</p>
              <div className="flex flex-wrap gap-2">
                {bd.apps.split(",").map((app) => (
                  <span
                    key={app}
                    className="rounded-full bg-muted px-3 py-1 text-xs font-medium"
                  >
                    {app.trim()}
                  </span>
                ))}
              </div>
            </div>
          )}
        </section>
      )}

      {/* SBI Codes */}
      {bd?.sbi_codes && (
        <section className="rounded-xl border border-border bg-card p-5 shadow-sm">
          <h3 className="mb-3 font-medium">SBI Codes</h3>
          <div className="flex flex-wrap gap-2">
            {bd.sbi_codes.split(",").map((code) => (
              <span key={code} className="rounded-full bg-muted px-3 py-1 text-xs font-medium">
                {code.trim()}
              </span>
            ))}
          </div>
        </section>
      )}

      {/* Bedrijfsprofiel link */}
      {bd?.bedrijfsprofiel && (
        <section className="rounded-xl border border-border bg-card p-5 shadow-sm">
          <h3 className="mb-3 font-medium">Company Profile</h3>
          <a
            href={bd.bedrijfsprofiel}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
          >
            View on Bedrijfsdata <ExternalLink className="h-3 w-3" />
          </a>
        </section>
      )}
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span className="text-muted-foreground">{label}: </span>
      <span>{value}</span>
    </div>
  );
}

// ── Company Info tab ──────────────────────────────────────────────────────────

function CompanyInfoTab({
  companyInfo,
}: {
  companyInfo: CompanyInfo | null;
}) {
  if (!companyInfo) {
    return (
      <EmptyState message="No company profile available yet. Trigger enrichment to generate one." />
    );
  }

  return (
    <div className="space-y-6">
      {/* Summary */}
      <section className="rounded-xl border border-border bg-card p-5 shadow-sm">
        <h3 className="mb-2 font-medium">Summary</h3>
        <p className="text-sm leading-relaxed text-muted-foreground">
          {companyInfo.summary}
        </p>
      </section>

      {/* Structured fields */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {companyInfo.products_services && (
          <InfoCard
            title="Products & Services"
            content={companyInfo.products_services}
          />
        )}
        {companyInfo.target_market && (
          <InfoCard title="Target Market" content={companyInfo.target_market} />
        )}
        {companyInfo.company_culture && (
          <InfoCard
            title="Culture & Values"
            content={companyInfo.company_culture}
          />
        )}
        {companyInfo.technologies.length > 0 && (
          <section className="rounded-xl border border-border bg-card p-5 shadow-sm">
            <h3 className="mb-2 font-medium">Technologies</h3>
            <div className="flex flex-wrap gap-2">
              {companyInfo.technologies.map((tech) => (
                <span
                  key={tech}
                  className="rounded-full bg-muted px-3 py-1 text-xs font-medium"
                >
                  {tech}
                </span>
              ))}
            </div>
          </section>
        )}
      </div>

      {/* Quick facts */}
      {(companyInfo.headquarters ||
        companyInfo.founded_year ||
        companyInfo.employee_count_estimate) && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {companyInfo.headquarters && (
            <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">
                Headquarters
              </p>
              <p className="mt-1 font-medium">{companyInfo.headquarters}</p>
            </div>
          )}
          {companyInfo.founded_year && (
            <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">
                Founded
              </p>
              <p className="mt-1 font-medium">{companyInfo.founded_year}</p>
            </div>
          )}
          {companyInfo.employee_count_estimate && (
            <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">
                Employees
              </p>
              <p className="mt-1 font-medium">
                {companyInfo.employee_count_estimate}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function InfoCard({ title, content }: { title: string; content: string }) {
  return (
    <section className="rounded-xl border border-border bg-card p-5 shadow-sm">
      <h3 className="mb-2 font-medium">{title}</h3>
      <p className="text-sm leading-relaxed text-muted-foreground">{content}</p>
    </section>
  );
}

// ── Contacts tab ──────────────────────────────────────────────────────────────

function ContactsTab({ companyId }: { companyId: number }) {
  const [offset, setOffset] = useState(0);
  const { data, isLoading } = useCompanyContacts(companyId, {
    offset,
    limit: PAGE_SIZE,
  });

  if (isLoading) return <LoadingRows count={4} />;
  if (!data || data.items.length === 0) {
    return <EmptyState message="No contacts found for this company." />;
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        {data.items.map((contact) => (
          <div
            key={contact.id}
            className="rounded-xl border border-border bg-card p-4 shadow-sm"
          >
            <div className="mb-2 flex items-start justify-between gap-2">
              <div>
                <div className="flex items-center gap-2">
                  <p className="font-medium">{contact.name}</p>
                  {contact.clickup_task_url && (
                    <a
                      href={contact.clickup_task_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 rounded bg-violet-500/10 px-1.5 py-0.5 text-[10px] font-medium text-violet-600 hover:bg-violet-500/20"
                      title="View in ClickUp"
                    >
                      ClickUp
                      <ExternalLink className="h-2.5 w-2.5" />
                    </a>
                  )}
                </div>
                {contact.title && (
                  <p className="text-sm text-muted-foreground">{contact.title}</p>
                )}
              </div>
              {contact.email_status && (
                <EmailStatusBadge status={contact.email_status} />
              )}
            </div>

            <div className="space-y-1 text-sm">
              {contact.email && (
                <div className="flex items-center text-muted-foreground">
                  <span className="w-16 shrink-0 text-xs uppercase tracking-wide">
                    Email
                  </span>
                  <span>{contact.email}</span>
                  <CopyButton text={contact.email} />
                </div>
              )}
              {contact.phone && (
                <div className="flex items-center text-muted-foreground">
                  <span className="w-16 shrink-0 text-xs uppercase tracking-wide">
                    Phone
                  </span>
                  <span>{contact.phone}</span>
                </div>
              )}
              {contact.linkedin_url && (
                <div className="flex items-center text-muted-foreground">
                  <span className="w-16 shrink-0 text-xs uppercase tracking-wide">
                    LinkedIn
                  </span>
                  <a
                    href={contact.linkedin_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-primary hover:underline"
                  >
                    View profile
                    <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
              )}
              {contact.source && (
                <div className="flex items-center text-muted-foreground">
                  <span className="w-16 shrink-0 text-xs uppercase tracking-wide">
                    Source
                  </span>
                  <span className="capitalize">{contact.source}</span>
                  {contact.confidence_score != null && (
                    <span className="ml-2 text-xs">
                      ({Math.round(contact.confidence_score * 100)}% confidence)
                    </span>
                  )}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      <Pagination
        offset={offset}
        limit={PAGE_SIZE}
        total={data.total}
        onOffsetChange={setOffset}
      />
    </div>
  );
}

// ── Signals tab ───────────────────────────────────────────────────────────────

function SignalsTab({ companyId }: { companyId: number }) {
  const [offset, setOffset] = useState(0);
  const [hideNoSignal, setHideNoSignal] = useState(true);
  const { data, isLoading } = useCompanySignals(companyId, {
    offset,
    limit: PAGE_SIZE,
    signal_type: hideNoSignal ? MEANINGFUL_SIGNAL_TYPES : undefined,
  });

  return (
    <div className="space-y-4">
      <label className="inline-flex cursor-pointer items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={hideNoSignal}
          onChange={(e) => {
            setHideNoSignal(e.target.checked);
            setOffset(0);
          }}
          className="h-4 w-4 rounded border-input accent-primary"
        />
        <span className="text-muted-foreground">Hide &ldquo;No Signal&rdquo; rows</span>
      </label>

      {isLoading ? (
        <LoadingRows count={4} />
      ) : !data || data.items.length === 0 ? (
        <EmptyState message="No signals detected for this company." />
      ) : (
        <>
          <div className="relative border-l-2 border-border pl-4 space-y-4">
            {data.items.map((signal) => (
              <div key={signal.id} className="relative">
                <div className="absolute -left-[21px] mt-1 h-3 w-3 rounded-full border-2 border-border bg-background" />
                <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <SignalTypeBadge type={signal.signal_type} />
                    {signal.relevance_score != null && (
                      <ScoreBadge score={signal.relevance_score} />
                    )}
                    {signal.action_taken && (
                      <SignalActionBadge action={signal.action_taken} />
                    )}
                    <span className="ml-auto text-xs text-muted-foreground">
                      {formatDateTime(signal.created_at)}
                    </span>
                  </div>
                  {signal.llm_summary && (
                    <p className="text-sm text-muted-foreground">{signal.llm_summary}</p>
                  )}
                  {signal.source_url && (
                    <div className="mt-2 space-y-0.5">
                      {signal.source_title && (
                        <p className="text-xs font-medium text-foreground">{signal.source_title}</p>
                      )}
                      <a
                        href={signal.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
                      >
                        {signal.source_title ? "Open page" : "View source"}
                        <ExternalLink className="h-3 w-3" />
                      </a>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>

          <Pagination
            offset={offset}
            limit={PAGE_SIZE}
            total={data.total}
            onOffsetChange={setOffset}
          />
        </>
      )}
    </div>
  );
}

// ── Scrape jobs tab ───────────────────────────────────────────────────────────

function ScrapeJobsTab({ companyId }: { companyId: number }) {
  const [offset, setOffset] = useState(0);
  const { data, isLoading } = useCompanyScrapeJobs(companyId, {
    offset,
    limit: PAGE_SIZE,
  });

  if (isLoading) return <LoadingRows count={3} />;
  if (!data || data.items.length === 0) {
    return <EmptyState message="No scrape jobs found for this company." />;
  }

  return (
    <div className="space-y-4">
      <div className="overflow-x-auto rounded-xl border border-border bg-card shadow-sm">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/40">
              <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                Target URL
              </th>
              <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                Status
              </th>
              <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                Pages
              </th>
              <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                Credits
              </th>
              <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                Started
              </th>
              <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                Completed
              </th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((job) => (
              <tr
                key={job.id}
                className="border-b border-border last:border-0 hover:bg-muted/30"
              >
                <td className="max-w-xs px-4 py-3">
                  <a
                    href={job.target_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-primary hover:underline"
                    title={job.target_url}
                  >
                    <span className="max-w-[180px] truncate">{job.target_url}</span>
                    <ExternalLink className="h-3 w-3 shrink-0" />
                  </a>
                </td>
                <td className="px-4 py-3">
                  <ScrapeJobStatusBadge status={job.status} />
                </td>
                <td className="px-4 py-3 text-muted-foreground">
                  {job.pages_scraped ?? "—"}
                </td>
                <td className="px-4 py-3 text-muted-foreground">
                  {job.credits_used != null ? job.credits_used.toFixed(3) : "—"}
                </td>
                <td className="px-4 py-3 text-muted-foreground">
                  {formatDateTime(job.started_at)}
                </td>
                <td className="px-4 py-3 text-muted-foreground">
                  {formatDateTime(job.completed_at)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {data.items.some((j) => j.error_message) && (
        <div className="space-y-2">
          {data.items
            .filter((j) => j.error_message)
            .map((j) => (
              <div
                key={j.id}
                className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive"
              >
                <span className="font-medium">Job #{j.id} error:</span>{" "}
                {j.error_message}
              </div>
            ))}
        </div>
      )}

      <Pagination
        offset={offset}
        limit={PAGE_SIZE}
        total={data.total}
        onOffsetChange={setOffset}
      />
    </div>
  );
}

// ── Shared UI bits ────────────────────────────────────────────────────────────

function LoadingRows({ count }: { count: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="h-14 animate-pulse rounded-md bg-muted"
        />
      ))}
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border py-12 text-center">
      <Building2 className="mb-3 h-8 w-8 text-muted-foreground" />
      <p className="text-sm text-muted-foreground">{message}</p>
    </div>
  );
}

function MutationFeedback({
  mutation,
  successMessage,
  errorMessage = "Failed to trigger action. Is the task queue running?",
}: {
  mutation: { isSuccess: boolean; isError: boolean };
  successMessage: string;
  errorMessage?: string;
}) {
  if (mutation.isSuccess) {
    return <p className="mt-2 text-sm text-green-600">{successMessage}</p>;
  }
  if (mutation.isError) {
    return <p className="mt-2 text-sm text-destructive">{errorMessage}</p>;
  }
  return null;
}

// ── Main component ────────────────────────────────────────────────────────────

export default function CompanyDetail() {
  const { id } = useParams<{ id: string }>();
  const companyId = Number(id);

  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab = (searchParams.get("tab") as Tab | null) ?? "overview";
  const [editOpen, setEditOpen] = useState(false);
  const [archiveConfirm, setArchiveConfirm] = useState(false);

  const { data: company, isLoading, isError } = useCompanyDetail(companyId);
  const { hasActiveICP } = useHasActiveICP();
  const enrichMutation = useTriggerEnrichment(companyId);
  const scrapeMutation = useTriggerScrape(companyId);
  const contactsMutation = useTriggerContacts(companyId);
  const pipelineMutation = useTriggerPipeline(companyId);
  const linkedinScrapeMutation = useTriggerLinkedInScrape(companyId);
  const crmMutation = usePushToCRM(companyId);
  const deleteMutation = useDeleteCompany();
  const crmStatusQuery = useCRMStatusSync(
    companyId,
    !!company?.crm_integration,
  );
  const queryClient = useQueryClient();
  const enrichmentJobsQuery = useCompanyEnrichmentJobs(companyId);
  const latestEnrichmentJob = enrichmentJobsQuery.data?.items[0] ?? null;
  const enrichmentRunning =
    latestEnrichmentJob?.status === "pending" || latestEnrichmentJob?.status === "running";

  const scrapeJobsQuery = useCompanyScrapeJobs(companyId);
  const latestScrapeJob = scrapeJobsQuery.data?.items[0] ?? null;
  const scrapeRunning =
    latestScrapeJob?.status === "pending" || latestScrapeJob?.status === "running";

  // Invalidate company detail cache when CRM status differs from local
  useEffect(() => {
    if (crmStatusQuery.data && company?.crm_integration) {
      if (company.crm_integration.external_status !== crmStatusQuery.data.status) {
        queryClient.invalidateQueries({ queryKey: ["companies", companyId] });
      }
    }
  }, [crmStatusQuery.data, company, companyId, queryClient]);

  // Auto-refresh detail + signals when jobs finish
  const prevEnrichmentRunning = usePrevious(enrichmentRunning);
  const prevScrapeRunning = usePrevious(scrapeRunning);
  useEffect(() => {
    if (prevEnrichmentRunning && !enrichmentRunning) {
      queryClient.invalidateQueries({ queryKey: ["companies", companyId] });
    }
  }, [enrichmentRunning, prevEnrichmentRunning, companyId, queryClient]);
  useEffect(() => {
    if (prevScrapeRunning && !scrapeRunning) {
      queryClient.invalidateQueries({ queryKey: ["companies", companyId] });
    }
  }, [scrapeRunning, prevScrapeRunning, companyId, queryClient]);

  const [refreshing, setRefreshing] = useState(false);
  async function handleRefresh() {
    setRefreshing(true);
    await queryClient.invalidateQueries({ queryKey: ["companies", companyId] });
    setRefreshing(false);
  }

  function setTab(tab: Tab) {
    setSearchParams({ tab }, { replace: true });
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (isError || !company) {
    return (
      <div className="py-12 text-center">
        <p className="text-muted-foreground">Company not found.</p>
        <Link to="/companies" className="mt-2 text-sm text-primary hover:underline">
          ← Back to companies
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-2 text-sm text-muted-foreground">
        <Link to="/" className="hover:text-foreground">
          Dashboard
        </Link>
        <span>/</span>
        <Link to="/companies" className="hover:text-foreground">
          Companies
        </Link>
        <span>/</span>
        <span className="text-foreground">{company.name}</span>
      </nav>

      {/* Company header */}
      <div className="rounded-xl border border-border bg-card p-6 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4">
          {/* Left: name, domain, meta */}
          <div className="space-y-1">
            <h1 className="text-2xl tracking-tight">{company.name}</h1>
            <div className="flex flex-wrap items-center gap-3">
              <a
                href={`https://${company.domain}`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
              >
                {company.domain}
                <ExternalLink className="h-3 w-3" />
              </a>
              {company.industry && (
                <span className="text-sm text-muted-foreground">
                  {company.industry}
                </span>
              )}
              {company.size && (
                <span className="text-sm text-muted-foreground">{company.size}</span>
              )}
              {company.location && (
                <span className="text-sm text-muted-foreground">
                  {company.location}
                </span>
              )}
              {company.linkedin_url && (
                <a
                  href={company.linkedin_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
                >
                  LinkedIn
                  <ExternalLink className="h-3 w-3" />
                </a>
              )}
            </div>
            {/* Contact details row */}
            {(company.phone || company.email || company.kvk_number || company.facebook_url || company.twitter_url) && (
              <div className="flex flex-wrap items-center gap-3">
                {company.kvk_number && (
                  <span className="text-sm text-muted-foreground">
                    KvK: {company.kvk_number}
                  </span>
                )}
                {company.phone && (
                  <span className="inline-flex items-center gap-1 text-sm text-muted-foreground">
                    {company.phone}
                    <CopyButton text={company.phone} />
                  </span>
                )}
                {company.email && (
                  <span className="inline-flex items-center gap-1 text-sm text-muted-foreground">
                    {company.email}
                    <CopyButton text={company.email} />
                  </span>
                )}
                {company.facebook_url && (
                  <a href={company.facebook_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-sm text-primary hover:underline">
                    Facebook <ExternalLink className="h-3 w-3" />
                  </a>
                )}
                {company.twitter_url && (
                  <a href={company.twitter_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-sm text-primary hover:underline">
                    Twitter <ExternalLink className="h-3 w-3" />
                  </a>
                )}
              </div>
            )}
          </div>

          {/* Right: badges + monitor toggle */}
          <div className="flex flex-wrap items-center gap-2">
            <MonitorToggle company={company} />
            <LeadScoreBadge score={company.lead_score} />
            <ScoreBadge score={company.icp_score} />
            <StatusBadge status={company.status} />
            {enrichmentRunning && (
              <span className="inline-flex items-center gap-1 rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-800">
                <Loader2 className="h-3 w-3 animate-spin" />
                Enriching…
              </span>
            )}
            {company.crm_integration && (
              <a
                href={company.crm_integration.external_url ?? "#"}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 rounded-full bg-violet-100 px-2 py-0.5 text-xs font-medium text-violet-800 hover:bg-violet-200 transition-colors"
              >
                {company.crm_integration.provider.charAt(0).toUpperCase() + company.crm_integration.provider.slice(1)}
                {company.crm_integration.external_status ? `: ${company.crm_integration.external_status}` : ""}
                {crmStatusQuery.isFetching && (
                  <Loader2 className="h-3 w-3 animate-spin" />
                )}
                <ExternalLink className="h-3 w-3" />
              </a>
            )}
          </div>
        </div>

        {/* Action buttons */}
        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={handleRefresh}
            disabled={refreshing}
            className="inline-flex items-center gap-2 rounded-md border border-input bg-background px-3 py-1.5 text-sm font-medium hover:bg-accent disabled:opacity-50"
            title="Refresh all data"
          >
            <RefreshCw className={cn("h-4 w-4", refreshing && "animate-spin")} />
          </button>
          <button
            type="button"
            onClick={() => setEditOpen(true)}
            className="inline-flex items-center gap-2 rounded-md border border-input bg-background px-3 py-1.5 text-sm font-medium hover:bg-accent"
          >
            <Pencil className="h-4 w-4" />
            Edit Company
          </button>
          <button
            type="button"
            disabled={!hasActiveICP || scrapeMutation.isPending || scrapeRunning}
            onClick={() => scrapeMutation.mutate()}
            className="inline-flex items-center gap-2 rounded-md border border-input bg-background px-3 py-1.5 text-sm font-medium hover:bg-accent disabled:opacity-50"
            title={!hasActiveICP ? "Activate an ICP profile first" : undefined}
          >
            {(scrapeMutation.isPending || scrapeRunning) ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : null}
            {scrapeMutation.isPending || scrapeRunning ? "Scraping..." : "Scrape"}
          </button>
          <button
            type="button"
            disabled={!hasActiveICP || enrichMutation.isPending || enrichmentRunning}
            onClick={() => enrichMutation.mutate()}
            className="inline-flex items-center gap-2 rounded-md border border-input bg-background px-3 py-1.5 text-sm font-medium hover:bg-accent disabled:opacity-50"
            title={!hasActiveICP ? "Activate an ICP profile first" : undefined}
          >
            {(enrichMutation.isPending || enrichmentRunning) ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : null}
            {enrichMutation.isPending || enrichmentRunning ? "Enriching..." : "Enrich"}
          </button>
          <button
            type="button"
            disabled={!hasActiveICP || contactsMutation.isPending}
            onClick={() => contactsMutation.mutate()}
            className="inline-flex items-center gap-2 rounded-md border border-input bg-background px-3 py-1.5 text-sm font-medium hover:bg-accent disabled:opacity-50"
            title={!hasActiveICP ? "Activate an ICP profile first" : undefined}
          >
            {contactsMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : null}
            {contactsMutation.isPending ? "Finding..." : "Find Contacts"}
          </button>
          <button
            type="button"
            disabled={linkedinScrapeMutation.isPending || !company.linkedin_url}
            onClick={() => linkedinScrapeMutation.mutate()}
            className="inline-flex items-center gap-2 rounded-md border border-input bg-background px-3 py-1.5 text-sm font-medium hover:bg-accent disabled:opacity-50"
            title={company.linkedin_url ? `Scrape ${company.linkedin_url}` : "No LinkedIn URL — scrape website first"}
          >
            {linkedinScrapeMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : null}
            {linkedinScrapeMutation.isPending ? "Scraping LinkedIn..." : "LinkedIn Scrape"}
          </button>
          <button
            type="button"
            disabled={!hasActiveICP || pipelineMutation.isPending || scrapeRunning || enrichmentRunning}
            onClick={() => pipelineMutation.mutate()}
            className="inline-flex items-center gap-2 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            title={!hasActiveICP ? "Activate an ICP profile first" : undefined}
          >
            {(pipelineMutation.isPending || scrapeRunning || enrichmentRunning) ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : null}
            {pipelineMutation.isPending ? "Running..." : "Full Pipeline"}
          </button>
          <button
            type="button"
            disabled={crmMutation.isPending}
            onClick={() => crmMutation.mutate()}
            className="inline-flex items-center gap-2 rounded-md border border-input bg-background px-3 py-1.5 text-sm font-medium hover:bg-accent disabled:opacity-50"
          >
            {crmMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : null}
            {crmMutation.isPending
              ? "Pushing..."
              : company.crm_integration
                ? "Update CRM"
                : "Push to CRM"}
          </button>
          <button
            type="button"
            onClick={() => setArchiveConfirm(true)}
            className="inline-flex items-center gap-2 rounded-md border border-destructive/30 bg-background px-3 py-1.5 text-sm font-medium text-destructive hover:bg-destructive/10 disabled:opacity-50"
          >
            <Trash2 className="h-4 w-4" />
            Archive
          </button>
        </div>

        {/* Action feedback */}
        <MutationFeedback mutation={scrapeMutation} successMessage="Scrape task dispatched — check the Scrape Jobs tab for progress." />
        <MutationFeedback mutation={enrichMutation} successMessage="Enrichment task dispatched — company profile and signals will be analyzed." />
        <MutationFeedback mutation={contactsMutation} successMessage="Contact finding task dispatched — contacts will appear shortly." />
        <MutationFeedback mutation={linkedinScrapeMutation} successMessage="LinkedIn scrape task dispatched — signals will appear after processing." />
        <MutationFeedback mutation={pipelineMutation} successMessage="Full pipeline dispatched: scrape → enrich → find contacts." />
        {crmMutation.isSuccess && (
          <p className="mt-2 text-sm text-green-600">
            Company {company.crm_integration ? "updated in" : "pushed to"} CRM.
          </p>
        )}
        {crmMutation.isError && (
          <p className="mt-2 text-sm text-destructive">
            Failed to push to CRM. Check integration configuration.
          </p>
        )}
      </div>

      {/* Tabs */}
      <div>
        <div className="border-b border-border">
          <nav className="-mb-px flex gap-6">
            {TABS.map((tab) => (
              <button
                key={tab.value}
                type="button"
                onClick={() => setTab(tab.value)}
                className={cn(
                  "border-b-2 pb-3 text-sm font-medium transition-colors",
                  activeTab === tab.value
                    ? "border-primary text-primary"
                    : "border-transparent text-muted-foreground hover:text-foreground",
                )}
              >
                {tab.label}
              </button>
            ))}
          </nav>
        </div>

        <div className="pt-6">
          {activeTab === "overview" && (
            <OverviewTab company={company} onTabChange={setTab} />
          )}
          {activeTab === "business-details" && (
            <BusinessDetailsTab company={company} />
          )}
          {activeTab === "company-info" && (
            <CompanyInfoTab companyInfo={company.company_info} />
          )}
          {activeTab === "contacts" && <ContactsTab companyId={companyId} />}
          {activeTab === "signals" && <SignalsTab companyId={companyId} />}
          {activeTab === "scrape-jobs" && <ScrapeJobsTab companyId={companyId} />}
        </div>
      </div>

      {/* Edit modal */}
      {editOpen && (
        <EditModal company={company} onClose={() => setEditOpen(false)} />
      )}

      {/* Archive confirm dialog */}
      {archiveConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setArchiveConfirm(false)}>
          <div
            className="w-full max-w-sm rounded-xl border border-border bg-card p-6 shadow-xl animate-enter"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-lg font-semibold">Archive company</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              Are you sure you want to archive <strong>{company.name}</strong>? The company will be moved to the archived status.
            </p>
            <div className="mt-5 flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setArchiveConfirm(false)}
                className="rounded-lg border border-input px-4 py-2 text-sm font-medium transition-colors hover:bg-accent"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={deleteMutation.isPending}
                onClick={async () => {
                  await deleteMutation.mutateAsync(companyId);
                  navigate("/companies");
                }}
                className="inline-flex items-center gap-2 rounded-lg bg-destructive px-4 py-2 text-sm font-medium text-destructive-foreground transition-all hover:bg-destructive/90 disabled:opacity-50"
              >
                {deleteMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                Archive
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
