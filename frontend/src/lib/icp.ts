import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "./api";

export type {
  ICPProfile,
  ICPProfileCreate,
  ICPProfileUpdate,
  SizeFilter,
  GeoFilter,
  NegativeFilters,
} from "@/types/api";

import type {
  ICPProfile,
  ICPProfileCreate,
  ICPProfileUpdate,
} from "@/types/api";

// ── Query keys ─────────────────────────────────────────────────────

const keys = {
  all: ["icp-profiles"] as const,
  detail: (id: number) => ["icp-profiles", id] as const,
};

// ── Hooks ──────────────────────────────────────────────────────────

export function useICPProfiles() {
  return useQuery({
    queryKey: keys.all,
    queryFn: async () => {
      const { data } = await api.get<ICPProfile[]>("/api/v1/icp-profiles");
      return data;
    },
  });
}

export function useHasActiveICP() {
  const { data: profiles, isLoading } = useICPProfiles();
  const hasActiveICP = isLoading || (profiles?.some((p) => p.is_active) ?? false);
  return { hasActiveICP, isLoading };
}

export function useCreateProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: ICPProfileCreate) => {
      const { data } = await api.post<ICPProfile>(
        "/api/v1/icp-profiles",
        body,
      );
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.all }),
  });
}

export function useUpdateProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      ...body
    }: ICPProfileUpdate & { id: number }) => {
      const { data } = await api.put<ICPProfile>(
        `/api/v1/icp-profiles/${id}`,
        body,
      );
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.all }),
  });
}

export function useActivateProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      const { data } = await api.post<ICPProfile>(
        `/api/v1/icp-profiles/${id}/activate`,
      );
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.all }),
  });
}

export function useDeactivateProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      const { data } = await api.post<ICPProfile>(
        `/api/v1/icp-profiles/${id}/deactivate`,
      );
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.all }),
  });
}

export function useDeleteProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/api/v1/icp-profiles/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.all }),
  });
}
