import { DiscoveryJobStatusBadge } from "@/components/badges";
import { Select, CustomSelect } from "@/components/Select";
import { useAuth } from "@/context/auth";
import {
  useDiscoveryJob,
  useDiscoveryJobs,
  useDiscoverySchedule,
  useTriggerDiscovery,
  useUpdateDiscoverySchedule,
  type DiscoveryJobResponse,
} from "@/lib/discovery";
import { cn } from "@/lib/utils";
import type { DiscoveryJobStatus } from "@/types/api";
import {
  Activity,
  Calendar,
  ChevronLeft,
  ChevronRight,
  Clock,
  Loader2,
  Play,
  Search as SearchIcon,
  X,
} from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

const PAGE_SIZES = [10, 25, 50] as const;

const STATUS_OPTIONS: { value: DiscoveryJobStatus; label: string }[] = [
  { value: "pending", label: "Pending" },
  { value: "running", label: "Running" },
  { value: "completed", label: "Completed" },
  { value: "failed", label: "Failed" },
];

const SCHEDULE_PRESETS = [
  { value: "daily", label: "Every day at 02:00 UTC" },
  { value: "twice_daily", label: "Twice daily (02:00 & 14:00 UTC)" },
  { value: "weekly", label: "Every Monday at 02:00 UTC" },
];

function formatDuration(seconds: number | null): string {
  if (seconds == null) return "—";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  if (m === 0) return `${s}s`;
  return `${m}m ${s}s`;
}

function formatDateTime(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// ── Active job progress bar ──────────────────────────────────────

function ActiveJobBar({ job }: { job: DiscoveryJobResponse }) {
  return (
    <div className="rounded-xl border border-blue-200 bg-blue-50 p-4 shadow-sm animate-enter">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="relative flex h-3 w-3">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400 opacity-75" />
            <span className="relative inline-flex h-3 w-3 rounded-full bg-blue-500" />
          </div>
          <div>
            <p className="text-sm font-medium text-blue-900">
              Discovery job #{job.id} is running
            </p>
            <p className="text-xs text-blue-700">
              Started {formatDateTime(job.started_at)} &middot; Trigger: {job.trigger}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-4 text-sm text-blue-800">
          <span>{job.companies_found} found</span>
          <span>{job.companies_added} added</span>
          <span>{job.companies_skipped} skipped</span>
        </div>
      </div>
      <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-blue-200">
        <div className="h-full animate-pulse rounded-full bg-blue-500" style={{ width: "60%" }} />
      </div>
    </div>
  );
}

// ── Schedule editor ──────────────────────────────────────────────

function ScheduleEditor() {
  const { data: schedule, isLoading } = useDiscoverySchedule();
  const updateSchedule = useUpdateDiscoverySchedule();
  const { isAdmin } = useAuth();
  const [editing, setEditing] = useState(false);
  const [customCron, setCustomCron] = useState("");

  if (isLoading) {
    return (
      <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
        <div className="flex items-center gap-2">
          <div className="h-4 w-4 animate-pulse rounded bg-muted" />
          <div className="h-4 w-32 animate-pulse rounded bg-muted" />
        </div>
      </div>
    );
  }

  function handlePreset(frequency: string) {
    updateSchedule.mutate(
      { frequency },
      { onSuccess: () => setEditing(false) },
    );
  }

  function handleCustom() {
    if (!customCron.trim()) return;
    updateSchedule.mutate(
      { frequency: customCron.trim() },
      {
        onSuccess: () => {
          setEditing(false);
          setCustomCron("");
        },
      },
    );
  }

  return (
    <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Calendar className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-medium">Schedule</span>
        </div>
        {isAdmin && (
          <button
            type="button"
            onClick={() => setEditing(!editing)}
            className="text-xs text-primary hover:underline"
          >
            {editing ? "Cancel" : "Edit"}
          </button>
        )}
      </div>

      <p className="mt-2 text-sm font-medium">
        {schedule?.human_readable ?? "Not configured"}
      </p>

      {editing && (
        <div className="mt-3 space-y-2 border-t border-border pt-3">
          <p className="text-xs font-medium text-muted-foreground">Quick presets</p>
          <div className="flex flex-col gap-1.5">
            {SCHEDULE_PRESETS.map((preset) => (
              <button
                key={preset.value}
                type="button"
                onClick={() => handlePreset(preset.value)}
                disabled={updateSchedule.isPending}
                className="rounded-lg border border-input px-3 py-1.5 text-left text-xs font-medium transition-colors hover:bg-accent disabled:opacity-50"
              >
                {preset.label}
              </button>
            ))}
          </div>
          <p className="text-xs font-medium text-muted-foreground pt-1">
            Or enter a custom cron expression
          </p>
          <div className="flex gap-2">
            <input
              type="text"
              value={customCron}
              onChange={(e) => setCustomCron(e.target.value)}
              placeholder="e.g. 0 2 * * * (min hour dom month dow)"
              className="flex-1 rounded-lg border border-input bg-background px-3 py-1.5 text-xs outline-none transition-shadow placeholder:text-muted-foreground focus:ring-2 focus:ring-ring/40"
            />
            <button
              type="button"
              onClick={handleCustom}
              disabled={!customCron.trim() || updateSchedule.isPending}
              className="rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground transition-all hover:bg-primary/90 disabled:opacity-50"
            >
              Apply
            </button>
          </div>
          {updateSchedule.isError && (
            <p className="text-xs text-destructive">
              Failed to update schedule. Check the cron format.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

// ── Job detail panel ─────────────────────────────────────────────

function JobDetailPanel({
  jobId,
  onClose,
}: {
  jobId: number;
  onClose: () => void;
}) {
  const { data: job, isLoading, isError } = useDiscoveryJob(jobId);

  return (
    <div className="fixed inset-y-0 right-0 z-40 flex w-full max-w-lg flex-col border-l border-border bg-background shadow-2xl animate-slide-in-right">
      <div className="flex items-center justify-between border-b border-border px-6 py-4">
        <h2 className="text-lg tracking-tight">Job #{jobId} Details</h2>
        <button
          type="button"
          onClick={onClose}
          className="rounded-lg p-1 transition-colors hover:bg-accent"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : isError || !job ? (
          <p className="text-sm text-destructive">Failed to load job details.</p>
        ) : (
          <div className="space-y-6">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-xs font-medium text-muted-foreground">Status</p>
                <div className="mt-1">
                  <DiscoveryJobStatusBadge status={job.status} />
                </div>
              </div>
              <div>
                <p className="text-xs font-medium text-muted-foreground">Trigger</p>
                <p className="mt-1 text-sm capitalize">{job.trigger}</p>
              </div>
              <div>
                <p className="text-xs font-medium text-muted-foreground">Started</p>
                <p className="mt-1 text-sm">{formatDateTime(job.started_at)}</p>
              </div>
              <div>
                <p className="text-xs font-medium text-muted-foreground">Completed</p>
                <p className="mt-1 text-sm">{formatDateTime(job.completed_at)}</p>
              </div>
              <div>
                <p className="text-xs font-medium text-muted-foreground">Duration</p>
                <p className="mt-1 text-sm">{formatDuration(job.duration_seconds)}</p>
              </div>
              <div>
                <p className="text-xs font-medium text-muted-foreground">Task ID</p>
                <p className="mt-1 truncate text-sm font-mono text-muted-foreground">
                  {job.celery_task_id ?? "—"}
                </p>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div className="rounded-xl border border-border bg-card p-3 text-center shadow-sm">
                <p className="text-2xl font-bold">{job.companies_found}</p>
                <p className="text-xs text-muted-foreground">Found</p>
              </div>
              <div className="rounded-xl border border-border bg-card p-3 text-center shadow-sm">
                <p className="text-2xl font-bold text-green-600">{job.companies_added}</p>
                <p className="text-xs text-muted-foreground">Added</p>
              </div>
              <div className="rounded-xl border border-border bg-card p-3 text-center shadow-sm">
                <p className="text-2xl font-bold text-yellow-600">{job.companies_skipped}</p>
                <p className="text-xs text-muted-foreground">Skipped</p>
              </div>
            </div>

            {job.error_message && (
              <div className="rounded-xl border border-red-200 bg-red-50 p-3">
                <p className="text-xs font-medium text-red-800">Error</p>
                <p className="mt-1 text-sm text-red-700">{job.error_message}</p>
              </div>
            )}

            {job.results && (
              <div>
                <p className="mb-2 text-sm font-medium">Source Breakdown</p>
                <div className="grid grid-cols-2 gap-3">
                  <div className="rounded-xl border border-border bg-muted/30 p-3">
                    <p className="text-lg font-semibold">
                      {(job.results as Record<string, number>).firecrawl_found ?? 0}
                    </p>
                    <p className="text-xs text-muted-foreground">From Firecrawl</p>
                  </div>
                  <div className="rounded-xl border border-border bg-muted/30 p-3">
                    <p className="text-lg font-semibold">
                      {(job.results as Record<string, number>).bedrijfsdata_found ?? 0}
                    </p>
                    <p className="text-xs text-muted-foreground">From Bedrijfsdata</p>
                  </div>
                </div>
                {((job.results as Record<string, string[]>).errors ?? []).length > 0 && (
                  <div className="mt-3">
                    <p className="mb-1 text-xs font-medium text-muted-foreground">Warnings</p>
                    <ul className="space-y-1">
                      {(job.results as Record<string, string[]>).errors.map((err, i) => (
                        <li key={i} className="text-xs text-yellow-700 bg-yellow-50 rounded px-2 py-1">
                          {err}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Table skeleton ───────────────────────────────────────────────

function TableSkeleton({ rows }: { rows: number }) {
  return (
    <>
      {Array.from({ length: rows }).map((_, i) => (
        <tr key={i} className="animate-pulse">
          <td className="px-4 py-3"><div className="h-4 w-8 rounded bg-muted" /></td>
          <td className="px-4 py-3"><div className="h-4 w-28 rounded bg-muted" /></td>
          <td className="px-4 py-3"><div className="h-4 w-28 rounded bg-muted" /></td>
          <td className="px-4 py-3"><div className="h-5 w-16 rounded-full bg-muted" /></td>
          <td className="px-4 py-3"><div className="h-4 w-10 rounded bg-muted" /></td>
          <td className="px-4 py-3"><div className="h-4 w-10 rounded bg-muted" /></td>
          <td className="px-4 py-3"><div className="h-4 w-10 rounded bg-muted" /></td>
          <td className="px-4 py-3"><div className="h-4 w-16 rounded bg-muted" /></td>
        </tr>
      ))}
    </>
  );
}

// ── Main component ───────────────────────────────────────────────

export default function Discovery() {
  const { isAdmin } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);

  const rawStatus = searchParams.get("status");
  const urlStatus =
    rawStatus && STATUS_OPTIONS.some((o) => o.value === rawStatus)
      ? (rawStatus as DiscoveryJobStatus)
      : null;
  const rawLimit = Number(searchParams.get("limit"));
  const urlLimit =
    Number.isFinite(rawLimit) && rawLimit > 0 && rawLimit <= 100 ? rawLimit : 25;
  const rawPage = Number(searchParams.get("page"));
  const urlPage =
    Number.isFinite(rawPage) && rawPage >= 1 ? Math.floor(rawPage) : 1;

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

  const queryParams = useMemo(
    () => ({
      offset: (urlPage - 1) * urlLimit,
      limit: urlLimit,
      status: urlStatus,
    }),
    [urlPage, urlLimit, urlStatus],
  );

  const { data, isLoading, isFetching, isError } = useDiscoveryJobs(queryParams);
  const triggerDiscovery = useTriggerDiscovery();

  const runningJob = data?.items.find((j) => j.status === "running");
  const totalPages = data ? Math.max(1, Math.ceil(data.total / urlLimit)) : 1;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl tracking-tight">Discovery Jobs</h1>
          <p className="mt-1 text-sm text-muted-foreground" style={{ fontFamily: '"DM Sans", system-ui, sans-serif' }}>
            Monitor discovery runs, view job history, and manage the schedule.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {isFetching && !isLoading && (
            <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
          )}
          {isAdmin && (
            <button
              type="button"
              onClick={() => triggerDiscovery.mutate()}
              disabled={triggerDiscovery.isPending || !!runningJob}
              className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-sm transition-all hover:bg-primary/90 hover:shadow-md active:scale-[0.98] disabled:opacity-50"
            >
              {triggerDiscovery.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Play className="h-4 w-4" />
              )}
              Run Discovery Now
            </button>
          )}
        </div>
      </div>

      {/* Active job indicator */}
      {runningJob && <ActiveJobBar job={runningJob} />}

      {/* Summary cards + schedule */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm font-medium">Total Jobs</span>
          </div>
          <p className="mt-2 text-2xl font-bold">{data?.total ?? "—"}</p>
        </div>
        <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
          <div className="flex items-center gap-2">
            <SearchIcon className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm font-medium">Last Run</span>
          </div>
          <div className="mt-2">
            {data?.items[0] ? (
              <DiscoveryJobStatusBadge status={data.items[0].status} />
            ) : (
              <span className="text-sm text-muted-foreground">No runs yet</span>
            )}
          </div>
        </div>
        <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
          <div className="flex items-center gap-2">
            <Clock className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm font-medium">Last Duration</span>
          </div>
          <p className="mt-2 text-2xl font-bold">
            {data?.items[0] ? formatDuration(data.items[0].duration_seconds) : "—"}
          </p>
        </div>
        <ScheduleEditor />
      </div>

      {/* Status filter */}
      <div className="flex items-center gap-3">
        <CustomSelect
          options={[
            { value: "", label: "All statuses" },
            ...STATUS_OPTIONS,
          ]}
          value={urlStatus ?? ""}
          onChange={(v) => updateParam("status", String(v) || null)}
          placeholder="All statuses"
          className="w-44"
        />
        {urlStatus && (
          <button
            type="button"
            onClick={() => updateParam("status", null)}
            className="text-sm text-muted-foreground hover:text-foreground"
          >
            Clear filter
          </button>
        )}
      </div>

      {/* Job history table */}
      <div className="overflow-x-auto rounded-xl border border-border bg-card shadow-sm">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/40">
              <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-muted-foreground">
                ID
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Started
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Completed
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Status
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Found
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Added
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Skipped
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Duration
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {isLoading ? (
              <TableSkeleton rows={Math.min(urlLimit, 10)} />
            ) : isError ? (
              <tr>
                <td colSpan={8}>
                  <div className="flex flex-col items-center justify-center py-16 text-center">
                    <p className="text-sm text-destructive">
                      Failed to load discovery jobs. Please try again.
                    </p>
                  </div>
                </td>
              </tr>
            ) : data && data.items.length > 0 ? (
              data.items.map((job) => (
                <tr
                  key={job.id}
                  onClick={() => setSelectedJobId(job.id)}
                  className={cn(
                    "cursor-pointer transition-colors hover:bg-muted/50",
                    selectedJobId === job.id && "bg-primary/5",
                  )}
                >
                  <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
                    #{job.id}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {formatDateTime(job.started_at)}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {formatDateTime(job.completed_at)}
                  </td>
                  <td className="px-4 py-3">
                    <DiscoveryJobStatusBadge status={job.status} />
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">{job.companies_found}</td>
                  <td className="px-4 py-3 text-right tabular-nums text-green-600">
                    {job.companies_added}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-yellow-600">
                    {job.companies_skipped}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {formatDuration(job.duration_seconds)}
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={8}>
                  <div className="flex flex-col items-center justify-center py-16 text-center">
                    <Activity className="h-12 w-12 text-muted-foreground/40" />
                    <h3 className="mt-4 text-lg font-medium">No discovery jobs yet</h3>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {isAdmin
                        ? 'Click "Run Discovery Now" to start your first discovery run.'
                        : "No discovery jobs have been run yet."}
                    </p>
                  </div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {data && data.total > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <span>
              Showing {data.offset + 1}–{Math.min(data.offset + data.limit, data.total)}{" "}
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
            <span className="px-3 text-sm text-muted-foreground">
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

      {/* Detail slide-over */}
      {selectedJobId != null && (
        <>
          <div
            className="fixed inset-0 z-30 bg-black/40 backdrop-blur-sm animate-fade-in"
            onClick={() => setSelectedJobId(null)}
          />
          <JobDetailPanel
            jobId={selectedJobId}
            onClose={() => setSelectedJobId(null)}
          />
        </>
      )}
    </div>
  );
}
