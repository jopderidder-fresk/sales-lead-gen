import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "./api";

import type {
  DiscoveryJobDetailResponse,
  DiscoveryJobResponse,
  DiscoveryJobStatus,
  DiscoveryScheduleResponse,
  DiscoveryScheduleUpdate,
  DiscoveryTriggerResponse,
  PaginatedResponse,
} from "@/types/api";

export type { DiscoveryJobResponse, DiscoveryJobDetailResponse, DiscoveryJobStatus };

interface DiscoveryJobListParams {
  offset?: number;
  limit?: number;
  status?: DiscoveryJobStatus | null;
}

const keys = {
  all: ["discovery"] as const,
  jobs: (params: DiscoveryJobListParams) => ["discovery", "jobs", params] as const,
  job: (id: number) => ["discovery", "jobs", id] as const,
  schedule: ["discovery", "schedule"] as const,
};

export function useDiscoveryJobs(params: DiscoveryJobListParams) {
  return useQuery({
    queryKey: keys.jobs(params),
    queryFn: async () => {
      const query: Record<string, string> = {};
      if (params.offset != null) query.offset = String(params.offset);
      if (params.limit != null) query.limit = String(params.limit);
      if (params.status) query.status = params.status;

      const { data } = await api.get<PaginatedResponse<DiscoveryJobResponse>>(
        "/api/v1/discovery/jobs",
        { params: query },
      );
      return data;
    },
    refetchInterval: (query) => {
      const items = query.state.data?.items;
      if (items?.some((j: DiscoveryJobResponse) => j.status === "running" || j.status === "pending")) {
        return 5000;
      }
      return false;
    },
  });
}

export function useDiscoveryJob(id: number | null) {
  return useQuery({
    queryKey: keys.job(id!),
    queryFn: async () => {
      const { data } = await api.get<DiscoveryJobDetailResponse>(
        `/api/v1/discovery/jobs/${id}`,
      );
      return data;
    },
    enabled: id != null,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "running" || status === "pending") {
        return 5000;
      }
      return false;
    },
  });
}

export function useDiscoverySchedule() {
  return useQuery({
    queryKey: keys.schedule,
    queryFn: async () => {
      const { data } = await api.get<DiscoveryScheduleResponse>(
        "/api/v1/discovery/schedule",
      );
      return data;
    },
  });
}

export function useTriggerDiscovery() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data } = await api.post<DiscoveryTriggerResponse>(
        "/api/v1/discovery/run",
      );
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.all }),
  });
}

export function useUpdateDiscoverySchedule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: DiscoveryScheduleUpdate) => {
      const { data } = await api.put<DiscoveryScheduleResponse>(
        "/api/v1/discovery/schedule",
        body,
      );
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.schedule }),
  });
}
