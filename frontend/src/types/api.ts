// Shared API contract types — kept in sync with backend Pydantic schemas.
//
// Regenerate from OpenAPI spec:  pnpm generate-types
// Manual source of truth:        backend/app/schemas/ + backend/app/models/enums.py

// ── Enums ───────────────────────────────────────────────────────────

export type CompanyStatus =
  | "discovered"
  | "enriched"
  | "monitoring"
  | "qualified"
  | "pushed"
  | "archived";

export type EmailStatus = "verified" | "catch-all" | "unverified";

export type SignalType =
  | "hiring_surge"
  | "technology_adoption"
  | "funding_round"
  | "leadership_change"
  | "expansion"
  | "partnership"
  | "product_launch"
  | "no_signal";

export type SignalAction =
  | "notify_immediate"
  | "notify_digest"
  | "enrich_further"
  | "ignore";

export type ScrapeJobStatus = "pending" | "running" | "completed" | "failed";

export type EnrichmentJobStatus = "pending" | "running" | "completed" | "failed";

export type DiscoveryJobStatus = "pending" | "running" | "completed" | "failed";

export type UserRole = "admin" | "user" | "viewer";

// ── Pagination ──────────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  offset: number;
  limit: number;
}

export interface PaginationParams {
  offset?: number;
  limit?: number;
}

// ── Company ─────────────────────────────────────────────────────────

export interface ScoreBreakdown {
  icp_fit: number;
  signal_strength: number;
  contact_quality: number;
  recency: number;
}

export interface CompanyResponse {
  id: number;
  name: string;
  domain: string;
  industry: string | null;
  size: string | null;
  location: string | null;
  icp_score: number | null;
  lead_score: number | null;
  score_breakdown: ScoreBreakdown | null;
  score_updated_at: string | null;
  linkedin_url: string | null;
  kvk_number: string | null;
  phone: string | null;
  email: string | null;
  website_url: string | null;
  address: string | null;
  postal_code: string | null;
  city: string | null;
  province: string | null;
  country: string | null;
  founded_year: number | null;
  employee_count: number | null;
  organization_type: string | null;
  facebook_url: string | null;
  twitter_url: string | null;
  bedrijfsdata: BedrijfsdataData | null;
  status: CompanyStatus;
  clickup_task_id: string | null;
  clickup_task_url: string | null;
  clickup_status: string | null;
  crm_integration: CRMIntegrationResponse | null;
  created_at: string;
  updated_at: string;
}

export interface BedrijfsdataData {
  bedrijfsdata_id?: string;
  btwnummer?: string;
  sbi_codes?: string;
  branches_kvk?: string;
  organisatietype?: string;
  vestigingstype?: string;
  gemeente?: string;
  coordinaten?: string;
  cms?: string;
  website_analytics?: string;
  cdn?: string;
  advertentienetwerken?: string;
  caching_server?: string;
  webshop?: string;
  emailprovider?: string;
  apps?: string;
  bedrijfsprofiel?: string;
  youtube_link?: string;
  instagram_link?: string;
  pinterest_link?: string;
}

export interface LeadScoreResponse {
  company_id: number;
  lead_score: number;
  breakdown: ScoreBreakdown;
  scored_at: string;
}

export interface CompanyInfo {
  summary: string;
  products_services: string | null;
  target_market: string | null;
  technologies: string[];
  company_culture: string | null;
  headquarters: string | null;
  founded_year: number | null;
  employee_count_estimate: string | null;
}

export interface CompanyDetailResponse extends CompanyResponse {
  contacts_count: number;
  signals_count: number;
  latest_signal_at: string | null;
  company_info: CompanyInfo | null;
}

export interface CompanyCreate {
  name: string;
  domain: string;
  industry?: string | null;
  size?: string | null;
  location?: string | null;
  icp_score?: number | null;
  linkedin_url?: string | null;
  kvk_number?: string | null;
  phone?: string | null;
  email?: string | null;
  website_url?: string | null;
  address?: string | null;
  postal_code?: string | null;
  city?: string | null;
  province?: string | null;
  country?: string | null;
  founded_year?: number | null;
  employee_count?: number | null;
  organization_type?: string | null;
  facebook_url?: string | null;
  twitter_url?: string | null;
  status?: CompanyStatus;
  clickup_task_id?: string | null;
}

export interface CompanyUpdate {
  name?: string | null;
  domain?: string | null;
  industry?: string | null;
  size?: string | null;
  location?: string | null;
  icp_score?: number | null;
  linkedin_url?: string | null;
  kvk_number?: string | null;
  phone?: string | null;
  email?: string | null;
  website_url?: string | null;
  address?: string | null;
  postal_code?: string | null;
  city?: string | null;
  province?: string | null;
  country?: string | null;
  founded_year?: number | null;
  employee_count?: number | null;
  organization_type?: string | null;
  facebook_url?: string | null;
  twitter_url?: string | null;
  status?: CompanyStatus | null;
  clickup_task_id?: string | null;
}

export interface CompanyListParams {
  offset?: number;
  limit?: number;
  status?: CompanyStatus | null;
  industry?: string | null;
  min_score?: number | null;
  search?: string | null;
  added_after?: string | null;
  added_before?: string | null;
  sort?: string;
  order?: "asc" | "desc";
}

// ── ICP Profile ─────────────────────────────────────────────────────

export interface SizeFilter {
  min_employees?: number | null;
  max_employees?: number | null;
  min_revenue?: number | null;
  max_revenue?: number | null;
}

export interface GeoFilter {
  countries: string[];
  regions: string[];
  cities: string[];
}

export interface NegativeFilters {
  excluded_industries: string[];
  excluded_domains: string[];
}

export interface ICPProfileResponse {
  id: number;
  name: string;
  industry_filter: string[] | null;
  size_filter: SizeFilter | null;
  geo_filter: GeoFilter | null;
  tech_filter: string[] | null;
  negative_filters: NegativeFilters | null;
  is_active: boolean;
  created_at: string;
}

export interface ICPProfileCreate {
  name: string;
  industry_filter?: string[] | null;
  size_filter?: SizeFilter | null;
  geo_filter?: GeoFilter | null;
  tech_filter?: string[] | null;
  negative_filters?: NegativeFilters | null;
}

export type ICPProfileUpdate = Partial<ICPProfileCreate>;

// ── Auth ────────────────────────────────────────────────────────────

export interface LoginRequest {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface RefreshRequest {
  refresh_token: string;
}

export interface UserResponse {
  id: number;
  username: string;
  email: string;
  role: UserRole;
  created_at: string;
}

// ── Deduplication ───────────────────────────────────────────────────

export interface DuplicateCheckRequest {
  name: string;
  domain: string;
}

export interface SimilarCompanyMatch {
  company_id: number;
  name: string;
  domain: string;
  domain_match: boolean;
  name_similarity: number;
}

export interface SimilarCompaniesResponse {
  matches: SimilarCompanyMatch[];
}

export interface DuplicateGroupMember {
  company_id: number;
  name: string;
  domain: string;
  domain_match: boolean | null;
  name_similarity: number | null;
}

export interface DuplicateGroup {
  companies: DuplicateGroupMember[];
}

export interface DuplicateScanResponse {
  groups: DuplicateGroup[];
  total_groups: number;
}

export interface MergeRequest {
  primary_id: number;
  duplicate_id: number;
}

// ── Contact ─────────────────────────────────────────────────────────

export interface ContactResponse {
  id: number;
  company_id: number;
  name: string;
  title: string | null;
  email: string | null;
  phone: string | null;
  linkedin_url: string | null;
  email_status: EmailStatus | null;
  confidence_score: number | null;
  source: string | null;
  clickup_task_id: string | null;
  clickup_task_url: string | null;
  created_at: string;
}

export interface ContactWithCompanyResponse extends ContactResponse {
  company_name: string;
  company_domain: string;
}

export interface ContactListParams {
  offset?: number;
  limit?: number;
  search?: string | null;
  email_status?: EmailStatus | null;
  company_id?: number | null;
  sort?: string;
  order?: "asc" | "desc";
}

// ── Signal ──────────────────────────────────────────────────────────

export interface SignalResponse {
  id: number;
  company_id: number;
  signal_type: SignalType;
  source_url: string | null;
  /** HTML page title from crawl (if Firecrawl provided it). */
  source_title?: string | null;
  llm_summary: string | null;
  relevance_score: number | null;
  action_taken: SignalAction | null;
  created_at: string;
}

export interface SignalWithCompany extends SignalResponse {
  company_name: string;
  company_domain: string;
}

export interface SignalFeedParams {
  signal_type?: SignalType[];
  action_taken?: SignalAction[];
  min_score?: number | null;
  date_from?: string | null;
  date_to?: string | null;
  company_search?: string | null;
}

// ── Enrichment Job ──────────────────────────────────────────────────

export interface EnrichmentJobResponse {
  id: number;
  company_id: number;
  status: EnrichmentJobStatus;
  result_summary: string | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

// ── Scrape Job ──────────────────────────────────────────────────────

export interface ScrapeJobResponse {
  id: number;
  company_id: number;
  target_url: string;
  status: ScrapeJobStatus;
  pages_scraped: number | null;
  credits_used: number | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

// ── Dashboard ──────────────────────────────────────────────────────

export interface DashboardStats {
  total_companies: number;
  total_contacts: number;
  signals_last_7d: number;
  hot_leads: number;
  warm_leads: number;
}

export interface FunnelStage {
  stage: CompanyStatus;
  count: number;
}

export interface DashboardFunnel {
  stages: FunnelStage[];
}

export interface TimelinePoint {
  week_start: string;
  count: number;
}

export interface DashboardTimeline {
  points: TimelinePoint[];
}

export interface ConversionMetrics {
  discovery_to_enrichment: number | null;
  enrichment_to_qualified: number | null;
  qualified_to_pushed: number | null;
}

export interface DashboardRecentSignal {
  id: number;
  company_id: number;
  company_name: string;
  signal_type: SignalType;
  relevance_score: number | null;
  action_taken: SignalAction | null;
  created_at: string;
}

export interface DashboardResponse {
  stats: DashboardStats;
  funnel: DashboardFunnel;
  timeline: DashboardTimeline;
  conversions: ConversionMetrics;
  recent_signals: DashboardRecentSignal[];
}

// ── Analytics ────────────────────────────────────────────────────────

export interface LeadsDataPoint {
  date: string;
  count: number;
}

export interface LeadsOverTimeResponse {
  points: LeadsDataPoint[];
  total: number;
  range: string;
}

export interface SignalTypeCount {
  signal_type: SignalType;
  count: number;
}

export interface SignalsByTypeResponse {
  breakdown: SignalTypeCount[];
  total: number;
  range: string;
}

export interface ProviderCostPoint {
  date: string;
  provider: string;
  cost: number;
  credits: number;
}

export interface APICostsResponse {
  points: ProviderCostPoint[];
  total_cost: number;
  cost_per_lead: number | null;
  range: string;
}

export interface AnalyticsFunnelStage {
  stage: CompanyStatus;
  count: number;
  percentage: number;
}

export interface ConversionFunnelResponse {
  stages: AnalyticsFunnelStage[];
  total: number;
}

export interface ProviderEnrichmentRate {
  provider: string;
  attempts: number;
  successes: number;
  rate: number;
}

export interface EnrichmentRatesResponse {
  providers: ProviderEnrichmentRate[];
  overall_rate: number;
}

// ── Discovery Job ───────────────────────────────────────────────────

export interface DiscoveryJobResponse {
  id: number;
  status: DiscoveryJobStatus;
  trigger: string;
  started_at: string | null;
  completed_at: string | null;
  companies_found: number;
  companies_added: number;
  companies_skipped: number;
  error_message: string | null;
  duration_seconds: number | null;
  celery_task_id: string | null;
  created_at: string;
}

export interface DiscoveryJobDetailResponse extends DiscoveryJobResponse {
  results: Record<string, unknown> | null;
}

export interface DiscoveryTriggerResponse {
  task_id: string;
  job_id: number;
  message: string;
}

export interface DiscoveryScheduleResponse {
  task_name: string;
  schedule_expression: string;
  human_readable: string;
  enabled: boolean;
}

export interface DiscoveryScheduleUpdate {
  frequency: string;
}

// ── Settings ────────────────────────────────────────────────────────

export interface ClickUpTaskResponse {
  id: string;
  name: string;
  status: string | null;
  url: string | null;
}

// ── CRM Integration ─────────────────────────────────────────────────

export interface CRMIntegrationResponse {
  provider: string;
  external_id: string;
  external_url: string | null;
  external_status: string | null;
  synced_at: string | null;
}

export interface CRMTaskResponse {
  id: string;
  name: string;
  status: string | null;
  url: string | null;
  provider: string;
}

export interface CRMPushResponse {
  company_id: number;
  task_id: string | null;
  task_url: string | null;
  provider: string;
  message: string;
}

export interface ClickUpSettingsResponse {
  configured: boolean;
  workspace_id: string;
  space_id: string;
  folder_id: string;
  list_id: string;
}

export interface ClickUpSettingsUpdate {
  workspace_id?: string;
  space_id?: string;
  folder_id?: string;
  list_id?: string;
}

// ── CRM Settings ─────────────────────────────────────────────────

export interface ClickUpCRMSettings {
  api_key_set: boolean;
  api_key_preview: string | null;
  workspace_id: string;
  space_id: string;
  folder_id: string;
  list_id: string;
  domain_field_id: string;
  person_list_id: string;
  person_email_field_id: string;
  person_phone_field_id: string;
  person_linkedin_field_id: string;
  person_surname_field_id: string;
  person_lastname_field_id: string;
  person_role_field_id: string;
  contact_relationship_field_id: string;
  company_contact_field_id: string;
}

export interface CRMSettingsResponse {
  provider: string;
  configured: boolean;
  available_providers: string[];
  clickup: ClickUpCRMSettings | null;
}

export interface CRMSettingsUpdate {
  provider?: string;
  clickup_api_key?: string;
  clickup_workspace_id?: string;
  clickup_space_id?: string;
  clickup_folder_id?: string;
  clickup_list_id?: string;
  clickup_domain_field_id?: string;
  clickup_person_list_id?: string;
  clickup_person_email_field_id?: string;
  clickup_person_phone_field_id?: string;
  clickup_person_linkedin_field_id?: string;
  clickup_person_surname_field_id?: string;
  clickup_person_lastname_field_id?: string;
  clickup_person_role_field_id?: string;
  clickup_contact_relationship_field_id?: string;
  clickup_company_contact_field_id?: string;
}

export interface SlackSettingsResponse {
  configured: boolean;
  webhook_url_set: boolean;
  digest_webhook_url_set: boolean;
  digest_hour: number;
  weekly_day: number;
  webhook_url_preview: string | null;
  digest_webhook_url_preview: string | null;
}

export interface SlackSettingsUpdate {
  webhook_url?: string;
  digest_webhook_url?: string;
  digest_hour?: number;
  weekly_day?: number;
}

export interface SlackTestResponse {
  success: boolean;
  message: string;
}

// ── LinkedIn Settings ───────────────────────────────────────────

export interface LinkedInSettingsResponse {
  enabled: boolean;
  interval_days: number;
  days_back: number;
  last_batch_run: string | null;
}

export interface LinkedInSettingsUpdate {
  enabled?: boolean;
  interval_days?: number;
  days_back?: number;
}

export interface UsageLimitsResponse {
  max_companies_per_discovery_run: number;
  max_discovery_runs_per_day: number;
  max_enrichments_per_day: number;
  max_scrapes_per_day: number;
  max_monitoring_companies_per_run: number;
  daily_api_cost_limit: number;
  discovery_runs_today: number;
  enrichments_today: number;
  scrapes_today: number;
  api_cost_today: number;
}

export interface UsageLimitsUpdate {
  max_companies_per_discovery_run?: number;
  max_discovery_runs_per_day?: number;
  max_enrichments_per_day?: number;
  max_scrapes_per_day?: number;
  max_monitoring_companies_per_run?: number;
  daily_api_cost_limit?: number;
}

// ── Job Schedule Settings ────────────────────────────────────────

export interface JobInfo {
  name: string;
  enabled: boolean;
  schedule: string;
  description: string;
}

export interface JobsResponse {
  jobs: JobInfo[];
}

export interface JobToggle {
  enabled: boolean;
}

// ── API Keys Settings ────────────────────────────────────────────

export interface APIKeyStatus {
  key_set: boolean;
  preview: string | null;
}

export interface APIKeysSettingsResponse {
  llm_provider: string;
  anthropic: APIKeyStatus;
  openrouter: APIKeyStatus;
  openrouter_model: string;
  gemini: APIKeyStatus;
  firecrawl: APIKeyStatus;
  hunter_io: APIKeyStatus;
  apollo: APIKeyStatus;
  scrapin: APIKeyStatus;
  bedrijfsdata: APIKeyStatus;
  apify: APIKeyStatus;
}

export interface APIKeysSettingsUpdate {
  llm_provider?: string;
  anthropic_api_key?: string;
  openrouter_api_key?: string;
  openrouter_model?: string;
  gemini_api_key?: string;
  firecrawl_api_key?: string;
  hunter_io_api_key?: string;
  apollo_api_key?: string;
  scrapin_api_key?: string;
  bedrijfsdata_api_key?: string;
  apify_api_token?: string;
}

// ── Convenience aliases ─────────────────────────────────────────────
// These match the names used by existing frontend code for backwards
// compatibility.  New code should prefer the *Response suffix.

// ── Bulk Operations ─────────────────────────────────────────────────

export interface ImportRowError {
  row: number;
  error: string;
}

export interface BulkImportResponse {
  imported: number;
  skipped: number;
  errors: ImportRowError[];
}

export interface BulkDeleteResponse {
  archived: number;
}

// ── Convenience aliases ─────────────────────────────────────────────
// These match the names used by existing frontend code for backwards
// compatibility.  New code should prefer the *Response suffix.

export type Company = CompanyResponse;
export type ICPProfile = ICPProfileResponse;
