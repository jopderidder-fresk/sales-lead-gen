import {
  useContacts,
  type ContactWithCompanyResponse,
  type ContactListParams,
} from "@/lib/contacts";
import { EmailStatusBadge } from "@/components/badges";
import { cn } from "@/lib/utils";
import type { EmailStatus } from "@/types/api";
import { Select } from "@/components/Select";
import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ClipboardCopy,
  ExternalLink,
  Loader2,
  Search,
  Users,
  X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

// ── Constants ─────────────────────────────────────────────────────

const PAGE_SIZES = [10, 25, 50] as const;

const EMAIL_STATUS_OPTIONS: { value: EmailStatus; label: string }[] = [
  { value: "verified", label: "Verified" },
  { value: "catch-all", label: "Catch-all" },
  { value: "unverified", label: "Unverified" },
];

const SORTABLE_COLUMNS = ["name", "title", "email", "company_name", "created_at"] as const;
type SortColumn = (typeof SORTABLE_COLUMNS)[number];

function isSortable(col: string): col is SortColumn {
  return (SORTABLE_COLUMNS as readonly string[]).includes(col);
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "\u2014";
  return new Date(iso).toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
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

// ── Copy button ──────────────────────────────────────────────────

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  function handleCopy(e: React.MouseEvent) {
    e.stopPropagation();
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }).catch(() => {});
  }

  return (
    <button
      type="button"
      onClick={handleCopy}
      className="ml-1.5 inline-flex items-center rounded p-0.5 text-muted-foreground/60 transition-colors hover:text-foreground"
      title="Copy email"
    >
      {copied ? (
        <Check className="h-3 w-3 text-green-600" />
      ) : (
        <ClipboardCopy className="h-3 w-3" />
      )}
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
            <div className="space-y-1.5">
              <div className="h-4 w-28 rounded bg-muted" />
              <div className="h-3 w-20 rounded bg-muted" />
            </div>
          </td>
          <td className="px-4 py-3.5">
            <div className="h-4 w-24 rounded bg-muted" />
          </td>
          <td className="px-4 py-3.5">
            <div className="h-4 w-36 rounded bg-muted" />
          </td>
          <td className="px-4 py-3.5 hidden lg:table-cell">
            <div className="h-4 w-24 rounded bg-muted" />
          </td>
          <td className="px-4 py-3.5 hidden md:table-cell">
            <div className="h-5 w-16 rounded bg-muted" />
          </td>
          <td className="px-4 py-3.5 hidden sm:table-cell">
            <div className="h-4 w-20 rounded bg-muted" />
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
        <Users className="h-10 w-10 text-muted-foreground/50" />
      </div>
      <h3 className="mt-5 text-lg font-medium">
        {hasFilters ? "No contacts match your filters" : "No contacts yet"}
      </h3>
      <p className="mt-1.5 max-w-sm text-sm text-muted-foreground">
        {hasFilters
          ? "Try adjusting your search or filters."
          : "Contacts will appear here once companies are enriched."}
      </p>
    </div>
  );
}

// ── Email status filter dropdown ──────────────────────────────────

const EMAIL_STATUS_DOT: Record<EmailStatus, string> = {
  verified: "bg-green-500",
  "catch-all": "bg-yellow-500",
  unverified: "bg-gray-400",
};

const EMAIL_STATUS_BADGE_COLORS: Record<EmailStatus, string> = {
  verified: "bg-green-50 text-green-700 ring-green-200",
  "catch-all": "bg-yellow-50 text-yellow-700 ring-yellow-200",
  unverified: "bg-gray-50 text-gray-600 ring-gray-200",
};

function EmailStatusFilter({
  value,
  onChange,
}: {
  value: EmailStatus | null;
  onChange: (value: EmailStatus | null) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  const selectedOption = value
    ? EMAIL_STATUS_OPTIONS.find((o) => o.value === value)
    : null;

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className={cn(
          "inline-flex items-center gap-2 rounded-lg border px-3 py-2.5 text-sm font-medium shadow-sm transition-all",
          value
            ? "border-primary/30 bg-primary/5 text-foreground"
            : "border-input bg-card text-muted-foreground hover:bg-accent hover:text-foreground",
        )}
      >
        {selectedOption ? (
          <>
            <span
              className={cn("h-2 w-2 rounded-full", EMAIL_STATUS_DOT[value!])}
            />
            {selectedOption.label}
          </>
        ) : (
          "Email status"
        )}
        <ChevronDown
          className={cn(
            "h-3.5 w-3.5 transition-transform duration-200",
            open && "rotate-180",
          )}
        />
      </button>

      {open && (
        <div className="absolute left-0 z-50 mt-1.5 w-48 rounded-xl border border-border bg-card shadow-lg animate-enter origin-top">
          {/* All / reset option */}
          <button
            type="button"
            onClick={() => {
              onChange(null);
              setOpen(false);
            }}
            className={cn(
              "flex w-full items-center gap-2.5 rounded-t-xl px-3 py-2.5 text-left text-sm transition-colors hover:bg-accent",
              !value && "font-medium",
            )}
          >
            <span className="flex h-4 w-4 items-center justify-center">
              {!value && <Check className="h-3.5 w-3.5 text-primary" />}
            </span>
            <span className="text-muted-foreground">All statuses</span>
          </button>

          <div className="mx-3 border-t border-border" />

          {EMAIL_STATUS_OPTIONS.map((opt, i) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => {
                onChange(opt.value === value ? null : opt.value);
                setOpen(false);
              }}
              className={cn(
                "flex w-full items-center gap-2.5 px-3 py-2.5 text-left text-sm transition-colors hover:bg-accent",
                i === EMAIL_STATUS_OPTIONS.length - 1 && "rounded-b-xl",
              )}
            >
              <span className="flex h-4 w-4 items-center justify-center">
                {value === opt.value && (
                  <Check className="h-3.5 w-3.5 text-primary" />
                )}
              </span>
              <span
                className={cn(
                  "inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
                  EMAIL_STATUS_BADGE_COLORS[opt.value],
                )}
              >
                {opt.label}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────

export default function People() {
  const [searchParams, setSearchParams] = useSearchParams();

  // Parse URL params
  const urlSearch = searchParams.get("search") ?? "";
  const rawEmailStatus = searchParams.get("email_status");
  const urlEmailStatus =
    rawEmailStatus && EMAIL_STATUS_OPTIONS.some((o) => o.value === rawEmailStatus)
      ? (rawEmailStatus as EmailStatus)
      : null;
  const rawSort = searchParams.get("sort") || "created_at";
  const urlSort = isSortable(rawSort) ? rawSort : "created_at";
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

  // Local search input (debounced)
  const [searchInput, setSearchInput] = useState(urlSearch);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const prevUrlSearch = useRef(urlSearch);
  useEffect(() => {
    if (urlSearch !== prevUrlSearch.current) {
      prevUrlSearch.current = urlSearch;
      setSearchInput(urlSearch);
    }
  }, [urlSearch]);

  const updateParam = useCallback(
    (key: string, value: string | null) => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        if (value) {
          next.set(key, value);
        } else {
          next.delete(key);
        }
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

  // Build query params
  const queryParams: ContactListParams = useMemo(
    () => ({
      offset: (urlPage - 1) * urlLimit,
      limit: urlLimit,
      search: urlSearch || null,
      email_status: urlEmailStatus,
      sort: urlSort,
      order: urlOrder,
    }),
    [urlPage, urlLimit, urlSearch, urlEmailStatus, urlSort, urlOrder],
  );

  const { data, isLoading, isFetching, isError } = useContacts(queryParams);
  const totalPages = data ? Math.max(1, Math.ceil(data.total / urlLimit)) : 1;
  const hasFilters = !!(urlSearch || urlEmailStatus);

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

  function clearFilters() {
    setSearchParams({});
    setSearchInput("");
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between animate-enter">
        <div>
          <h1 className="text-2xl tracking-tight">People</h1>
          <p
            className="mt-1 text-sm text-muted-foreground"
            style={{ fontFamily: '"DM Sans", system-ui, sans-serif' }}
          >
            {data
              ? `${data.total.toLocaleString()} contact${data.total !== 1 ? "s" : ""} across all companies.`
              : "Browse contacts across all companies."}
          </p>
        </div>
        {isFetching && !isLoading && (
          <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
        )}
      </div>

      {/* Search + filters */}
      <div
        className="relative z-20 flex flex-wrap items-center gap-3 animate-enter"
        style={{ animationDelay: "60ms" }}
      >
        <div className="relative flex-1 min-w-[200px] max-w-md">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="Search by name, email, title, or company\u2026"
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

        {/* Email status filter */}
        <EmailStatusFilter
          value={urlEmailStatus}
          onChange={(v) => updateParam("email_status", v)}
        />

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

      {/* Table */}
      <div
        className="overflow-x-auto rounded-xl border border-border bg-card shadow-sm animate-enter"
        style={{ animationDelay: "120ms" }}
      >
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/40">
              <th className="px-4 py-3.5 text-left">
                <SortHeader
                  label="Name"
                  column="name"
                  currentSort={urlSort}
                  currentOrder={urlOrder}
                  onSort={handleSort}
                />
              </th>
              <th className="px-4 py-3.5 text-left">
                <SortHeader
                  label="Company"
                  column="company_name"
                  currentSort={urlSort}
                  currentOrder={urlOrder}
                  onSort={handleSort}
                />
              </th>
              <th className="px-4 py-3.5 text-left">
                <SortHeader
                  label="Email"
                  column="email"
                  currentSort={urlSort}
                  currentOrder={urlOrder}
                  onSort={handleSort}
                />
              </th>
              <th className="hidden lg:table-cell px-4 py-3.5 text-left">
                <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Phone
                </span>
              </th>
              <th className="hidden md:table-cell px-4 py-3.5 text-left">
                <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Source
                </span>
              </th>
              <th className="hidden sm:table-cell px-4 py-3.5 text-left">
                <SortHeader
                  label="Added"
                  column="created_at"
                  currentSort={urlSort}
                  currentOrder={urlOrder}
                  onSort={handleSort}
                />
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {isLoading ? (
              <TableSkeleton rows={urlLimit > 10 ? 10 : urlLimit} />
            ) : isError ? (
              <tr>
                <td colSpan={6}>
                  <div className="flex flex-col items-center justify-center py-16 text-center">
                    <p className="text-sm text-destructive">
                      Failed to load contacts. Please try again.
                    </p>
                  </div>
                </td>
              </tr>
            ) : data && data.items.length > 0 ? (
              data.items.map((contact) => (
                <ContactRow key={contact.id} contact={contact} />
              ))
            ) : (
              <tr>
                <td colSpan={6}>
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
              Showing {data.offset + 1}&ndash;
              {Math.min(data.offset + data.limit, data.total)} of {data.total}
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
    </div>
  );
}

// ── Table row ─────────────────────────────────────────────────────

function ContactRow({ contact }: { contact: ContactWithCompanyResponse }) {
  return (
    <tr className="transition-colors duration-150 hover:bg-muted/40">
      {/* Name + title */}
      <td className="px-4 py-3.5">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
            {contact.name
              .split(" ")
              .slice(0, 2)
              .map((w) => w[0])
              .join("")
              .toUpperCase()}
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-1.5">
              <span className="font-medium truncate">{contact.name}</span>
              {contact.linkedin_url && (
                <a
                  href={contact.linkedin_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                  className="shrink-0 rounded px-1 py-0.5 text-[10px] font-semibold tracking-wide text-muted-foreground/60 ring-1 ring-inset ring-border transition-colors hover:text-[#0A66C2] hover:ring-[#0A66C2]/30"
                  title="LinkedIn profile"
                >
                  in
                </a>
              )}
            </div>
            {contact.title && (
              <p className="text-xs text-muted-foreground truncate max-w-[200px]">
                {contact.title}
              </p>
            )}
          </div>
        </div>
      </td>

      {/* Company */}
      <td className="px-4 py-3.5">
        <Link
          to={`/companies/${contact.company_id}`}
          onClick={(e) => e.stopPropagation()}
          className="group inline-flex items-center gap-1 text-sm transition-colors hover:text-primary"
        >
          <span className="truncate max-w-[160px]">{contact.company_name}</span>
          <ExternalLink className="h-3 w-3 shrink-0 opacity-0 transition-opacity group-hover:opacity-60" />
        </Link>
        <p className="text-xs text-muted-foreground">{contact.company_domain}</p>
      </td>

      {/* Email */}
      <td className="px-4 py-3.5">
        {contact.email ? (
          <div className="flex items-center gap-1.5">
            <span className="truncate max-w-[180px] text-sm">{contact.email}</span>
            <CopyButton text={contact.email} />
            {contact.email_status && (
              <EmailStatusBadge status={contact.email_status} />
            )}
          </div>
        ) : (
          <span className="text-muted-foreground">&mdash;</span>
        )}
      </td>

      {/* Phone */}
      <td className="hidden lg:table-cell px-4 py-3.5 text-muted-foreground">
        {contact.phone ?? "\u2014"}
      </td>

      {/* Source */}
      <td className="hidden md:table-cell px-4 py-3.5">
        {contact.source ? (
          <span className="inline-flex items-center rounded-md bg-secondary px-2 py-0.5 text-xs font-medium text-secondary-foreground ring-1 ring-inset ring-border">
            {contact.source}
          </span>
        ) : (
          <span className="text-muted-foreground">&mdash;</span>
        )}
      </td>

      {/* Added */}
      <td className="hidden sm:table-cell px-4 py-3.5 text-muted-foreground">
        {formatDate(contact.created_at)}
      </td>
    </tr>
  );
}
