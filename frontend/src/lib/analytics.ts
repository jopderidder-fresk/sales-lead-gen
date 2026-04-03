import { useQuery } from "@tanstack/react-query";
import api from "./api";

import type {
  APICostsResponse,
  ConversionFunnelResponse,
  EnrichmentRatesResponse,
  LeadsOverTimeResponse,
  SignalsByTypeResponse,
} from "@/types/api";

const keys = {
  all: ["analytics"] as const,
  leadsOverTime: (timeRange: string) => [...keys.all, "leads-over-time", timeRange] as const,
  signalsByType: (timeRange: string) => [...keys.all, "signals-by-type", timeRange] as const,
  apiCosts: (timeRange: string) => [...keys.all, "api-costs", timeRange] as const,
  conversionFunnel: () => [...keys.all, "conversion-funnel"] as const,
  enrichmentRates: () => [...keys.all, "enrichment-rates"] as const,
};

export function useLeadsOverTime(timeRange: string) {
  return useQuery({
    queryKey: keys.leadsOverTime(timeRange),
    queryFn: async () => {
      const { data } = await api.get<LeadsOverTimeResponse>(
        "/api/v1/analytics/leads-over-time",
        { params: { range: timeRange } },
      );
      return data;
    },
  });
}

export function useSignalsByType(timeRange: string) {
  return useQuery({
    queryKey: keys.signalsByType(timeRange),
    queryFn: async () => {
      const { data } = await api.get<SignalsByTypeResponse>(
        "/api/v1/analytics/signals-by-type",
        { params: { range: timeRange } },
      );
      return data;
    },
  });
}

export function useAPICosts(timeRange: string) {
  return useQuery({
    queryKey: keys.apiCosts(timeRange),
    queryFn: async () => {
      const { data } = await api.get<APICostsResponse>(
        "/api/v1/analytics/api-costs",
        { params: { range: timeRange } },
      );
      return data;
    },
  });
}

export function useConversionFunnel() {
  return useQuery({
    queryKey: keys.conversionFunnel(),
    queryFn: async () => {
      const { data } = await api.get<ConversionFunnelResponse>(
        "/api/v1/analytics/conversion-funnel",
      );
      return data;
    },
  });
}

export function useEnrichmentRates() {
  return useQuery({
    queryKey: keys.enrichmentRates(),
    queryFn: async () => {
      const { data } = await api.get<EnrichmentRatesResponse>(
        "/api/v1/analytics/enrichment-rates",
      );
      return data;
    },
  });
}
