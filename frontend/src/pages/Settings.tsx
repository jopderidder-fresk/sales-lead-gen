import { CustomSelect } from "@/components/Select";
import {
  useAPIKeysSettings,
  useUpdateAPIKeysSettings,
  useCRMSettings,
  useUpdateCRMSettings,
  useJobs,
  useToggleJob,
  useLinkedInSettings,
  useUpdateLinkedInSettings,
  useSlackSettings,
  useUpdateSlackSettings,
  useTestSlackNotification,
  useUsageLimits,
  useUpdateUsageLimits,
} from "@/lib/settings";
import type { APIKeyStatus } from "@/types/api";
import {
  AlertTriangle,
  Check,
  Clock,
  KeyRound,
  Loader2,
  Power,
  Rss,
  Send,
  Shield,
} from "lucide-react";
import { useAuth } from "@/context/auth";
import { useEffect, useState } from "react";

// ── Shared styles ──────────────────────────────────────────────────

const inputClass =
  "w-full rounded-lg border border-input bg-background px-3 py-2.5 text-sm outline-none transition-shadow focus:ring-2 focus:ring-ring/40";

const cardClass = "rounded-xl border border-border bg-card p-6 shadow-sm";

const labelClass = "block text-sm font-medium mb-1.5";

const btnPrimary =
  "inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-sm transition-all hover:bg-primary/90 hover:shadow-md active:scale-[0.98] disabled:opacity-50";

const btnSecondary =
  "inline-flex items-center gap-2 rounded-lg border border-input bg-card px-4 py-2 text-sm font-medium shadow-sm transition-all hover:bg-muted disabled:opacity-50";

// ── Secret field helper ───────────────────────────────────────────

function SecretField({
  label,
  status,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  status: APIKeyStatus | undefined;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <div>
      <label className={labelClass}>
        {label}{" "}
        {status?.key_set && (
          <span className="text-xs text-green-600">(configured)</span>
        )}
      </label>
      <input
        type="password"
        className={inputClass}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={
          status?.key_set
            ? "Leave empty to keep current key"
            : placeholder ?? "Enter key..."
        }
      />
      {status?.preview && (
        <div className="mt-1.5 flex items-center gap-1.5 rounded bg-muted/50 px-2 py-1">
          <KeyRound className="h-3 w-3 shrink-0 text-muted-foreground/70" />
          <code className="truncate text-[11px] text-muted-foreground">
            {status.preview}
          </code>
        </div>
      )}
    </div>
  );
}

// ── API Keys Card ─────────────────────────────────────────────────

const LLM_PROVIDERS = [
  { value: "anthropic", label: "Anthropic" },
  { value: "openrouter", label: "OpenRouter" },
  { value: "gemini", label: "Gemini" },
  { value: "google_vertex", label: "Google Vertex" },
];

function APIKeysCard() {
  const { data, isLoading, error } = useAPIKeysSettings();
  const update = useUpdateAPIKeysSettings();

  const [form, setForm] = useState({
    llm_provider: "anthropic",
    anthropic_api_key: "",
    openrouter_api_key: "",
    openrouter_model: "",
    gemini_api_key: "",
    firecrawl_api_key: "",
    hunter_io_api_key: "",
    apollo_api_key: "",
    scrapin_api_key: "",
    bedrijfsdata_api_key: "",
    apify_api_token: "",
  });
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (data) {
      setForm((f) => ({
        ...f,
        llm_provider: data.llm_provider,
        openrouter_model: data.openrouter_model,
      }));
    }
  }, [data]);

  function handleSave() {
    setSaved(false);
    const body: Record<string, string> = { llm_provider: form.llm_provider };

    // Only include non-empty key fields
    if (form.openrouter_model) body.openrouter_model = form.openrouter_model;
    if (form.anthropic_api_key) body.anthropic_api_key = form.anthropic_api_key;
    if (form.openrouter_api_key) body.openrouter_api_key = form.openrouter_api_key;
    if (form.gemini_api_key) body.gemini_api_key = form.gemini_api_key;
    if (form.firecrawl_api_key) body.firecrawl_api_key = form.firecrawl_api_key;
    if (form.hunter_io_api_key) body.hunter_io_api_key = form.hunter_io_api_key;
    if (form.apollo_api_key) body.apollo_api_key = form.apollo_api_key;
    if (form.scrapin_api_key) body.scrapin_api_key = form.scrapin_api_key;
    if (form.bedrijfsdata_api_key) body.bedrijfsdata_api_key = form.bedrijfsdata_api_key;
    if (form.apify_api_token) body.apify_api_token = form.apify_api_token;

    update.mutate(body, {
      onSuccess: () => {
        setSaved(true);
        // Clear all secret inputs after save
        setForm((f) => ({
          ...f,
          anthropic_api_key: "",
          openrouter_api_key: "",
          gemini_api_key: "",
          firecrawl_api_key: "",
          hunter_io_api_key: "",
          apollo_api_key: "",
          scrapin_api_key: "",
          bedrijfsdata_api_key: "",
          apify_api_token: "",
        }));
        setTimeout(() => setSaved(false), 3000);
      },
    });
  }

  if (isLoading) {
    return (
      <div className={cardClass}>
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading API key settings...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={cardClass}>
        <div className="flex items-center gap-2 text-destructive">
          <AlertTriangle className="h-4 w-4" />
          Failed to load API key settings
        </div>
      </div>
    );
  }

  // Count how many keys are set
  const keyStatuses = data
    ? [
        data.anthropic,
        data.openrouter,
        data.gemini,
        data.firecrawl,
        data.hunter_io,
        data.apollo,
        data.scrapin,
        data.bedrijfsdata,
      ]
    : [];
  const keysConfigured = keyStatuses.filter((s) => s.key_set).length;

  return (
    <div className={cardClass}>
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">API Keys</h2>
          <p className="text-sm text-muted-foreground">
            Configure external API keys for LLM, enrichment, and scraping services.
            Keys are encrypted at rest.
          </p>
        </div>
        <span
          className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${
            keysConfigured > 0
              ? "bg-green-50 text-green-700 ring-green-200"
              : "bg-yellow-50 text-yellow-700 ring-yellow-200"
          }`}
        >
          <KeyRound className="h-3 w-3" />
          {keysConfigured} key{keysConfigured !== 1 ? "s" : ""} set
        </span>
      </div>

      {/* LLM Provider */}
      <div className="mb-5">
        <p className="mb-3 text-xs font-medium uppercase tracking-wider text-muted-foreground">
          LLM Provider
        </p>
        <div className="mb-4">
          <label className={labelClass}>Active Provider</label>
          <CustomSelect
            options={LLM_PROVIDERS}
            value={form.llm_provider}
            onChange={(v) => setForm({ ...form, llm_provider: String(v) })}
          />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <SecretField
            label="Anthropic API Key"
            status={data?.anthropic}
            value={form.anthropic_api_key}
            onChange={(v) => setForm({ ...form, anthropic_api_key: v })}
            placeholder="sk-ant-..."
          />
          <SecretField
            label="OpenRouter API Key"
            status={data?.openrouter}
            value={form.openrouter_api_key}
            onChange={(v) => setForm({ ...form, openrouter_api_key: v })}
            placeholder="sk-or-..."
          />
          <div>
            <label className={labelClass}>OpenRouter Model</label>
            <input
              type="text"
              className={inputClass}
              value={form.openrouter_model}
              onChange={(e) =>
                setForm({ ...form, openrouter_model: e.target.value })
              }
              placeholder="e.g. minimax/minimax-m2.5:free"
            />
          </div>
          <SecretField
            label="Gemini API Key"
            status={data?.gemini}
            value={form.gemini_api_key}
            onChange={(v) => setForm({ ...form, gemini_api_key: v })}
            placeholder="AIza..."
          />
        </div>
      </div>

      {/* Enrichment & Scraping */}
      <div className="mb-5">
        <p className="mb-3 text-xs font-medium uppercase tracking-wider text-muted-foreground">
          Enrichment & Scraping
        </p>
        <div className="grid gap-4 sm:grid-cols-2">
          <SecretField
            label="Firecrawl API Key"
            status={data?.firecrawl}
            value={form.firecrawl_api_key}
            onChange={(v) => setForm({ ...form, firecrawl_api_key: v })}
            placeholder="fc-..."
          />
          <SecretField
            label="Hunter.io API Key"
            status={data?.hunter_io}
            value={form.hunter_io_api_key}
            onChange={(v) => setForm({ ...form, hunter_io_api_key: v })}
          />
          <SecretField
            label="Apollo API Key"
            status={data?.apollo}
            value={form.apollo_api_key}
            onChange={(v) => setForm({ ...form, apollo_api_key: v })}
          />
          <SecretField
            label="Scrapin API Key"
            status={data?.scrapin}
            value={form.scrapin_api_key}
            onChange={(v) => setForm({ ...form, scrapin_api_key: v })}
          />
          <SecretField
            label="Bedrijfsdata API Key"
            status={data?.bedrijfsdata}
            value={form.bedrijfsdata_api_key}
            onChange={(v) => setForm({ ...form, bedrijfsdata_api_key: v })}
          />
        </div>
      </div>

      {/* Apify (LinkedIn scraping) */}
      <div className="mb-5">
        <p className="mb-3 text-xs font-medium uppercase tracking-wider text-muted-foreground">
          Apify (LinkedIn)
        </p>
        <SecretField
          label="API Token"
          status={data?.apify}
          value={form.apify_api_token}
          onChange={(v) => setForm({ ...form, apify_api_token: v })}
          placeholder="apify_api_..."
        />
      </div>

      <div className="flex items-center gap-3">
        <button
          className={btnPrimary}
          onClick={handleSave}
          disabled={update.isPending}
        >
          {update.isPending && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
          Save API Keys
        </button>
        {saved && (
          <span className="flex items-center gap-1 text-sm text-green-600">
            <Check className="h-3.5 w-3.5" /> Saved
          </span>
        )}
        {update.isError && (
          <span className="text-sm text-destructive">
            Failed to save — check your permissions.
          </span>
        )}
      </div>
    </div>
  );
}

// ── CRM Settings Card ─────────────────────────────────────────────

const PROVIDER_META: Record<string, { label: string; description: string; color: string }> = {
  clickup: {
    label: "ClickUp",
    description: "Sync leads as tasks in your ClickUp workspace",
    color: "bg-violet-500",
  },
};

function CRMCard() {
  const { data, isLoading, error } = useCRMSettings();
  const update = useUpdateCRMSettings();

  const [provider, setProvider] = useState("");
  const [clickupForm, setClickupForm] = useState({
    api_key: "",
    workspace_id: "",
    space_id: "",
    folder_id: "",
    list_id: "",
    domain_field_id: "",
    person_list_id: "",
    person_email_field_id: "",
    person_phone_field_id: "",
    person_linkedin_field_id: "",
    person_surname_field_id: "",
    person_lastname_field_id: "",
    person_role_field_id: "",
    contact_relationship_field_id: "",
    company_contact_field_id: "",
  });
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (data) {
      setProvider(data.provider);
      if (data.clickup) {
        setClickupForm({
          api_key: "",
          workspace_id: data.clickup.workspace_id,
          space_id: data.clickup.space_id,
          folder_id: data.clickup.folder_id,
          list_id: data.clickup.list_id,
          domain_field_id: data.clickup.domain_field_id,
          person_list_id: data.clickup.person_list_id,
          person_email_field_id: data.clickup.person_email_field_id,
          person_phone_field_id: data.clickup.person_phone_field_id,
          person_linkedin_field_id: data.clickup.person_linkedin_field_id,
          person_surname_field_id: data.clickup.person_surname_field_id,
          person_lastname_field_id: data.clickup.person_lastname_field_id,
          person_role_field_id: data.clickup.person_role_field_id,
          contact_relationship_field_id: data.clickup.contact_relationship_field_id,
          company_contact_field_id: data.clickup.company_contact_field_id,
        });
      }
    }
  }, [data]);

  function handleSave() {
    setSaved(false);
    const body: Record<string, string> = { provider };
    if (provider === "clickup") {
      if (clickupForm.api_key) body.clickup_api_key = clickupForm.api_key;
      body.clickup_workspace_id = clickupForm.workspace_id;
      body.clickup_space_id = clickupForm.space_id;
      body.clickup_folder_id = clickupForm.folder_id;
      body.clickup_list_id = clickupForm.list_id;
      body.clickup_domain_field_id = clickupForm.domain_field_id;
      body.clickup_person_list_id = clickupForm.person_list_id;
      body.clickup_person_email_field_id = clickupForm.person_email_field_id;
      body.clickup_person_phone_field_id = clickupForm.person_phone_field_id;
      body.clickup_person_linkedin_field_id = clickupForm.person_linkedin_field_id;
      body.clickup_person_surname_field_id = clickupForm.person_surname_field_id;
      body.clickup_person_lastname_field_id = clickupForm.person_lastname_field_id;
      body.clickup_person_role_field_id = clickupForm.person_role_field_id;
      body.clickup_contact_relationship_field_id = clickupForm.contact_relationship_field_id;
      body.clickup_company_contact_field_id = clickupForm.company_contact_field_id;
    }
    update.mutate(body, {
      onSuccess: () => {
        setSaved(true);
        setClickupForm((f) => ({ ...f, api_key: "" }));
        setTimeout(() => setSaved(false), 3000);
      },
    });
  }

  if (isLoading) {
    return (
      <div className={cardClass}>
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading CRM settings...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={cardClass}>
        <div className="flex items-center gap-2 text-destructive">
          <AlertTriangle className="h-4 w-4" />
          Failed to load CRM settings
        </div>
      </div>
    );
  }

  return (
    <div className={cardClass}>
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">CRM Integration</h2>
          <p className="text-sm text-muted-foreground">
            Choose your CRM provider and configure credentials for lead sync.
          </p>
        </div>
        <StatusBadge configured={data?.configured ?? false} label="CRM" />
      </div>

      {/* Provider selector */}
      <div className="mb-5">
        <label className={labelClass}>CRM Provider</label>
        <div className="mt-1 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => setProvider("")}
            className={`flex items-center gap-2.5 rounded-lg border px-4 py-2.5 text-sm font-medium transition-all ${
              provider === ""
                ? "border-primary bg-primary/5 text-primary ring-2 ring-primary/20"
                : "border-border bg-card text-muted-foreground hover:border-muted-foreground/30 hover:bg-muted/50"
            }`}
          >
            <span className="flex h-5 w-5 items-center justify-center rounded-full border-2 border-current">
              {provider === "" && <span className="h-2.5 w-2.5 rounded-full bg-primary" />}
            </span>
            None
          </button>
          {(data?.available_providers ?? []).map((prov) => {
            const meta = PROVIDER_META[prov];
            const isSelected = provider === prov;
            return (
              <button
                key={prov}
                type="button"
                onClick={() => setProvider(prov)}
                className={`flex items-center gap-2.5 rounded-lg border px-4 py-2.5 text-sm font-medium transition-all ${
                  isSelected
                    ? "border-primary bg-primary/5 text-primary ring-2 ring-primary/20"
                    : "border-border bg-card text-muted-foreground hover:border-muted-foreground/30 hover:bg-muted/50"
                }`}
              >
                <span className="flex h-5 w-5 items-center justify-center rounded-full border-2 border-current">
                  {isSelected && <span className="h-2.5 w-2.5 rounded-full bg-primary" />}
                </span>
                <span className="flex items-center gap-2">
                  {meta && <span className={`h-2 w-2 rounded-full ${meta.color}`} />}
                  {meta?.label ?? prov}
                </span>
              </button>
            );
          })}
        </div>
        {provider && PROVIDER_META[provider] && (
          <p className="mt-2 text-xs text-muted-foreground">
            {PROVIDER_META[provider].description}
          </p>
        )}
      </div>

      {/* ClickUp fields */}
      {provider === "clickup" && (
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <label className={labelClass}>
              API Key{" "}
              {data?.clickup?.api_key_set && (
                <span className="text-xs text-green-600">(configured)</span>
              )}
            </label>
            <input
              type="password"
              className={inputClass}
              value={clickupForm.api_key}
              onChange={(e) =>
                setClickupForm({ ...clickupForm, api_key: e.target.value })
              }
              placeholder={
                data?.clickup?.api_key_set
                  ? "Leave empty to keep current key"
                  : "pk_..."
              }
            />
            {data?.clickup?.api_key_preview && (
              <div className="mt-1.5 flex items-center gap-1.5 rounded bg-muted/50 px-2 py-1">
                <KeyRound className="h-3 w-3 shrink-0 text-muted-foreground/70" />
                <code className="truncate text-[11px] text-muted-foreground">
                  {data.clickup.api_key_preview}
                </code>
              </div>
            )}
          </div>
          <div>
            <label className={labelClass}>Workspace ID</label>
            <input
              type="text"
              className={inputClass}
              value={clickupForm.workspace_id}
              onChange={(e) =>
                setClickupForm({ ...clickupForm, workspace_id: e.target.value })
              }
              placeholder="e.g. 12345678"
            />
          </div>
          <div>
            <label className={labelClass}>Space ID</label>
            <input
              type="text"
              className={inputClass}
              value={clickupForm.space_id}
              onChange={(e) =>
                setClickupForm({ ...clickupForm, space_id: e.target.value })
              }
              placeholder="e.g. 42410352"
            />
          </div>
          <div>
            <label className={labelClass}>Folder ID</label>
            <input
              type="text"
              className={inputClass}
              value={clickupForm.folder_id}
              onChange={(e) =>
                setClickupForm({ ...clickupForm, folder_id: e.target.value })
              }
              placeholder="e.g. 901210088035"
            />
          </div>
          <div>
            <label className={labelClass}>List ID</label>
            <input
              type="text"
              className={inputClass}
              value={clickupForm.list_id}
              onChange={(e) =>
                setClickupForm({ ...clickupForm, list_id: e.target.value })
              }
              placeholder="e.g. 901216671828"
            />
          </div>
          <div>
            <label className={labelClass}>Domain Field ID</label>
            <input
              type="text"
              className={inputClass}
              value={clickupForm.domain_field_id}
              onChange={(e) =>
                setClickupForm({ ...clickupForm, domain_field_id: e.target.value })
              }
              placeholder="Optional — for domain-based deduplication"
            />
          </div>

          {/* Person Task Settings */}
          <div className="sm:col-span-2 mt-4 border-t border-border pt-4">
            <h3 className="text-sm font-semibold mb-1">Person Task Settings</h3>
            <p className="text-xs text-muted-foreground mb-3">
              Push contacts as separate Person tasks and link them to company tasks.
            </p>
          </div>
          {([
            ["person_list_id", "Person List ID", "ClickUp list ID for Person tasks"],
            ["person_email_field_id", "Person Email Field ID", "Custom field ID for email"],
            ["person_phone_field_id", "Person Phone Field ID", "Custom field ID for phone"],
            ["person_linkedin_field_id", "Person LinkedIn Field ID", "Custom field ID for LinkedIn URL"],
            ["person_surname_field_id", "Person Surname Field ID", "Custom field ID for first name"],
            ["person_lastname_field_id", "Person Last Name Field ID", "Custom field ID for last name"],
            ["person_role_field_id", "Person Role Field ID", "Custom field ID for role/title"],
          ] as const).map(([key, lbl, ph]) => (
            <div key={key}>
              <label className={labelClass}>{lbl}</label>
              <input
                type="text"
                className={inputClass}
                value={clickupForm[key]}
                onChange={(e) => setClickupForm({ ...clickupForm, [key]: e.target.value })}
                placeholder={ph}
              />
            </div>
          ))}
          <div className="sm:col-span-2 mt-2 border-t border-border pt-4">
            <h3 className="text-sm font-semibold mb-1">Relationship Fields</h3>
            <p className="text-xs text-muted-foreground mb-3">
              Link Person tasks to Company tasks bidirectionally.
            </p>
          </div>
          {([
            ["contact_relationship_field_id", "Contact Relationship Field ID", "Person \u2192 Company ('Customer' field)"],
            ["company_contact_field_id", "Company Contact Field ID", "Company \u2192 Person ('Contact and role' field)"],
          ] as const).map(([key, lbl, ph]) => (
            <div key={key}>
              <label className={labelClass}>{lbl}</label>
              <input
                type="text"
                className={inputClass}
                value={clickupForm[key]}
                onChange={(e) => setClickupForm({ ...clickupForm, [key]: e.target.value })}
                placeholder={ph}
              />
            </div>
          ))}
        </div>
      )}

      <div className="mt-5 flex items-center gap-3">
        <button
          className={btnPrimary}
          onClick={handleSave}
          disabled={update.isPending}
        >
          {update.isPending && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
          Save CRM Settings
        </button>
        {saved && (
          <span className="flex items-center gap-1 text-sm text-green-600">
            <Check className="h-3.5 w-3.5" /> Saved
          </span>
        )}
        {update.isError && (
          <span className="text-sm text-destructive">
            Failed to save — check your permissions.
          </span>
        )}
      </div>
    </div>
  );
}

// ── Slack Settings Card ────────────────────────────────────────────

const DAY_LABELS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

function SlackCard() {
  const { data, isLoading, error } = useSlackSettings();
  const update = useUpdateSlackSettings();
  const testSlack = useTestSlackNotification();

  const [form, setForm] = useState({
    webhook_url: "",
    digest_webhook_url: "",
    digest_hour: 9,
    weekly_day: 0,
  });
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (data) {
      setForm({
        webhook_url: "",
        digest_webhook_url: "",
        digest_hour: data.digest_hour,
        weekly_day: data.weekly_day,
      });
    }
  }, [data]);

  function handleSave() {
    setSaved(false);
    const body: Record<string, string | number> = {
      digest_hour: form.digest_hour,
      weekly_day: form.weekly_day,
    };
    if (form.webhook_url) body.webhook_url = form.webhook_url;
    if (form.digest_webhook_url)
      body.digest_webhook_url = form.digest_webhook_url;

    update.mutate(body, {
      onSuccess: () => {
        setSaved(true);
        setForm((f) => ({ ...f, webhook_url: "", digest_webhook_url: "" }));
        setTimeout(() => setSaved(false), 3000);
      },
    });
  }

  if (isLoading) {
    return (
      <div className={cardClass}>
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading Slack settings...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={cardClass}>
        <div className="flex items-center gap-2 text-destructive">
          <AlertTriangle className="h-4 w-4" />
          Failed to load Slack settings
        </div>
      </div>
    );
  }

  return (
    <div className={cardClass}>
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Slack Integration</h2>
          <p className="text-sm text-muted-foreground">
            Configure Slack webhook URLs and digest schedule.
          </p>
        </div>
        <StatusBadge configured={data?.configured ?? false} label="Webhooks" />
      </div>

      <div className="grid gap-4">
        <div>
          <label className={labelClass}>
            Webhook URL{" "}
            {data?.webhook_url_set && (
              <span className="text-xs text-green-600">(configured)</span>
            )}
          </label>
          <input
            type="text"
            className={inputClass}
            value={form.webhook_url}
            onChange={(e) => setForm({ ...form, webhook_url: e.target.value })}
            placeholder={
              data?.webhook_url_set
                ? "Leave empty to keep current URL"
                : "https://hooks.slack.com/services/..."
            }
          />
          {data?.webhook_url_preview && (
            <div className="mt-1.5 flex items-center gap-1.5 rounded bg-muted/50 px-2 py-1">
              <KeyRound className="h-3 w-3 shrink-0 text-muted-foreground/70" />
              <code className="truncate text-[11px] text-muted-foreground">
                {data.webhook_url_preview}
              </code>
            </div>
          )}
        </div>
        <div>
          <label className={labelClass}>
            Digest Webhook URL{" "}
            {data?.digest_webhook_url_set && (
              <span className="text-xs text-green-600">(configured)</span>
            )}
          </label>
          <input
            type="text"
            className={inputClass}
            value={form.digest_webhook_url}
            onChange={(e) =>
              setForm({ ...form, digest_webhook_url: e.target.value })
            }
            placeholder={
              data?.digest_webhook_url_set
                ? "Leave empty to keep current URL"
                : "https://hooks.slack.com/services/..."
            }
          />
          {data?.digest_webhook_url_preview && (
            <div className="mt-1.5 flex items-center gap-1.5 rounded bg-muted/50 px-2 py-1">
              <KeyRound className="h-3 w-3 shrink-0 text-muted-foreground/70" />
              <code className="truncate text-[11px] text-muted-foreground">
                {data.digest_webhook_url_preview}
              </code>
            </div>
          )}
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className={labelClass}>Daily Digest Hour (UTC)</label>
            <CustomSelect
              options={Array.from({ length: 24 }, (_, i) => ({
                value: i,
                label: `${String(i).padStart(2, "0")}:00 UTC`,
              }))}
              value={form.digest_hour}
              onChange={(v) => setForm({ ...form, digest_hour: Number(v) })}
            />
          </div>
          <div>
            <label className={labelClass}>Weekly Summary Day</label>
            <CustomSelect
              options={DAY_LABELS.map((label, i) => ({ value: i, label }))}
              value={form.weekly_day}
              onChange={(v) => setForm({ ...form, weekly_day: Number(v) })}
            />
          </div>
        </div>
      </div>

      <div className="mt-5 flex flex-wrap items-center gap-3">
        <button
          className={btnPrimary}
          onClick={handleSave}
          disabled={update.isPending}
        >
          {update.isPending && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
          Save Slack Settings
        </button>
        <button
          className={btnSecondary}
          onClick={() => testSlack.mutate()}
          disabled={testSlack.isPending || !data?.webhook_url_set}
        >
          {testSlack.isPending ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Send className="h-3.5 w-3.5" />
          )}
          Send Test
        </button>
        {saved && (
          <span className="flex items-center gap-1 text-sm text-green-600">
            <Check className="h-3.5 w-3.5" /> Saved
          </span>
        )}
        {update.isError && (
          <span className="text-sm text-destructive">
            Failed to save — check your permissions.
          </span>
        )}
        {testSlack.isSuccess && (
          <span
            className={`text-sm ${testSlack.data?.success ? "text-green-600" : "text-destructive"}`}
          >
            {testSlack.data?.message}
          </span>
        )}
        {testSlack.isError && (
          <span className="text-sm text-destructive">
            Test notification failed.
          </span>
        )}
      </div>
    </div>
  );
}

// ── Job Schedule Card ──────────────────────────────────────────────

function JobScheduleCard() {
  const { isAdmin } = useAuth();
  const { data, isLoading, error } = useJobs();
  const toggle = useToggleJob();

  if (!isAdmin) return null;

  if (isLoading) {
    return (
      <div className={cardClass}>
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading job schedule...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={cardClass}>
        <div className="flex items-center gap-2 text-destructive">
          <AlertTriangle className="h-4 w-4" />
          Failed to load job schedule
        </div>
      </div>
    );
  }

  const enabledCount = data?.jobs.filter((j) => j.enabled).length ?? 0;
  const totalCount = data?.jobs.length ?? 0;

  return (
    <div className={cardClass}>
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Scheduled Jobs</h2>
          <p className="text-sm text-muted-foreground">
            Enable or disable background jobs to control costs.
          </p>
        </div>
        <span className="inline-flex items-center gap-1.5 rounded-md bg-blue-50 px-2.5 py-0.5 text-xs font-medium text-blue-700 ring-1 ring-inset ring-blue-200">
          <Power className="h-3 w-3" />
          {enabledCount}/{totalCount} active
        </span>
      </div>

      <div className="divide-y divide-border rounded-lg border border-border">
        {data?.jobs.map((job) => (
          <div
            key={job.name}
            className="flex items-center justify-between gap-4 px-4 py-3"
          >
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">{job.name}</span>
                <span className="inline-flex items-center gap-1 rounded bg-muted px-1.5 py-0.5 text-[11px] text-muted-foreground">
                  <Clock className="h-2.5 w-2.5" />
                  {job.schedule}
                </span>
              </div>
              <p className="mt-0.5 text-xs text-muted-foreground">
                {job.description}
              </p>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={job.enabled}
              disabled={toggle.isPending}
              onClick={() =>
                toggle.mutate({
                  jobName: job.name,
                  enabled: !job.enabled,
                })
              }
              className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 ${
                job.enabled ? "bg-primary" : "bg-muted"
              }`}
            >
              <span
                className={`pointer-events-none block h-5 w-5 rounded-full bg-white shadow-lg ring-0 transition-transform ${
                  job.enabled ? "translate-x-5" : "translate-x-0"
                }`}
              />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── LinkedIn Card ─────────────────────────────────────────────────

function LinkedInCard() {
  const { isAdmin } = useAuth();
  const { data, isLoading, error } = useLinkedInSettings();
  const update = useUpdateLinkedInSettings();
  const [form, setForm] = useState({ interval_days: 7, days_back: 7, daily_scrape_limit: 50 });
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (data) {
      setForm({
        interval_days: data.interval_days,
        days_back: data.days_back,
        daily_scrape_limit: data.daily_scrape_limit,
      });
    }
  }, [data]);

  if (!isAdmin) return null;

  if (isLoading) {
    return (
      <div className={cardClass}>
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading LinkedIn settings...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={cardClass}>
        <div className="flex items-center gap-2 text-destructive">
          <AlertTriangle className="h-4 w-4" />
          Failed to load LinkedIn settings
        </div>
      </div>
    );
  }

  const handleToggle = () => {
    if (data) update.mutate({ enabled: !data.enabled });
  };

  const handleSave = () => {
    update.mutate(form, {
      onSuccess: () => {
        setSaved(true);
        setTimeout(() => setSaved(false), 3000);
      },
    });
  };

  return (
    <div className={cardClass}>
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">LinkedIn Scraping</h2>
          <p className="text-sm text-muted-foreground">
            Periodically scrape LinkedIn posts for tracked companies to discover
            signals.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span
            className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${
              data?.enabled
                ? "bg-green-50 text-green-700 ring-green-200"
                : "bg-yellow-50 text-yellow-700 ring-yellow-200"
            }`}
          >
            <Rss className="h-3 w-3" />
            {data?.enabled ? "Active" : "Disabled"}
          </span>
          <button
            type="button"
            role="switch"
            aria-checked={data?.enabled}
            disabled={update.isPending}
            onClick={handleToggle}
            className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 ${
              data?.enabled ? "bg-primary" : "bg-muted"
            }`}
          >
            <span
              className={`pointer-events-none block h-5 w-5 rounded-full bg-white shadow-lg ring-0 transition-transform ${
                data?.enabled ? "translate-x-5" : "translate-x-0"
              }`}
            />
          </button>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <label className={labelClass}>Companies per Daily Run</label>
          <input
            type="number"
            className={inputClass}
            min={1}
            max={500}
            value={form.daily_scrape_limit}
            onChange={(e) => {
              const v = parseInt(e.target.value, 10);
              if (!isNaN(v)) setForm({ ...form, daily_scrape_limit: v });
            }}
          />
          <p className="mt-1 text-xs text-muted-foreground">
            Max companies to scrape per daily LinkedIn batch (currently {data?.daily_scrape_limit ?? 50}).
          </p>
        </div>
        <div>
          <label className={labelClass}>Run Every N Days</label>
          <input
            type="number"
            className={inputClass}
            min={1}
            max={30}
            value={form.interval_days}
            onChange={(e) => {
              const v = parseInt(e.target.value, 10);
              if (!isNaN(v)) setForm({ ...form, interval_days: v });
            }}
          />
          <p className="mt-1 text-xs text-muted-foreground">
            How often the batch scrape runs (1 = daily, 7 = weekly).
          </p>
        </div>
        <div>
          <label className={labelClass}>Scrape Last N Days of Posts</label>
          <input
            type="number"
            className={inputClass}
            min={1}
            max={90}
            value={form.days_back}
            onChange={(e) => {
              const v = parseInt(e.target.value, 10);
              if (!isNaN(v)) setForm({ ...form, days_back: v });
            }}
          />
          <p className="mt-1 text-xs text-muted-foreground">
            How many days of LinkedIn posts to include per scrape.
          </p>
        </div>
      </div>

      {data?.last_batch_run && (
        <div className="mt-4 flex items-center gap-2 rounded-lg border border-border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
          <Clock className="h-3 w-3" />
          Last batch run:{" "}
          {new Date(data.last_batch_run).toLocaleString()}
        </div>
      )}

      <div className="mt-5 flex items-center gap-3">
        <button
          className={btnPrimary}
          onClick={handleSave}
          disabled={update.isPending}
        >
          {update.isPending && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
          Save LinkedIn Settings
        </button>
        {saved && (
          <span className="flex items-center gap-1 text-sm text-green-600">
            <Check className="h-3.5 w-3.5" /> Saved
          </span>
        )}
        {update.isError && (
          <span className="text-sm text-destructive">
            Failed to save — check your permissions.
          </span>
        )}
      </div>
    </div>
  );
}

// ── Status Badge ───────────────────────────────────────────────────

function StatusBadge({
  configured,
  label,
}: {
  configured: boolean;
  label: string;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${
        configured
          ? "bg-green-50 text-green-700 ring-green-200"
          : "bg-yellow-50 text-yellow-700 ring-yellow-200"
      }`}
    >
      {configured ? (
        <Check className="h-3 w-3" />
      ) : (
        <AlertTriangle className="h-3 w-3" />
      )}
      {label} {configured ? "configured" : "not set"}
    </span>
  );
}

// ── Usage Limits Card ──────────────────────────────────────────────

function UsageLimitsCard() {
  const { isAdmin } = useAuth();
  const { data, isLoading, error } = useUsageLimits({ enabled: isAdmin });
  const update = useUpdateUsageLimits();

  const [form, setForm] = useState({
    max_companies_per_discovery_run: 50,
    max_discovery_runs_per_day: 5,
    max_enrichments_per_day: 100,
    max_scrapes_per_day: 50,
    max_monitoring_companies_per_run: 200,
    daily_api_cost_limit: 25,
  });
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (data) {
      setForm({
        max_companies_per_discovery_run: data.max_companies_per_discovery_run,
        max_discovery_runs_per_day: data.max_discovery_runs_per_day,
        max_enrichments_per_day: data.max_enrichments_per_day,
        max_scrapes_per_day: data.max_scrapes_per_day,
        max_monitoring_companies_per_run: data.max_monitoring_companies_per_run,
        daily_api_cost_limit: data.daily_api_cost_limit,
      });
    }
  }, [data]);

  function handleSave() {
    setSaved(false);
    update.mutate(form, {
      onSuccess: () => {
        setSaved(true);
        setTimeout(() => setSaved(false), 3000);
      },
    });
  }

  if (!isAdmin) return null;

  if (isLoading) {
    return (
      <div className={cardClass}>
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading usage limits...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={cardClass}>
        <div className="flex items-center gap-2 text-destructive">
          <AlertTriangle className="h-4 w-4" />
          Failed to load usage limits
        </div>
      </div>
    );
  }

  const usageItems = [
    {
      label: "Discovery Runs",
      used: data?.discovery_runs_today ?? 0,
      limit: form.max_discovery_runs_per_day,
    },
    {
      label: "Enrichments",
      used: data?.enrichments_today ?? 0,
      limit: form.max_enrichments_per_day,
    },
    {
      label: "Scrapes",
      used: data?.scrapes_today ?? 0,
      limit: form.max_scrapes_per_day,
    },
  ];

  return (
    <div className={cardClass}>
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Usage Limits</h2>
          <p className="text-sm text-muted-foreground">
            Set daily caps for discovery, enrichment, and scraping to manage API costs.
          </p>
        </div>
        <span className="inline-flex items-center gap-1.5 rounded-md bg-blue-50 px-2.5 py-0.5 text-xs font-medium text-blue-700 ring-1 ring-inset ring-blue-200">
          <Shield className="h-3 w-3" />
          Cost Control
        </span>
      </div>

      {/* Today's usage bars */}
      <div className="mb-5 rounded-lg border border-border bg-muted/30 p-4">
        <p className="mb-3 text-xs font-medium uppercase tracking-wider text-muted-foreground">
          Today's Usage
        </p>
        <div className="space-y-3">
          {usageItems.map((item) => {
            const pct = item.limit > 0 ? Math.min((item.used / item.limit) * 100, 100) : 0;
            const isWarning = pct >= 80;
            const isAtLimit = pct >= 100;
            return (
              <div key={item.label}>
                <div className="mb-1 flex items-center justify-between text-sm">
                  <span>{item.label}</span>
                  <span className={isAtLimit ? "font-medium text-destructive" : isWarning ? "font-medium text-yellow-600" : "text-muted-foreground"}>
                    {item.used} / {item.limit}
                  </span>
                </div>
                <div className="h-1.5 w-full rounded-full bg-muted">
                  <div
                    className={`h-1.5 rounded-full transition-all ${
                      isAtLimit
                        ? "bg-destructive"
                        : isWarning
                          ? "bg-yellow-500"
                          : "bg-primary"
                    }`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
            );
          })}
          {data && data.daily_api_cost_limit > 0 && (
            <div>
              <div className="mb-1 flex items-center justify-between text-sm">
                <span>API Cost</span>
                <span className={data.api_cost_today >= data.daily_api_cost_limit ? "font-medium text-destructive" : "text-muted-foreground"}>
                  ${data.api_cost_today.toFixed(2)} / ${data.daily_api_cost_limit.toFixed(2)}
                </span>
              </div>
              <div className="h-1.5 w-full rounded-full bg-muted">
                <div
                  className={`h-1.5 rounded-full transition-all ${
                    data.api_cost_today >= data.daily_api_cost_limit
                      ? "bg-destructive"
                      : data.api_cost_today >= data.daily_api_cost_limit * 0.8
                        ? "bg-yellow-500"
                        : "bg-primary"
                  }`}
                  style={{ width: `${Math.min((data.api_cost_today / data.daily_api_cost_limit) * 100, 100)}%` }}
                />
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Limit settings */}
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className={labelClass}>Max Companies per Discovery Run</label>
          <input
            type="number"
            className={inputClass}
            min={1}
            max={1000}
            value={form.max_companies_per_discovery_run}
            onChange={(e) => {
              const v = parseInt(e.target.value, 10);
              if (!isNaN(v)) setForm({ ...form, max_companies_per_discovery_run: v });
            }}
          />
          <p className="mt-1 text-xs text-muted-foreground">
            Caps how many new companies are added per discovery run.
          </p>
        </div>
        <div>
          <label className={labelClass}>Max Discovery Runs per Day</label>
          <input
            type="number"
            className={inputClass}
            min={1}
            max={100}
            value={form.max_discovery_runs_per_day}
            onChange={(e) => {
              const v = parseInt(e.target.value, 10);
              if (!isNaN(v)) setForm({ ...form, max_discovery_runs_per_day: v });
            }}
          />
          <p className="mt-1 text-xs text-muted-foreground">
            Total manual + scheduled runs allowed per day.
          </p>
        </div>
        <div>
          <label className={labelClass}>Max Enrichments per Day</label>
          <input
            type="number"
            className={inputClass}
            min={1}
            max={10000}
            value={form.max_enrichments_per_day}
            onChange={(e) => {
              const v = parseInt(e.target.value, 10);
              if (!isNaN(v)) setForm({ ...form, max_enrichments_per_day: v });
            }}
          />
          <p className="mt-1 text-xs text-muted-foreground">
            Limits contact enrichment jobs (Hunter.io, Apollo, etc.).
          </p>
        </div>
        <div>
          <label className={labelClass}>Max Scrapes per Day</label>
          <input
            type="number"
            className={inputClass}
            min={1}
            max={10000}
            value={form.max_scrapes_per_day}
            onChange={(e) => {
              const v = parseInt(e.target.value, 10);
              if (!isNaN(v)) setForm({ ...form, max_scrapes_per_day: v });
            }}
          />
          <p className="mt-1 text-xs text-muted-foreground">
            Limits Firecrawl domain scrapes per day.
          </p>
        </div>
        <div>
          <label className={labelClass}>Max Monitoring Companies per Run</label>
          <input
            type="number"
            className={inputClass}
            min={1}
            max={10000}
            value={form.max_monitoring_companies_per_run}
            onChange={(e) => {
              const v = parseInt(e.target.value, 10);
              if (!isNaN(v)) setForm({ ...form, max_monitoring_companies_per_run: v });
            }}
          />
          <p className="mt-1 text-xs text-muted-foreground">
            Caps companies monitored per scheduled batch (prevents runaway Firecrawl costs).
          </p>
        </div>
        <div className="sm:col-span-2">
          <label className={labelClass}>Daily API Cost Limit (EUR)</label>
          <input
            type="number"
            className={inputClass}
            min={0}
            step={0.01}
            value={form.daily_api_cost_limit}
            onChange={(e) => {
              const v = parseFloat(e.target.value);
              if (!isNaN(v)) setForm({ ...form, daily_api_cost_limit: v });
            }}
          />
          <p className="mt-1 text-xs text-muted-foreground">
            Set to 0 for unlimited. Tracks estimated costs across all API providers.
          </p>
        </div>
      </div>

      <div className="mt-5 flex items-center gap-3">
        <button
          className={btnPrimary}
          onClick={handleSave}
          disabled={update.isPending}
        >
          {update.isPending && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
          Save Usage Limits
        </button>
        {saved && (
          <span className="flex items-center gap-1 text-sm text-green-600">
            <Check className="h-3.5 w-3.5" /> Saved
          </span>
        )}
        {update.isError && (
          <span className="text-sm text-destructive">
            Failed to save — check your permissions.
          </span>
        )}
      </div>
    </div>
  );
}

// ── Page ───────────────────────────────────────────────────────────

export default function Settings() {
  return (
    <div>
      <h1 className="text-2xl tracking-tight">Settings</h1>
      <p className="mt-1 text-sm text-muted-foreground" style={{ fontFamily: '"DM Sans", system-ui, sans-serif' }}>
        Manage integrations and application preferences.
      </p>

      <div className="mt-6 space-y-6">
        <JobScheduleCard />
        <UsageLimitsCard />
        <LinkedInCard />
        <APIKeysCard />
        <CRMCard />
        <SlackCard />
      </div>
    </div>
  );
}
