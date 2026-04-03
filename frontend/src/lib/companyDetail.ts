import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "./api";
import type {
  CRMPushResponse,
  CRMTaskResponse,
  CompanyDetailResponse,
  ContactResponse,
  EnrichmentJobResponse,
  PaginatedResponse,
  PaginationParams,
  ScrapeJobResponse,
  SignalResponse,
  SignalType,
  ScrapeJobStatus,
} from "@/types/api";

// ── Query keys ──────────────────────────────────────────────────────

const keys = {
  detail: (id: number) => ["companies", id] as const,
  contacts: (id: number, params: PaginationParams) =>
    ["companies", id, "contacts", params] as const,
  signals: (id: number, params: PaginationParams & { signal_type?: SignalType[] }) =>
    ["companies", id, "signals", params] as const,
  scrapeJobs: (id: number, params: PaginationParams & { status?: ScrapeJobStatus }) =>
    ["companies", id, "scrape-jobs", params] as const,
  enrichmentJobs: (id: number) => ["companies", id, "enrichment-jobs"] as const,
  crmTask: (id: number) => ["companies", id, "crm-task"] as const,
};

// ── Hooks ───────────────────────────────────────────────────────────

export function useCompanyDetail(id: number) {
  return useQuery({
    queryKey: keys.detail(id),
    queryFn: async () => {
      const { data } = await api.get<CompanyDetailResponse>(`/api/v1/companies/${id}`);
      return data;
    },
    enabled: !!id,
  });
}

export function useCompanyContacts(id: number, params: PaginationParams = {}) {
  return useQuery({
    queryKey: keys.contacts(id, params),
    queryFn: async () => {
      const query: Record<string, string> = {};
      if (params.offset != null) query.offset = String(params.offset);
      if (params.limit != null) query.limit = String(params.limit);
      const { data } = await api.get<PaginatedResponse<ContactResponse>>(
        `/api/v1/companies/${id}/contacts`,
        { params: query },
      );
      return data;
    },
    enabled: !!id,
  });
}

export function useCompanySignals(
  id: number,
  params: PaginationParams & { signal_type?: SignalType[] } = {},
) {
  return useQuery({
    queryKey: keys.signals(id, params),
    queryFn: async () => {
      const sp = new URLSearchParams();
      if (params.offset != null) sp.set("offset", String(params.offset));
      if (params.limit != null) sp.set("limit", String(params.limit));
      for (const t of params.signal_type ?? []) sp.append("signal_type", t);
      const { data } = await api.get<PaginatedResponse<SignalResponse>>(
        `/api/v1/companies/${id}/signals`,
        { params: sp },
      );
      return data;
    },
    enabled: !!id,
  });
}

export function useCompanyScrapeJobs(
  id: number,
  params: PaginationParams & { status?: ScrapeJobStatus } = {},
) {
  return useQuery({
    queryKey: keys.scrapeJobs(id, params),
    queryFn: async () => {
      const query: Record<string, string> = {};
      if (params.offset != null) query.offset = String(params.offset);
      if (params.limit != null) query.limit = String(params.limit);
      if (params.status) query.status = params.status;
      const { data } = await api.get<PaginatedResponse<ScrapeJobResponse>>(
        `/api/v1/companies/${id}/scrape-jobs`,
        { params: query },
      );
      return data;
    },
    enabled: !!id,
    // Poll every 3 seconds so active jobs update in real time
    refetchInterval: (query) => {
      const items = query.state.data?.items ?? [];
      const hasActive = items.some((j) => j.status === "pending" || j.status === "running");
      return hasActive ? 3000 : false;
    },
  });
}

export function useCompanyEnrichmentJobs(id: number) {
  return useQuery({
    queryKey: keys.enrichmentJobs(id),
    queryFn: async () => {
      const { data } = await api.get<PaginatedResponse<EnrichmentJobResponse>>(
        `/api/v1/companies/${id}/enrichment-jobs`,
        { params: { limit: 10 } },
      );
      return data;
    },
    enabled: !!id,
    // Poll every 3 seconds so active jobs update in real time
    refetchInterval: (query) => {
      const items = query.state.data?.items ?? [];
      const hasActive = items.some((j) => j.status === "pending" || j.status === "running");
      return hasActive ? 3000 : false;
    },
  });
}

export function useCRMStatusSync(companyId: number, hasCRMIntegration: boolean) {
  return useQuery({
    queryKey: keys.crmTask(companyId),
    queryFn: async () => {
      const { data } = await api.get<CRMTaskResponse>(
        `/api/v1/companies/${companyId}/crm/task`,
      );
      return data;
    },
    enabled: !!companyId && hasCRMIntegration,
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });
}

// ── Mutations ────────────────────────────────────────────────────────

interface TriggerResponse {
  task_id: string;
  company_id: number;
  message: string;
}

export function useTriggerEnrichment(companyId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data } = await api.post<TriggerResponse>(
        `/api/v1/companies/${companyId}/enrich`,
      );
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.detail(companyId) });
      qc.invalidateQueries({ queryKey: ["companies", companyId, "contacts"] });
      qc.invalidateQueries({ queryKey: keys.enrichmentJobs(companyId) });
    },
  });
}

export function useTriggerScrape(companyId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data } = await api.post<TriggerResponse>(
        `/api/v1/companies/${companyId}/scrape`,
      );
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.detail(companyId) });
      qc.invalidateQueries({ queryKey: ["companies", companyId, "scrape-jobs"] });
    },
  });
}

export function useTriggerContacts(companyId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data } = await api.post<TriggerResponse>(
        `/api/v1/companies/${companyId}/contacts`,
      );
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.detail(companyId) });
      qc.invalidateQueries({ queryKey: ["companies", companyId, "contacts"] });
      qc.invalidateQueries({ queryKey: keys.enrichmentJobs(companyId) });
    },
  });
}

export function useTriggerPipeline(companyId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data } = await api.post<TriggerResponse>(
        `/api/v1/companies/${companyId}/pipeline`,
      );
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.detail(companyId) });
      qc.invalidateQueries({ queryKey: ["companies", companyId, "scrape-jobs"] });
      qc.invalidateQueries({ queryKey: ["companies", companyId, "contacts"] });
      qc.invalidateQueries({ queryKey: keys.enrichmentJobs(companyId) });
    },
  });
}

export function useTriggerLinkedInScrape(companyId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data } = await api.post<TriggerResponse>(
        `/api/v1/companies/${companyId}/linkedin-scrape`,
      );
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.detail(companyId) });
      qc.invalidateQueries({ queryKey: ["companies", companyId, "signals"] });
    },
  });
}

export function usePushToCRM(companyId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data } = await api.post<CRMPushResponse>(
        `/api/v1/companies/${companyId}/crm/push`,
      );
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.detail(companyId) });
      qc.invalidateQueries({ queryKey: keys.crmTask(companyId) });
      qc.invalidateQueries({ queryKey: ["companies"] });
    },
  });
}
