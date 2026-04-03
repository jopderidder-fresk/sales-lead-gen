import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "./api";

import type {
  APIKeysSettingsResponse,
  APIKeysSettingsUpdate,
  ClickUpSettingsResponse,
  ClickUpSettingsUpdate,
  CRMSettingsResponse,
  CRMSettingsUpdate,
  JobInfo,
  JobsResponse,
  JobToggle,
  LinkedInSettingsResponse,
  LinkedInSettingsUpdate,
  SlackSettingsResponse,
  SlackSettingsUpdate,
  SlackTestResponse,
  UsageLimitsResponse,
  UsageLimitsUpdate,
} from "@/types/api";

// ── Query keys ─────────────────────────────────────────────────────

const keys = {
  apiKeys: ["settings", "api-keys"] as const,
  clickup: ["settings", "clickup"] as const,
  crm: ["settings", "crm"] as const,
  jobs: ["settings", "jobs"] as const,
  linkedin: ["settings", "linkedin"] as const,
  slack: ["settings", "slack"] as const,
  usageLimits: ["settings", "usage-limits"] as const,
};

// ── API Keys ──────────────────────────────────────────────────────

export function useAPIKeysSettings() {
  return useQuery({
    queryKey: keys.apiKeys,
    queryFn: async () => {
      const { data } = await api.get<APIKeysSettingsResponse>(
        "/api/v1/settings/api-keys",
      );
      return data;
    },
  });
}

export function useUpdateAPIKeysSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: APIKeysSettingsUpdate) => {
      const { data } = await api.put<APIKeysSettingsResponse>(
        "/api/v1/settings/api-keys",
        body,
      );
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.apiKeys }),
  });
}

// ── ClickUp ────────────────────────────────────────────────────────

export function useClickUpSettings() {
  return useQuery({
    queryKey: keys.clickup,
    queryFn: async () => {
      const { data } = await api.get<ClickUpSettingsResponse>(
        "/api/v1/settings/clickup",
      );
      return data;
    },
  });
}

export function useUpdateClickUpSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: ClickUpSettingsUpdate) => {
      const { data } = await api.put<ClickUpSettingsResponse>(
        "/api/v1/settings/clickup",
        body,
      );
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.clickup }),
  });
}

// ── CRM ───────────────────────────────────────────────────────

export function useCRMSettings() {
  return useQuery({
    queryKey: keys.crm,
    queryFn: async () => {
      const { data } = await api.get<CRMSettingsResponse>(
        "/api/v1/settings/crm",
      );
      return data;
    },
  });
}

export function useUpdateCRMSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: CRMSettingsUpdate) => {
      const { data } = await api.put<CRMSettingsResponse>(
        "/api/v1/settings/crm",
        body,
      );
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.crm });
      qc.invalidateQueries({ queryKey: keys.clickup });
    },
  });
}

// ── LinkedIn ──────────────────────────────────────────────────────

export function useLinkedInSettings() {
  return useQuery({
    queryKey: keys.linkedin,
    queryFn: async () => {
      const { data } = await api.get<LinkedInSettingsResponse>(
        "/api/v1/settings/linkedin",
      );
      return data;
    },
  });
}

export function useUpdateLinkedInSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: LinkedInSettingsUpdate) => {
      const { data } = await api.put<LinkedInSettingsResponse>(
        "/api/v1/settings/linkedin",
        body,
      );
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.linkedin });
      qc.invalidateQueries({ queryKey: keys.jobs });
    },
  });
}

// ── Slack ──────────────────────────────────────────────────────────

export function useSlackSettings() {
  return useQuery({
    queryKey: keys.slack,
    queryFn: async () => {
      const { data } = await api.get<SlackSettingsResponse>(
        "/api/v1/settings/slack",
      );
      return data;
    },
  });
}

export function useUpdateSlackSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: SlackSettingsUpdate) => {
      const { data } = await api.put<SlackSettingsResponse>(
        "/api/v1/settings/slack",
        body,
      );
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.slack }),
  });
}

export function useTestSlackNotification() {
  return useMutation({
    mutationFn: async () => {
      const { data } = await api.post<SlackTestResponse>("/api/v1/slack/test");
      return data;
    },
  });
}

// ── Usage Limits ──────────────────────────────────────────────────

export function useUsageLimits({ enabled = true }: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: keys.usageLimits,
    queryFn: async () => {
      const { data } = await api.get<UsageLimitsResponse>(
        "/api/v1/settings/usage-limits",
      );
      return data;
    },
    enabled,
  });
}

export function useUpdateUsageLimits() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: UsageLimitsUpdate) => {
      const { data } = await api.put<UsageLimitsResponse>(
        "/api/v1/settings/usage-limits",
        body,
      );
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.usageLimits }),
  });
}

// ── Jobs ──────────────────────────────────────────────────────────

export function useJobs() {
  return useQuery({
    queryKey: keys.jobs,
    queryFn: async () => {
      const { data } = await api.get<JobsResponse>("/api/v1/settings/jobs");
      return data;
    },
  });
}

export function useToggleJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      jobName,
      enabled,
    }: {
      jobName: string;
      enabled: boolean;
    }) => {
      const { data } = await api.put<JobInfo>(
        `/api/v1/settings/jobs/${jobName}`,
        { enabled } as JobToggle,
      );
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.jobs }),
  });
}
