import { useQuery } from "@tanstack/react-query";
import api from "./api";

import type { DashboardResponse } from "@/types/api";

const keys = {
  all: ["dashboard"] as const,
};

export function useDashboard() {
  return useQuery({
    queryKey: keys.all,
    queryFn: async () => {
      const { data } = await api.get<DashboardResponse>("/api/v1/dashboard");
      return data;
    },
    refetchInterval: 60_000,
  });
}
