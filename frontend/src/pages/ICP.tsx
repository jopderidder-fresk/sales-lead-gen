import {
  useICPProfiles,
  useCreateProfile,
  useUpdateProfile,
  useActivateProfile,
  useDeactivateProfile,
  useDeleteProfile,
  type ICPProfile,
  type ICPProfileCreate,
} from "@/lib/icp";
import { cn } from "@/lib/utils";
import {
  AlertTriangle,
  Check,
  Loader2,
  Pencil,
  Plus,
  Power,
  Trash2,
  X,
} from "lucide-react";
import { useState } from "react";

// ── Common industries for typeahead ────────────────────────────────

const COMMON_INDUSTRIES = [
  "SaaS",
  "FinTech",
  "HealthTech",
  "Manufacturing",
  "E-commerce",
  "EdTech",
  "Logistics",
  "Cybersecurity",
  "AI/ML",
  "CleanTech",
  "PropTech",
  "InsurTech",
  "AgriTech",
  "Media",
  "Retail",
  "Consulting",
];

// ── Tag Input ──────────────────────────────────────────────────────

function TagInput({
  value,
  onChange,
  placeholder,
  suggestions,
}: {
  value: string[];
  onChange: (v: string[]) => void;
  placeholder?: string;
  suggestions?: string[];
}) {
  const [input, setInput] = useState("");
  const [showSuggestions, setShowSuggestions] = useState(false);

  const filtered = suggestions?.filter(
    (s) =>
      s.toLowerCase().includes(input.toLowerCase()) && !value.includes(s),
  );

  function add(tag: string) {
    const trimmed = tag.trim();
    if (trimmed && !value.includes(trimmed)) {
      onChange([...value, trimmed]);
    }
    setInput("");
    setShowSuggestions(false);
  }

  function remove(tag: string) {
    onChange(value.filter((t) => t !== tag));
  }

  return (
    <div className="relative">
      <div className="flex flex-wrap gap-1.5 rounded-lg border border-input bg-background px-3 py-2.5">
        {value.map((tag) => (
          <span
            key={tag}
            className="inline-flex items-center gap-1 rounded-md bg-secondary px-2 py-0.5 text-xs font-medium text-secondary-foreground"
          >
            {tag}
            <button
              type="button"
              onClick={() => remove(tag)}
              className="hover:text-destructive"
            >
              <X className="h-3 w-3" />
            </button>
          </span>
        ))}
        <input
          type="text"
          value={input}
          onChange={(e) => {
            setInput(e.target.value);
            setShowSuggestions(true);
          }}
          onFocus={() => setShowSuggestions(true)}
          onBlur={() => setTimeout(() => setShowSuggestions(false), 150)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && input.trim()) {
              e.preventDefault();
              add(input);
            }
            if (e.key === "Backspace" && !input && value.length > 0) {
              remove(value[value.length - 1]);
            }
          }}
          placeholder={value.length === 0 ? placeholder : ""}
          className="min-w-[120px] flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
        />
      </div>
      {showSuggestions && filtered && filtered.length > 0 && (
        <div className="absolute z-10 mt-1 max-h-40 w-full overflow-y-auto rounded-lg border border-border bg-popover shadow-lg">
          {filtered.map((s) => (
            <button
              key={s}
              type="button"
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => add(s)}
              className="block w-full px-3 py-1.5 text-left text-sm hover:bg-accent"
            >
              {s}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Confirm Dialog ─────────────────────────────────────────────────

function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel,
  destructive,
  loading,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  message: string;
  confirmLabel: string;
  destructive?: boolean;
  loading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-dialog-title"
    >
      <div className="w-full max-w-sm rounded-xl border border-border bg-card p-6 shadow-xl animate-enter">
        <div className="mb-1 flex items-center gap-2">
          {destructive && (
            <AlertTriangle className="h-5 w-5 text-destructive" />
          )}
          <h3 id="confirm-dialog-title" className="text-lg font-semibold">{title}</h3>
        </div>
        <p className="mb-5 text-sm text-muted-foreground">{message}</p>
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            disabled={loading}
            className="rounded-lg border border-input px-3 py-1.5 text-sm transition-colors hover:bg-accent"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={loading}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium text-white transition-all disabled:opacity-50",
              destructive ? "bg-destructive hover:bg-destructive/90" : "bg-primary hover:bg-primary/90",
            )}
          >
            {loading && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Profile Card ───────────────────────────────────────────────────

function filterSummary(profile: ICPProfile): string {
  const parts: string[] = [];
  if (profile.industry_filter?.length)
    parts.push(`${profile.industry_filter.length} industries`);
  if (profile.size_filter) {
    const s = profile.size_filter;
    if (s.min_employees != null || s.max_employees != null) parts.push("size range");
    if (s.min_revenue != null || s.max_revenue != null) parts.push("revenue range");
  }
  if (profile.geo_filter) {
    const g = profile.geo_filter;
    const count = g.countries.length + g.regions.length + g.cities.length;
    if (count > 0) parts.push(`${count} geo filters`);
  }
  if (profile.tech_filter?.length)
    parts.push(`${profile.tech_filter.length} technologies`);
  if (profile.negative_filters) {
    const n = profile.negative_filters;
    const count = n.excluded_industries.length + n.excluded_domains.length;
    if (count > 0) parts.push(`${count} exclusions`);
  }
  return parts.length ? parts.join(" \u00b7 ") : "No filters configured";
}

function ProfileCard({
  profile,
  onEdit,
  onActivate,
  onDeactivate,
  onDelete,
}: {
  profile: ICPProfile;
  onEdit: () => void;
  onActivate: () => void;
  onDeactivate: () => void;
  onDelete: () => void;
}) {
  return (
    <div
      className={cn(
        "rounded-xl border bg-card p-5 shadow-sm transition-all duration-200 hover:shadow-md hover:-translate-y-0.5",
        profile.is_active
          ? "border-primary/40 ring-2 ring-primary/15"
          : "border-border",
      )}
    >
      <div className="mb-3 flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-semibold">{profile.name}</h3>
            <span
              className={cn(
                "rounded-full px-2 py-0.5 text-xs font-medium",
                profile.is_active
                  ? "bg-primary/10 text-primary"
                  : "bg-muted text-muted-foreground",
              )}
            >
              {profile.is_active ? "Active" : "Inactive"}
            </span>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            {filterSummary(profile)}
          </p>
        </div>
      </div>

      {/* Filter detail chips */}
      <div className="mb-4 flex flex-wrap gap-1.5">
        {profile.industry_filter?.map((i) => (
          <span key={i} className="rounded bg-secondary px-2 py-0.5 text-xs">
            {i}
          </span>
        ))}
        {profile.tech_filter?.map((t) => (
          <span key={t} className="rounded bg-secondary px-2 py-0.5 text-xs">
            {t}
          </span>
        ))}
        {profile.geo_filter?.countries.map((c) => (
          <span key={c} className="rounded bg-secondary px-2 py-0.5 text-xs">
            {c}
          </span>
        ))}
      </div>

      <div className="flex items-center justify-between">
        <span className="text-xs text-muted-foreground">
          Created {new Date(profile.created_at).toLocaleDateString()}
        </span>
        <div className="flex gap-1">
          <button
            type="button"
            onClick={onEdit}
            title="Edit"
            className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-accent-foreground"
          >
            <Pencil className="h-4 w-4" />
          </button>
          {profile.is_active ? (
            <button
              type="button"
              onClick={onDeactivate}
              title="Deactivate"
              className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-orange-600"
            >
              <Power className="h-4 w-4" />
            </button>
          ) : (
            <button
              type="button"
              onClick={onActivate}
              title="Activate"
              className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-primary"
            >
              <Power className="h-4 w-4" />
            </button>
          )}
          <button
            type="button"
            onClick={onDelete}
            title="Delete"
            className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-destructive"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Profile Form ───────────────────────────────────────────────────

interface FormState {
  name: string;
  industry_filter: string[];
  min_employees: string;
  max_employees: string;
  min_revenue: string;
  max_revenue: string;
  countries: string[];
  regions: string[];
  cities: string[];
  tech_filter: string[];
  excluded_industries: string[];
  excluded_domains: string[];
}

function emptyForm(): FormState {
  return {
    name: "",
    industry_filter: [],
    min_employees: "",
    max_employees: "",
    min_revenue: "",
    max_revenue: "",
    countries: [],
    regions: [],
    cities: [],
    tech_filter: [],
    excluded_industries: [],
    excluded_domains: [],
  };
}

function profileToForm(p: ICPProfile): FormState {
  return {
    name: p.name,
    industry_filter: p.industry_filter ?? [],
    min_employees: p.size_filter?.min_employees?.toString() ?? "",
    max_employees: p.size_filter?.max_employees?.toString() ?? "",
    min_revenue: p.size_filter?.min_revenue?.toString() ?? "",
    max_revenue: p.size_filter?.max_revenue?.toString() ?? "",
    countries: p.geo_filter?.countries ?? [],
    regions: p.geo_filter?.regions ?? [],
    cities: p.geo_filter?.cities ?? [],
    tech_filter: p.tech_filter ?? [],
    excluded_industries: p.negative_filters?.excluded_industries ?? [],
    excluded_domains: p.negative_filters?.excluded_domains ?? [],
  };
}

function formToPayload(f: FormState): ICPProfileCreate {
  const minEmp = f.min_employees ? Number(f.min_employees) : null;
  const maxEmp = f.max_employees ? Number(f.max_employees) : null;
  const minRev = f.min_revenue ? Number(f.min_revenue) : null;
  const maxRev = f.max_revenue ? Number(f.max_revenue) : null;
  const hasSizeFilter =
    minEmp != null || maxEmp != null || minRev != null || maxRev != null;

  const hasGeo =
    f.countries.length > 0 || f.regions.length > 0 || f.cities.length > 0;

  const hasNegative =
    f.excluded_industries.length > 0 || f.excluded_domains.length > 0;

  return {
    name: f.name,
    industry_filter: f.industry_filter.length ? f.industry_filter : null,
    size_filter: hasSizeFilter
      ? {
          min_employees: minEmp,
          max_employees: maxEmp,
          min_revenue: minRev,
          max_revenue: maxRev,
        }
      : null,
    geo_filter: hasGeo
      ? { countries: f.countries, regions: f.regions, cities: f.cities }
      : null,
    tech_filter: f.tech_filter.length ? f.tech_filter : null,
    negative_filters: hasNegative
      ? {
          excluded_industries: f.excluded_industries,
          excluded_domains: f.excluded_domains,
        }
      : null,
  };
}

function hasPositiveFilter(f: FormState): boolean {
  return (
    f.industry_filter.length > 0 ||
    !!f.min_employees ||
    !!f.max_employees ||
    !!f.min_revenue ||
    !!f.max_revenue ||
    f.countries.length > 0 ||
    f.regions.length > 0 ||
    f.cities.length > 0 ||
    f.tech_filter.length > 0
  );
}

function ProfileForm({
  initial,
  editing,
  loading,
  onSubmit,
  onCancel,
}: {
  initial: FormState;
  editing: boolean;
  loading: boolean;
  onSubmit: (data: ICPProfileCreate) => void;
  onCancel: () => void;
}) {
  const [form, setForm] = useState<FormState>(initial);
  const [error, setError] = useState<string | null>(null);

  function set<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!form.name.trim()) {
      setError("Profile name is required.");
      return;
    }
    if (!hasPositiveFilter(form)) {
      setError(
        "At least one positive filter (industry, size, geo, or tech) is required.",
      );
      return;
    }

    const minEmp = form.min_employees ? Number(form.min_employees) : null;
    const maxEmp = form.max_employees ? Number(form.max_employees) : null;
    if (minEmp != null && maxEmp != null && minEmp >= maxEmp) {
      setError("Min employees must be less than max employees.");
      return;
    }
    const minRev = form.min_revenue ? Number(form.min_revenue) : null;
    const maxRev = form.max_revenue ? Number(form.max_revenue) : null;
    if (minRev != null && maxRev != null && minRev >= maxRev) {
      setError("Min revenue must be less than max revenue.");
      return;
    }

    onSubmit(formToPayload(form));
  }

  const inputClass =
    "w-full rounded-lg border border-input bg-background px-3 py-2.5 text-sm outline-none transition-shadow focus:ring-2 focus:ring-ring/40";

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/50 backdrop-blur-sm p-6">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-2xl rounded-xl border border-border bg-card p-6 shadow-xl animate-enter"
      >
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-lg font-semibold">
            {editing ? "Edit Profile" : "Create New Profile"}
          </h2>
          <button
            type="button"
            onClick={onCancel}
            className="rounded-md p-1 hover:bg-accent"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="space-y-5">
          {/* Name */}
          <div>
            <label className="mb-1 block text-sm font-medium">
              Profile Name
            </label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => set("name", e.target.value)}
              placeholder="e.g. European SaaS Mid-Market"
              className={inputClass}
            />
          </div>

          {/* Industry filter */}
          <div>
            <label className="mb-1 block text-sm font-medium">
              Industry Filter
            </label>
            <TagInput
              value={form.industry_filter}
              onChange={(v) => set("industry_filter", v)}
              placeholder="Add industries..."
              suggestions={COMMON_INDUSTRIES}
            />
          </div>

          {/* Size filter */}
          <fieldset>
            <legend className="mb-2 text-sm font-medium">
              Company Size Range
            </legend>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1 block text-xs text-muted-foreground">
                  Min Employees
                </label>
                <input
                  type="number"
                  min={0}
                  value={form.min_employees}
                  onChange={(e) => set("min_employees", e.target.value)}
                  placeholder="e.g. 10"
                  className={inputClass}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-muted-foreground">
                  Max Employees
                </label>
                <input
                  type="number"
                  min={0}
                  value={form.max_employees}
                  onChange={(e) => set("max_employees", e.target.value)}
                  placeholder="e.g. 500"
                  className={inputClass}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-muted-foreground">
                  Min Revenue (EUR)
                </label>
                <input
                  type="number"
                  min={0}
                  value={form.min_revenue}
                  onChange={(e) => set("min_revenue", e.target.value)}
                  placeholder="e.g. 1000000"
                  className={inputClass}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-muted-foreground">
                  Max Revenue (EUR)
                </label>
                <input
                  type="number"
                  min={0}
                  value={form.max_revenue}
                  onChange={(e) => set("max_revenue", e.target.value)}
                  placeholder="e.g. 50000000"
                  className={inputClass}
                />
              </div>
            </div>
          </fieldset>

          {/* Geo filter */}
          <fieldset>
            <legend className="mb-2 text-sm font-medium">
              Geographic Filter
            </legend>
            <div className="space-y-3">
              <div>
                <label className="mb-1 block text-xs text-muted-foreground">
                  Countries
                </label>
                <TagInput
                  value={form.countries}
                  onChange={(v) => set("countries", v)}
                  placeholder="Add countries..."
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-muted-foreground">
                  Regions
                </label>
                <TagInput
                  value={form.regions}
                  onChange={(v) => set("regions", v)}
                  placeholder="Add regions..."
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-muted-foreground">
                  Cities
                </label>
                <TagInput
                  value={form.cities}
                  onChange={(v) => set("cities", v)}
                  placeholder="Add cities..."
                />
              </div>
            </div>
          </fieldset>

          {/* Tech filter */}
          <div>
            <label className="mb-1 block text-sm font-medium">
              Technology Stack Filter
            </label>
            <TagInput
              value={form.tech_filter}
              onChange={(v) => set("tech_filter", v)}
              placeholder="Add technologies..."
            />
          </div>

          {/* Negative filters */}
          <fieldset>
            <legend className="mb-2 text-sm font-medium">
              Negative Filters (Exclusions)
            </legend>
            <div className="space-y-3">
              <div>
                <label className="mb-1 block text-xs text-muted-foreground">
                  Excluded Industries
                </label>
                <TagInput
                  value={form.excluded_industries}
                  onChange={(v) => set("excluded_industries", v)}
                  placeholder="Industries to exclude..."
                  suggestions={COMMON_INDUSTRIES}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-muted-foreground">
                  Excluded Domains
                </label>
                <TagInput
                  value={form.excluded_domains}
                  onChange={(v) => set("excluded_domains", v)}
                  placeholder="Domains to exclude (one per entry)..."
                />
              </div>
            </div>
          </fieldset>
        </div>

        {error && (
          <p className="mt-4 text-sm text-destructive">{error}</p>
        )}

        <div className="mt-6 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            disabled={loading}
            className="rounded-lg border border-input px-4 py-2 text-sm transition-colors hover:bg-accent"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={loading}
            className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-all hover:bg-primary/90 disabled:opacity-50"
          >
            {loading && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            {editing ? "Save Changes" : "Create Profile"}
          </button>
        </div>
      </form>
    </div>
  );
}

// ── Main Page ──────────────────────────────────────────────────────

export default function ICP() {
  const { data: profiles, isLoading, error } = useICPProfiles();
  const createMutation = useCreateProfile();
  const updateMutation = useUpdateProfile();
  const activateMutation = useActivateProfile();
  const deactivateMutation = useDeactivateProfile();
  const deleteMutation = useDeleteProfile();

  const [formOpen, setFormOpen] = useState(false);
  const [editingProfile, setEditingProfile] = useState<ICPProfile | null>(null);
  const [activateTarget, setActivateTarget] = useState<ICPProfile | null>(null);
  const [deactivateTarget, setDeactivateTarget] = useState<ICPProfile | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ICPProfile | null>(null);

  function openCreate() {
    setEditingProfile(null);
    setFormOpen(true);
  }

  function openEdit(profile: ICPProfile) {
    setEditingProfile(profile);
    setFormOpen(true);
  }

  function closeForm() {
    setFormOpen(false);
    setEditingProfile(null);
  }

  function handleSubmit(data: ICPProfileCreate) {
    if (editingProfile) {
      updateMutation.mutate(
        { id: editingProfile.id, ...data },
        { onSuccess: closeForm },
      );
    } else {
      createMutation.mutate(data, { onSuccess: closeForm });
    }
  }

  function handleActivate() {
    if (!activateTarget) return;
    activateMutation.mutate(activateTarget.id, {
      onSuccess: () => setActivateTarget(null),
    });
  }

  function handleDeactivate() {
    if (!deactivateTarget) return;
    deactivateMutation.mutate(deactivateTarget.id, {
      onSuccess: () => setDeactivateTarget(null),
    });
  }

  function handleDelete() {
    if (!deleteTarget) return;
    deleteMutation.mutate(deleteTarget.id, {
      onSuccess: () => setDeleteTarget(null),
    });
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl tracking-tight">Ideal Customer Profile</h1>
          <p className="mt-1 text-sm text-muted-foreground" style={{ fontFamily: '"DM Sans", system-ui, sans-serif' }}>
            Define and manage ICP profiles that drive the discovery engine.
          </p>
        </div>
        <button
          type="button"
          onClick={openCreate}
          className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-sm transition-all hover:bg-primary/90 hover:shadow-md active:scale-[0.98]"
        >
          <Plus className="h-4 w-4" />
          Create New Profile
        </button>
      </div>

      <div className="mb-8 rounded-xl border bg-muted/40 p-5 text-sm text-muted-foreground">
        <p className="mb-2 font-medium text-foreground">What is an ICP profile?</p>
        <p className="mb-3">
          An Ideal Customer Profile (ICP) describes the type of company most likely to benefit from your product. It acts as a filter for the discovery engine — only companies that match the active profile are surfaced as leads.
        </p>
        <p className="font-medium text-foreground">How it works</p>
        <ul className="mt-2 list-inside list-disc space-y-1">
          <li>Create one or more profiles with filters such as industry, company size, geography, and tech stack.</li>
          <li>Mark one profile as <span className="font-medium text-foreground">active</span> — this is the profile the discovery engine uses when finding new leads.</li>
          <li>Only one profile can be active at a time. Switching the active profile takes effect immediately.</li>
        </ul>
      </div>

      {isLoading && (
        <div className="flex items-center gap-2 py-12 text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin" />
          Loading profiles...
        </div>
      )}

      {error && (
        <p className="py-12 text-sm text-destructive">
          Failed to load profiles. Please try again.
        </p>
      )}

      {profiles && profiles.length === 0 && (
        <div className="rounded-xl border border-dashed border-border py-16 text-center animate-fade-in">
          <p className="text-muted-foreground">
            No ICP profiles yet. Create one to get started.
          </p>
        </div>
      )}

      {profiles && profiles.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {profiles.map((profile) => (
            <ProfileCard
              key={profile.id}
              profile={profile}
              onEdit={() => openEdit(profile)}
              onActivate={() => setActivateTarget(profile)}
              onDeactivate={() => setDeactivateTarget(profile)}
              onDelete={() => setDeleteTarget(profile)}
            />
          ))}
        </div>
      )}

      {/* Create / Edit form */}
      {formOpen && (
        <ProfileForm
          initial={editingProfile ? profileToForm(editingProfile) : emptyForm()}
          editing={!!editingProfile}
          loading={createMutation.isPending || updateMutation.isPending}
          onSubmit={handleSubmit}
          onCancel={closeForm}
        />
      )}

      {/* Activate confirmation */}
      <ConfirmDialog
        open={!!activateTarget}
        title="Activate Profile"
        message={`This will deactivate the current active profile and activate "${activateTarget?.name}". The discovery engine will use this profile's filters.`}
        confirmLabel="Activate"
        loading={activateMutation.isPending}
        onConfirm={handleActivate}
        onCancel={() => setActivateTarget(null)}
      />

      {/* Deactivate confirmation */}
      <ConfirmDialog
        open={!!deactivateTarget}
        title="Deactivate Profile"
        message={`This will deactivate "${deactivateTarget?.name}". The discovery engine will not use any ICP profile until you activate one.`}
        confirmLabel="Deactivate"
        loading={deactivateMutation.isPending}
        onConfirm={handleDeactivate}
        onCancel={() => setDeactivateTarget(null)}
      />

      {/* Delete confirmation */}
      <ConfirmDialog
        open={!!deleteTarget}
        title="Delete Profile"
        message={`Are you sure you want to delete "${deleteTarget?.name}"? This action cannot be undone.`}
        confirmLabel="Delete"
        destructive
        loading={deleteMutation.isPending}
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
      />

      {/* Active profile indicator */}
      {profiles?.some((p) => p.is_active) && (
        <div className="mt-6 flex items-center gap-2 rounded-xl bg-primary/5 px-4 py-3 text-sm border border-primary/10">
          <Check className="h-4 w-4 text-primary" />
          <span>
            Active profile:{" "}
            <strong>{profiles.find((p) => p.is_active)?.name}</strong>
          </span>
        </div>
      )}
    </div>
  );
}
