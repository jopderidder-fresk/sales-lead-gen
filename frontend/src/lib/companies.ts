import { useMutation, useQuery, useQueryClient, keepPreviousData } from "@tanstack/react-query";
import api from "./api";

export type {
  Company,
  CompanyStatus,
  CompanyListParams,
  PaginatedResponse,
} from "@/types/api";

import type {
  BulkDeleteResponse,
  BulkImportResponse,
  Company,
  CompanyCreate,
  CompanyListParams,
  PaginatedResponse,
} from "@/types/api";

// ── Query keys ─────────────────────────────────────────────────────

const keys = {
  all: ["companies"] as const,
  list: (params: CompanyListParams) => ["companies", "list", params] as const,
};

// ── Hooks ──────────────────────────────────────────────────────────

export function useCompanies(params: CompanyListParams) {
  return useQuery({
    queryKey: keys.list(params),
    placeholderData: keepPreviousData,
    queryFn: async () => {
      const query: Record<string, string> = {};
      if (params.offset != null) query.offset = String(params.offset);
      if (params.limit != null) query.limit = String(params.limit);
      if (params.status) query.status = params.status;
      if (params.industry) query.industry = params.industry;
      if (params.min_score != null) query.min_score = String(params.min_score);
      if (params.monitor != null) query.monitor = String(params.monitor);
      if (params.search) query.search = params.search;
      if (params.added_after) query.added_after = params.added_after;
      if (params.added_before) query.added_before = params.added_before;
      if (params.sort) query.sort = params.sort;
      if (params.order) query.order = params.order;

      const { data } = await api.get<PaginatedResponse<Company>>(
        "/api/v1/companies",
        { params: query },
      );
      return data;
    },
  });
}

export function useUpdateCompany() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      ...body
    }: Partial<Company> & { id: number }) => {
      const { data } = await api.patch<Company>(
        `/api/v1/companies/${id}`,
        body,
      );
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.all }),
  });
}

export function useDeleteCompany() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/api/v1/companies/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.all }),
  });
}

export function useCreateCompany() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: CompanyCreate) => {
      const { data } = await api.post<Company>("/api/v1/companies", body);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.all }),
  });
}

export function useImportCompanies() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (file: File) => {
      const formData = new FormData();
      formData.append("file", file);
      const { data } = await api.post<BulkImportResponse>(
        "/api/v1/companies/import",
        formData,
      );
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.all }),
  });
}

export function useBulkDeleteCompanies() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (ids: number[]) => {
      const { data } = await api.post<BulkDeleteResponse>(
        "/api/v1/companies/bulk-delete",
        { ids },
      );
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.all }),
  });
}

export function useTriggerScrapeFromList() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (companyId: number) => {
      await api.post(`/api/v1/companies/${companyId}/scrape`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.all }),
  });
}

export function useTriggerPipelineFromList() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (companyId: number) => {
      await api.post(`/api/v1/companies/${companyId}/pipeline`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.all }),
  });
}
