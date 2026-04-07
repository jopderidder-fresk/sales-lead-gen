import {
  useCompanies,
  useUpdateCompany,
  useCreateCompany,
  useImportCompanies,
  useBulkDeleteCompanies,
  useTriggerScrapeFromList,
  useTriggerPipelineFromList,
  type Company,
  type CompanyListParams,
  type CompanyStatus,
} from "@/lib/companies";
import { useHasActiveICP } from "@/lib/icp";
import { LeadScoreBadge, ScoreBadge, StatusBadge } from "@/components/badges";
import { cn } from "@/lib/utils";
import { Select, CustomSelect } from "@/components/Select";
import type { BulkImportResponse } from "@/types/api";
import {
  AlertCircle,
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  Building2,
  Calendar,
  Check,
  ChevronLeft,
  ChevronRight,
  Filter,
  Globe,
  Loader2,
  Plus,
  Search,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

// ── Constants ─────────────────────────────────────────────────────

const PAGE_SIZES = [10, 25, 50] as const;

const STATUS_OPTIONS: { value: CompanyStatus; label: string }[] = [
  { value: "discovered", label: "Discovered" },
  { value: "enriched", label: "Enriched" },
  { value: "monitoring", label: "Monitoring" },
  { value: "qualified", label: "Qualified" },
  { value: "pushed", label: "Pushed" },
];

const SORTABLE_COLUMNS = ["name", "icp_score", "lead_score", "created_at", "updated_at"] as const;
type SortColumn = (typeof SORTABLE_COLUMNS)[number];

function isSortable(col: string): col is SortColumn {
  return (SORTABLE_COLUMNS as readonly string[]).includes(col);
}

// ── Sort header ───────────────────────────────────────────────────

function SortHeader({
  label,
  column,
  currentSort,
  currentOrder,
  onSort,
}: {
  label: string;
  column: string;
  currentSort: string;
  currentOrder: "asc" | "desc";
  onSort: (col: string) => void;
}) {
  const active = currentSort === column;
  const sortable = isSortable(column);
  return (
    <button
      type="button"
      disabled={!sortable}
      onClick={() => sortable && onSort(column)}
      className={cn(
        "inline-flex items-center gap-1 text-xs font-medium uppercase tracking-wider text-muted-foreground",
        sortable && "cursor-pointer hover:text-foreground transition-colors",
      )}
    >
      {label}
      {sortable &&
        (active ? (
          currentOrder === "asc" ? (
            <ArrowUp className="h-3 w-3" />
          ) : (
            <ArrowDown className="h-3 w-3" />
          )
        ) : (
          <ArrowUpDown className="h-3 w-3 opacity-40" />
        ))}
    </button>
  );
}

// ── Loading skeleton ──────────────────────────────────────────────

function TableSkeleton({ rows }: { rows: number }) {
  return (
    <>
      {Array.from({ length: rows }).map((_, i) => (
        <tr key={i} className="animate-pulse">
          <td className="px-4 py-3.5">
            <div className="h-4 w-4 rounded bg-muted" />
          </td>
          <td className="px-4 py-3.5">
            <div className="h-4 w-32 rounded bg-muted" />
          </td>
          <td className="px-4 py-3.5">
            <div className="h-4 w-28 rounded bg-muted" />
          </td>
          <td className="px-4 py-3.5">
            <div className="h-4 w-20 rounded bg-muted" />
          </td>
          <td className="px-4 py-3.5">
            <div className="h-4 w-16 rounded bg-muted" />
          </td>
          <td className="px-4 py-3.5">
            <div className="h-5 w-10 rounded bg-muted" />
          </td>
          <td className="px-4 py-3.5">
            <div className="h-5 w-10 rounded bg-muted" />
          </td>
          <td className="px-4 py-3.5">
            <div className="h-5 w-16 rounded bg-muted" />
          </td>
          <td className="px-4 py-3.5">
            <div className="h-4 w-20 rounded bg-muted" />
          </td>
          <td className="px-4 py-3.5">
            <div className="h-4 w-6 rounded bg-muted" />
          </td>
        </tr>
      ))}
    </>
  );
}

// ── Empty state ───────────────────────────────────────────────────

function EmptyState({ hasFilters }: { hasFilters: boolean }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center animate-fade-in">
      <div className="rounded-2xl bg-muted p-5">
        <Building2 className="h-10 w-10 text-muted-foreground/50" />
      </div>
      <h3 className="mt-5 text-lg font-medium">
        {hasFilters ? "No companies match your filters" : "No companies yet"}
      </h3>
      <p className="mt-1.5 max-w-sm text-sm text-muted-foreground">
        {hasFilters
          ? "Try adjusting your filters or search query."
          : "Run a discovery job to find companies matching your ICP."}
      </p>
    </div>
  );
}

// ── Bulk action bar ───────────────────────────────────────────────

function BulkActionBar({
  count,
  onUpdateStatus,
  onDelete,
  onClear,
  loading,
  deleteLoading,
}: {
  count: number;
  onUpdateStatus: (status: CompanyStatus) => void;
  onDelete: () => void;
  onClear: () => void;
  loading: boolean;
  deleteLoading: boolean;
}) {
  const [statusOpen, setStatusOpen] = useState(false);

  return (
    <div className="flex items-center gap-3 rounded-xl border border-border bg-card px-4 py-2.5 shadow-sm animate-enter-up">
      <span className="text-sm font-medium tabular-nums">
        {count} selected
      </span>
      <div className="relative">
        <button
          type="button"
          onClick={() => setStatusOpen((o) => !o)}
          disabled={loading}
          className="inline-flex items-center gap-1 rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground transition-all hover:bg-primary/90 disabled:opacity-50"
        >
          {loading && <Loader2 className="h-3 w-3 animate-spin" />}
          Update Status
        </button>
        {statusOpen && (
          <div className="absolute left-0 z-20 mt-1.5 w-40 rounded-lg border border-border bg-card shadow-lg animate-enter">
            {STATUS_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => {
                  onUpdateStatus(opt.value);
                  setStatusOpen(false);
                }}
                className="block w-full px-3 py-2 text-left text-sm transition-colors hover:bg-accent first:rounded-t-lg last:rounded-b-lg"
              >
                <StatusBadge status={opt.value} />
              </button>
            ))}
          </div>
        )}
      </div>
      <button
        type="button"
        onClick={onDelete}
        disabled={deleteLoading}
        className="inline-flex items-center gap-1 rounded-lg bg-destructive px-3 py-1.5 text-xs font-medium text-destructive-foreground transition-all hover:bg-destructive/90 disabled:opacity-50"
      >
        {deleteLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Trash2 className="h-3 w-3" />}
        Delete
      </button>
      <button
        type="button"
        onClick={onClear}
        className="text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        Clear
      </button>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────

export default function Companies() {
  const { hasActiveICP } = useHasActiveICP();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // Parse URL params with validation
  const urlSearch = searchParams.get("search") ?? "";
  const rawStatus = searchParams.get("status");
  const urlStatus =
    rawStatus && STATUS_OPTIONS.some((o) => o.value === rawStatus)
      ? (rawStatus as CompanyStatus)
      : null;
  const urlIndustry = searchParams.get("industry") || null;
  const rawMinScoreStr = searchParams.get("min_score");
  const rawMinScore = rawMinScoreStr !== null ? Number(rawMinScoreStr) : NaN;
  const urlMinScore =
    rawMinScoreStr !== null && Number.isFinite(rawMinScore) && rawMinScore >= 0
      ? rawMinScore
      : null;
  const urlMonitor = searchParams.get("monitor") === "true" ? true : null;
  const urlAddedAfter = searchParams.get("added_after") || null;
  const urlAddedBefore = searchParams.get("added_before") || null;
  const rawSort = searchParams.get("sort") || "icp_score";
  const urlSort = isSortable(rawSort) ? rawSort : "icp_score";
  const rawOrder = searchParams.get("order");
  const urlOrder: "asc" | "desc" =
    rawOrder === "asc" || rawOrder === "desc" ? rawOrder : "desc";
  const rawLimit = Number(searchParams.get("limit"));
  const urlLimit =
    Number.isFinite(rawLimit) && rawLimit > 0 && rawLimit <= 100
      ? rawLimit
      : 25;
  const rawPage = Number(searchParams.get("page"));
  const urlPage =
    Number.isFinite(rawPage) && rawPage >= 1 ? Math.floor(rawPage) : 1;

  // Local search input (for debounce)
  const [searchInput, setSearchInput] = useState(urlSearch);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  // Sync search input when URL changes externally (e.g. browser back/forward)
  const prevUrlSearch = useRef(urlSearch);
  useEffect(() => {
    if (urlSearch !== prevUrlSearch.current) {
      prevUrlSearch.current = urlSearch;
      setSearchInput(urlSearch);
    }
  }, [urlSearch]);

  // Filters panel
  const [filtersOpen, setFiltersOpen] = useState(false);

  // Selection
  const [selected, setSelected] = useState<Set<number>>(new Set());

  // Sync search input debounce to URL
  const updateParam = useCallback(
    (key: string, value: string | null) => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        if (value) {
          next.set(key, value);
        } else {
          next.delete(key);
        }
        // Reset to page 1 on filter change
        if (key !== "page") next.delete("page");
        return next;
      });
    },
    [setSearchParams],
  );

  useEffect(() => {
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      if ((searchInput || null) !== (urlSearch || null)) {
        updateParam("search", searchInput || null);
      }
    }, 300);
    return () => clearTimeout(debounceRef.current);
  }, [searchInput, updateParam, urlSearch]);

  // Clear selection when filters/page/sort change
  useEffect(() => {
    setSelected(new Set());
  }, [urlPage, urlLimit, urlStatus, urlIndustry, urlMinScore, urlMonitor, urlSearch, urlAddedAfter, urlAddedBefore, urlSort, urlOrder]);

  // Build query params
  const queryParams: CompanyListParams = useMemo(
    () => ({
      offset: (urlPage - 1) * urlLimit,
      limit: urlLimit,
      status: urlStatus,
      industry: urlIndustry,
      min_score: urlMinScore,
      monitor: urlMonitor,
      search: urlSearch || null,
      added_after: urlAddedAfter,
      added_before: urlAddedBefore,
      sort: urlSort,
      order: urlOrder,
    }),
    [urlPage, urlLimit, urlStatus, urlIndustry, urlMinScore, urlMonitor, urlSearch, urlAddedAfter, urlAddedBefore, urlSort, urlOrder],
  );

  const { data, isLoading, isFetching, isError, isPlaceholderData } = useCompanies(queryParams);
  const updateCompany = useUpdateCompany();
  const createCompany = useCreateCompany();
  const importCompanies = useImportCompanies();
  const bulkDelete = useBulkDeleteCompanies();

  // Modal states
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [importModalOpen, setImportModalOpen] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const totalPages = data ? Math.max(1, Math.ceil(data.total / urlLimit)) : 1;
  const hasFilters = !!(urlSearch || urlStatus || urlIndustry || urlMinScore !== null || urlMonitor || urlAddedAfter || urlAddedBefore);

  // Sort toggle
  function handleSort(col: string) {
    if (urlSort === col) {
      updateParam("order", urlOrder === "asc" ? "desc" : "asc");
    } else {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        next.set("sort", col);
        next.set("order", "desc");
        next.delete("page");
        return next;
      });
    }
  }

  // Selection
  function toggleSelect(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleSelectAll() {
    if (!data) return;
    const allIds = data.items.map((c) => c.id);
    const allSelected = allIds.every((id) => selected.has(id));
    if (allSelected) {
      setSelected((prev) => {
        const next = new Set(prev);
        allIds.forEach((id) => next.delete(id));
        return next;
      });
    } else {
      setSelected((prev) => {
        const next = new Set(prev);
        allIds.forEach((id) => next.add(id));
        return next;
      });
    }
  }

  // Bulk status update — use allSettled so one failure doesn't abort the rest
  async function handleBulkUpdateStatus(status: CompanyStatus) {
    const ids = Array.from(selected);
    const results = await Promise.allSettled(
      ids.map((id) => updateCompany.mutateAsync({ id, status })),
    );
    const failures = results.filter((r) => r.status === "rejected");
    if (failures.length > 0) {
      console.error(`Bulk update: ${failures.length}/${ids.length} failed`);
    }
    setSelected(new Set());
  }

  // Bulk delete
  async function handleBulkDelete() {
    const ids = Array.from(selected);
    await bulkDelete.mutateAsync(ids);
    setSelected(new Set());
    setConfirmDelete(false);
  }

  // Clear filters
  function clearFilters() {
    setSearchParams({});
    setSearchInput("");
  }

  const allPageSelected =
    !!data && data.items.length > 0 && data.items.every((c) => selected.has(c.id));

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between animate-enter">
        <div>
          <h1 className="text-2xl tracking-tight">Companies</h1>
          <p className="mt-1 text-sm text-muted-foreground" style={{ fontFamily: '"DM Sans", system-ui, sans-serif' }}>
            Browse and manage your company list.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {isFetching && !isLoading && (
            <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
          )}
          <button
            type="button"
            onClick={() => setImportModalOpen(true)}
            className="inline-flex items-center gap-2 rounded-lg border border-input bg-card px-3 py-2 text-sm font-medium shadow-sm transition-all hover:bg-accent"
          >
            <Upload className="h-4 w-4" />
            Import Excel
          </button>
          <button
            type="button"
            onClick={() => setAddModalOpen(true)}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground shadow-sm transition-all hover:bg-primary/90"
          >
            <Plus className="h-4 w-4" />
            Add Company
          </button>
        </div>
      </div>

      {/* Search + filter toggle */}
      <div className="flex flex-wrap items-center gap-3 animate-enter" style={{ animationDelay: "60ms" }}>
        <div className="relative flex-1 min-w-[200px] max-w-md">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="Search by name or domain\u2026"
            className="w-full rounded-lg border border-input bg-card py-2.5 pl-9 pr-3 text-sm shadow-sm outline-none transition-shadow placeholder:text-muted-foreground focus:ring-2 focus:ring-ring/40 focus:shadow-md"
          />
          {searchInput && (
            <button
              type="button"
              onClick={() => setSearchInput("")}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
              <X className="h-3 w-3" />
            </button>
          )}
        </div>
        <button
          type="button"
          onClick={() => setFiltersOpen((o) => !o)}
          className={cn(
            "inline-flex items-center gap-2 rounded-lg border px-3 py-2.5 text-sm font-medium shadow-sm transition-all",
            filtersOpen || hasFilters
              ? "border-primary bg-primary/5 text-primary"
              : "border-input bg-card text-muted-foreground hover:bg-accent",
          )}
        >
          <Filter className="h-4 w-4" />
          Filters
          {hasFilters && (
            <span className="rounded-full bg-primary px-1.5 text-xs text-primary-foreground">
              {[urlSearch, urlStatus, urlIndustry, urlMinScore !== null ? urlMinScore : undefined, urlAddedAfter, urlAddedBefore].filter((v) => v != null && v !== "").length}
            </span>
          )}
        </button>
        {hasFilters && (
          <button
            type="button"
            onClick={clearFilters}
            className="text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            Clear all
          </button>
        )}
      </div>

      {/* Filters panel */}
      {filtersOpen && (
        <div className="relative z-10 rounded-xl border border-border bg-card p-5 shadow-sm animate-enter">
          <div className="grid grid-cols-1 gap-x-4 gap-y-4 sm:grid-cols-2 lg:grid-cols-4">
            {/* Status filter */}
            <div>
              <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                Status
              </label>
              <CustomSelect
                options={[
                  { value: "", label: "All statuses" },
                  ...STATUS_OPTIONS,
                ]}
                value={urlStatus ?? ""}
                onChange={(v) => updateParam("status", String(v) || null)}
                placeholder="All statuses"
              />
            </div>

            {/* Industry filter */}
            <div>
              <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                Industry
              </label>
              <input
                type="text"
                value={urlIndustry ?? ""}
                onChange={(e) => updateParam("industry", e.target.value || null)}
                placeholder="e.g. SaaS, FinTech"
                className="w-full rounded-lg border border-input bg-background px-3 py-2.5 text-sm outline-none transition-shadow placeholder:text-muted-foreground focus:ring-2 focus:ring-ring/40"
              />
            </div>

            {/* Min score filter */}
            <div>
              <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                Minimum Lead Score
              </label>
              <input
                type="number"
                min={0}
                max={100}
                value={urlMinScore ?? ""}
                onChange={(e) =>
                  updateParam("min_score", e.target.value || null)
                }
                placeholder="0"
                className="w-full rounded-lg border border-input bg-background px-3 py-2.5 text-sm outline-none transition-shadow placeholder:text-muted-foreground focus:ring-2 focus:ring-ring/40"
              />
            </div>

            {/* Monitor filter */}
            <div className="flex items-end">
              <label className="inline-flex cursor-pointer items-center gap-2 pb-1 text-sm">
                <input
                  type="checkbox"
                  checked={urlMonitor === true}
                  onChange={(e) => updateParam("monitor", e.target.checked ? "true" : null)}
                  className="h-4 w-4 rounded border-input accent-primary"
                />
                <span className="inline-flex items-center gap-1.5">
                  <span className="inline-block h-2 w-2 rounded-full bg-emerald-500" />
                  Monitored only
                </span>
              </label>
            </div>

            {/* Added date range filter */}
            <div>
              <label className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                <Calendar className="h-3 w-3" />
                Added Date
              </label>
              <div className="flex items-center gap-2">
                <input
                  type="date"
                  value={urlAddedAfter ?? ""}
                  onChange={(e) => updateParam("added_after", e.target.value || null)}
                  className="w-full min-w-0 rounded-lg border border-input bg-background px-3 py-2.5 text-sm outline-none transition-shadow placeholder:text-muted-foreground focus:ring-2 focus:ring-ring/40"
                />
                <span className="shrink-0 text-xs text-muted-foreground">to</span>
                <input
                  type="date"
                  value={urlAddedBefore ?? ""}
                  onChange={(e) => updateParam("added_before", e.target.value || null)}
                  className="w-full min-w-0 rounded-lg border border-input bg-background px-3 py-2.5 text-sm outline-none transition-shadow placeholder:text-muted-foreground focus:ring-2 focus:ring-ring/40"
                />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Bulk actions */}
      {selected.size > 0 && (
        <BulkActionBar
          count={selected.size}
          onUpdateStatus={handleBulkUpdateStatus}
          onDelete={() => setConfirmDelete(true)}
          onClear={() => setSelected(new Set())}
          loading={updateCompany.isPending}
          deleteLoading={bulkDelete.isPending}
        />
      )}

      {/* Table */}
      <div className="overflow-x-auto rounded-xl border border-border bg-card shadow-sm animate-enter" style={{ animationDelay: "120ms" }}>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/40">
              <th className="w-10 px-4 py-3.5 text-left">
                <input
                  type="checkbox"
                  checked={allPageSelected}
                  onChange={toggleSelectAll}
                  className="h-4 w-4 rounded border-input accent-primary"
                />
              </th>
              <th className="px-4 py-3.5 text-left">
                <SortHeader
                  label="Company"
                  column="name"
                  currentSort={urlSort}
                  currentOrder={urlOrder}
                  onSort={handleSort}
                />
              </th>
              <th className="px-4 py-3.5 text-left">
                <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Domain
                </span>
              </th>
              <th className="px-4 py-3.5 text-left">
                <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Industry
                </span>
              </th>
              <th className="px-4 py-3.5 text-left">
                <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Size
                </span>
              </th>
              <th className="px-4 py-3.5 text-left">
                <SortHeader
                  label="ICP"
                  column="icp_score"
                  currentSort={urlSort}
                  currentOrder={urlOrder}
                  onSort={handleSort}
                />
              </th>
              <th className="px-4 py-3.5 text-left">
                <SortHeader
                  label="Lead Score"
                  column="lead_score"
                  currentSort={urlSort}
                  currentOrder={urlOrder}
                  onSort={handleSort}
                />
              </th>
              <th className="px-4 py-3.5 text-left">
                <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Status
                </span>
              </th>
              <th className="px-4 py-3.5 text-left">
                <SortHeader
                  label="Added"
                  column="created_at"
                  currentSort={urlSort}
                  currentOrder={urlOrder}
                  onSort={handleSort}
                />
              </th>
              <th className="w-24 px-4 py-3.5 text-left">
                <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Actions
                </span>
              </th>
            </tr>
          </thead>
          <tbody className={cn("divide-y divide-border", isPlaceholderData && "opacity-50 pointer-events-none")}>
            {isLoading ? (
              <TableSkeleton rows={urlLimit > 10 ? 10 : urlLimit} />
            ) : isError ? (
              <tr>
                <td colSpan={10}>
                  <div className="flex flex-col items-center justify-center py-16 text-center">
                    <p className="text-sm text-destructive">Failed to load companies. Please try again.</p>
                  </div>
                </td>
              </tr>
            ) : data && data.items.length > 0 ? (
              data.items.map((company) => (
                <CompanyRow
                  key={company.id}
                  company={company}
                  hasActiveICP={hasActiveICP}
                  selected={selected.has(company.id)}
                  onToggleSelect={() => toggleSelect(company.id)}
                  onClick={() => navigate(`/companies/${company.id}`)}
                />
              ))
            ) : (
              <tr>
                <td colSpan={10}>
                  <EmptyState hasFilters={hasFilters} />
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {data && data.total > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-4 animate-fade-in">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <span>
              Showing {data.offset + 1}&ndash;{Math.min(data.offset + data.limit, data.total)}{" "}
              of {data.total}
            </span>
            <span className="text-border">|</span>
            <label className="flex items-center gap-1">
              Rows:
              <Select
                compact
                value={urlLimit}
                onChange={(e) => updateParam("limit", e.target.value)}
                className="w-auto"
              >
                {PAGE_SIZES.map((size) => (
                  <option key={size} value={size}>
                    {size}
                  </option>
                ))}
              </Select>
            </label>
          </div>
          <div className="flex items-center gap-1">
            <button
              type="button"
              disabled={urlPage <= 1}
              onClick={() => updateParam("page", String(urlPage - 1))}
              className="inline-flex items-center rounded-lg border border-input bg-card px-2.5 py-1.5 text-sm shadow-sm transition-all hover:bg-accent disabled:opacity-40"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <span className="px-3 text-sm text-muted-foreground tabular-nums">
              Page {urlPage} of {totalPages}
            </span>
            <button
              type="button"
              disabled={urlPage >= totalPages}
              onClick={() => updateParam("page", String(urlPage + 1))}
              className="inline-flex items-center rounded-lg border border-input bg-card px-2.5 py-1.5 text-sm shadow-sm transition-all hover:bg-accent disabled:opacity-40"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      {/* Add Company Modal */}
      {addModalOpen && (
        <AddCompanyModal
          onClose={() => setAddModalOpen(false)}
          mutation={createCompany}
        />
      )}

      {/* Import Excel Modal */}
      {importModalOpen && (
        <ImportModal
          onClose={() => setImportModalOpen(false)}
          mutation={importCompanies}
        />
      )}

      {/* Confirm Bulk Delete Dialog */}
      {confirmDelete && (
        <ConfirmDialog
          title="Archive companies"
          message={`Are you sure you want to archive ${selected.size} company${selected.size > 1 ? "ies" : ""}? They will be moved to the archived status.`}
          confirmLabel="Archive"
          loading={bulkDelete.isPending}
          onConfirm={handleBulkDelete}
          onCancel={() => setConfirmDelete(false)}
        />
      )}
    </div>
  );
}

// ── Table row ─────────────────────────────────────────────────────

function CompanyRow({
  company,
  hasActiveICP,
  selected,
  onToggleSelect,
  onClick,
}: {
  company: Company;
  hasActiveICP: boolean;
  selected: boolean;
  onToggleSelect: () => void;
  onClick: () => void;
}) {
  const scrapeMutation = useTriggerScrapeFromList();
  const pipelineMutation = useTriggerPipelineFromList();
  const [scrapeStatus, setScrapeStatus] = useState<"idle" | "success" | "error">("idle");
  const [pipelineStatus, setPipelineStatus] = useState<"idle" | "success" | "error">("idle");

  const handleAction = (
    mutation: typeof scrapeMutation,
    setStatus: typeof setScrapeStatus,
  ) => {
    setStatus("idle");
    mutation.mutate(company.id, {
      onSuccess: () => {
        setStatus("success");
        setTimeout(() => setStatus("idle"), 3000);
      },
      onError: () => {
        setStatus("error");
        setTimeout(() => setStatus("idle"), 3000);
      },
    });
  };

  return (
    <tr
      className={cn(
        "cursor-pointer transition-colors duration-150 hover:bg-muted/40",
        selected && "bg-primary/5",
      )}
      onClick={onClick}
    >
      <td className="px-4 py-3.5" onClick={(e) => { e.stopPropagation(); onToggleSelect(); }}>
        <input
          type="checkbox"
          checked={selected}
          onChange={() => {}}
          className="h-4 w-4 rounded border-input accent-primary"
        />
      </td>
      <td className="px-4 py-3.5 font-medium">
        {company.name}
      </td>
      <td className="px-4 py-3.5 text-muted-foreground">
        {company.domain}
      </td>
      <td className="px-4 py-3.5 text-muted-foreground max-w-[200px]">
        <span className="block truncate" title={company.industry ?? undefined}>
          {company.industry ?? "\u2014"}
        </span>
      </td>
      <td className="px-4 py-3.5 text-muted-foreground">
        {company.size ?? "\u2014"}
      </td>
      <td className="px-4 py-3.5">
        <ScoreBadge score={company.icp_score} />
      </td>
      <td className="px-4 py-3.5">
        <LeadScoreBadge score={company.lead_score} />
      </td>
      <td className="px-4 py-3.5">
        <div className="flex items-center gap-1.5">
          <StatusBadge status={company.status} />
          {company.monitor && (
            <span
              className="inline-block h-2 w-2 rounded-full bg-emerald-500"
              title="Monitored — LinkedIn checked weekly"
            />
          )}
        </div>
      </td>
      <td className="px-4 py-3.5 text-muted-foreground">
        {new Date(company.created_at).toLocaleDateString()}
      </td>
      <td className="px-4 py-3.5" onClick={(e) => e.stopPropagation()}>
        <div className="flex gap-1">
          <button
            type="button"
            disabled={!hasActiveICP || scrapeMutation.isPending}
            title={!hasActiveICP ? "Activate an ICP profile first" : undefined}
            onClick={() => handleAction(scrapeMutation, setScrapeStatus)}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium transition-colors disabled:opacity-50",
              scrapeStatus === "success"
                ? "text-green-600"
                : scrapeStatus === "error"
                  ? "text-destructive"
                  : "text-muted-foreground hover:bg-accent hover:text-foreground",
            )}
          >
            {scrapeMutation.isPending ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : scrapeStatus === "success" ? (
              <Check className="h-3.5 w-3.5" />
            ) : scrapeStatus === "error" ? (
              <AlertCircle className="h-3.5 w-3.5" />
            ) : (
              <Globe className="h-3.5 w-3.5" />
            )}
            {scrapeMutation.isPending
              ? "Scraping…"
              : scrapeStatus === "success"
                ? "Scraped"
                : scrapeStatus === "error"
                  ? "Failed"
                  : "Scrape"}
          </button>
          <button
            type="button"
            disabled={!hasActiveICP || pipelineMutation.isPending}
            title={!hasActiveICP ? "Activate an ICP profile first" : undefined}
            onClick={() => handleAction(pipelineMutation, setPipelineStatus)}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium transition-colors disabled:opacity-50",
              pipelineStatus === "success"
                ? "text-green-600"
                : pipelineStatus === "error"
                  ? "text-destructive"
                  : "text-muted-foreground hover:bg-accent hover:text-foreground",
            )}
          >
            {pipelineMutation.isPending ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : pipelineStatus === "success" ? (
              <Check className="h-3.5 w-3.5" />
            ) : pipelineStatus === "error" ? (
              <AlertCircle className="h-3.5 w-3.5" />
            ) : null}
            {pipelineMutation.isPending
              ? "Running…"
              : pipelineStatus === "success"
                ? "Started"
                : pipelineStatus === "error"
                  ? "Failed"
                  : "Pipeline"}
          </button>
        </div>
      </td>
    </tr>
  );
}

// ── Add Company Modal ─────────────────────────────────────────────

function AddCompanyModal({
  onClose,
  mutation,
}: {
  onClose: () => void;
  mutation: ReturnType<typeof useCreateCompany>;
}) {
  const [name, setName] = useState("");
  const [domain, setDomain] = useState("");
  const [industry, setIndustry] = useState("");
  const [size, setSize] = useState("");
  const [location, setLocation] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await mutation.mutateAsync({
        name,
        domain,
        industry: industry || undefined,
        size: size || undefined,
        location: location || undefined,
      });
      onClose();
    } catch (err: unknown) {
      const msg =
        err && typeof err === "object" && "response" in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      setError(msg || "Failed to create company");
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="w-full max-w-md rounded-xl border border-border bg-card p-6 shadow-xl animate-enter"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-semibold">Add Company</h2>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X className="h-5 w-5" />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1.5 block text-xs font-medium text-muted-foreground">Name *</label>
            <input
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded-lg border border-input bg-background px-3 py-2.5 text-sm outline-none transition-shadow placeholder:text-muted-foreground focus:ring-2 focus:ring-ring/40"
              placeholder="Acme Corp"
            />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium text-muted-foreground">Domain *</label>
            <input
              type="text"
              required
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              className="w-full rounded-lg border border-input bg-background px-3 py-2.5 text-sm outline-none transition-shadow placeholder:text-muted-foreground focus:ring-2 focus:ring-ring/40"
              placeholder="acme.com"
            />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium text-muted-foreground">Industry</label>
            <input
              type="text"
              value={industry}
              onChange={(e) => setIndustry(e.target.value)}
              className="w-full rounded-lg border border-input bg-background px-3 py-2.5 text-sm outline-none transition-shadow placeholder:text-muted-foreground focus:ring-2 focus:ring-ring/40"
              placeholder="SaaS"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1.5 block text-xs font-medium text-muted-foreground">Size</label>
              <input
                type="text"
                value={size}
                onChange={(e) => setSize(e.target.value)}
                className="w-full rounded-lg border border-input bg-background px-3 py-2.5 text-sm outline-none transition-shadow placeholder:text-muted-foreground focus:ring-2 focus:ring-ring/40"
                placeholder="50 employees"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium text-muted-foreground">Location</label>
              <input
                type="text"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                className="w-full rounded-lg border border-input bg-background px-3 py-2.5 text-sm outline-none transition-shadow placeholder:text-muted-foreground focus:ring-2 focus:ring-ring/40"
                placeholder="Amsterdam"
              />
            </div>
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-input px-4 py-2 text-sm font-medium transition-colors hover:bg-accent"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={mutation.isPending}
              className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-all hover:bg-primary/90 disabled:opacity-50"
            >
              {mutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
              Add Company
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Import Excel Modal ────────────────────────────────────────────

function ImportModal({
  onClose,
  mutation,
}: {
  onClose: () => void;
  mutation: ReturnType<typeof useImportCompanies>;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<BulkImportResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleUpload() {
    if (!file) return;
    setError(null);
    try {
      const res = await mutation.mutateAsync(file);
      setResult(res);
    } catch (err: unknown) {
      const msg =
        err && typeof err === "object" && "response" in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      setError(msg || "Failed to import file");
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="w-full max-w-md rounded-xl border border-border bg-card p-6 shadow-xl animate-enter"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-semibold">Import Companies</h2>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X className="h-5 w-5" />
          </button>
        </div>

        {!result ? (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Upload an Excel file (.xlsx). Supports both English (<strong>name</strong>, <strong>domain</strong>)
              and Dutch Bedrijfsdata headers (<strong>bedrijfsnaam</strong>, <strong>domein</strong>).
              All Bedrijfsdata columns (KvK, address, phone, social links, tech stack, etc.) are imported automatically.
            </p>
            <div>
              <input
                type="file"
                accept=".xlsx,.xls"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                className="w-full text-sm text-muted-foreground file:mr-3 file:rounded-lg file:border-0 file:bg-primary file:px-3 file:py-2 file:text-sm file:font-medium file:text-primary-foreground hover:file:bg-primary/90"
              />
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <div className="flex justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={onClose}
                className="rounded-lg border border-input px-4 py-2 text-sm font-medium transition-colors hover:bg-accent"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleUpload}
                disabled={!file || mutation.isPending}
                className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-all hover:bg-primary/90 disabled:opacity-50"
              >
                {mutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                Upload
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="grid grid-cols-3 gap-3">
              <div className="rounded-lg bg-green-50 dark:bg-green-950/30 p-3 text-center">
                <div className="text-2xl font-bold text-green-600">{result.imported}</div>
                <div className="text-xs text-muted-foreground">Imported</div>
              </div>
              <div className="rounded-lg bg-yellow-50 dark:bg-yellow-950/30 p-3 text-center">
                <div className="text-2xl font-bold text-yellow-600">{result.skipped}</div>
                <div className="text-xs text-muted-foreground">Skipped</div>
              </div>
              <div className="rounded-lg bg-red-50 dark:bg-red-950/30 p-3 text-center">
                <div className="text-2xl font-bold text-red-600">{result.errors.length}</div>
                <div className="text-xs text-muted-foreground">Errors</div>
              </div>
            </div>
            {result.errors.length > 0 && (
              <div className="max-h-40 overflow-y-auto rounded-lg border border-border p-3 text-xs space-y-1">
                {result.errors.map((e) => (
                  <div key={e.row} className="text-destructive">
                    Row {e.row}: {e.error}
                  </div>
                ))}
              </div>
            )}
            <div className="flex justify-end pt-2">
              <button
                type="button"
                onClick={onClose}
                className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-all hover:bg-primary/90"
              >
                Done
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Confirm Dialog ────────────────────────────────────────────────

function ConfirmDialog({
  title,
  message,
  confirmLabel,
  loading,
  onConfirm,
  onCancel,
}: {
  title: string;
  message: string;
  confirmLabel: string;
  loading: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onCancel}>
      <div
        className="w-full max-w-sm rounded-xl border border-border bg-card p-6 shadow-xl animate-enter"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-lg font-semibold">{title}</h3>
        <p className="mt-2 text-sm text-muted-foreground">{message}</p>
        <div className="mt-5 flex justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-lg border border-input px-4 py-2 text-sm font-medium transition-colors hover:bg-accent"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={loading}
            className="inline-flex items-center gap-2 rounded-lg bg-destructive px-4 py-2 text-sm font-medium text-destructive-foreground transition-all hover:bg-destructive/90 disabled:opacity-50"
          >
            {loading && <Loader2 className="h-4 w-4 animate-spin" />}
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
