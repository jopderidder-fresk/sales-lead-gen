import { useInfiniteQuery } from "@tanstack/react-query";
import api from "./api";
import type { PaginatedResponse, SignalFeedParams, SignalWithCompany } from "@/types/api";

const LIMIT = 25;

export type { SignalWithCompany, SignalFeedParams };

// ── Query keys ─────────────────────────────────────────────────────

const keys = {
  feed: (params: SignalFeedParams) => ["signals", "feed", params] as const,
};

// ── Hooks ──────────────────────────────────────────────────────────

export function useSignalsFeed(
  params: SignalFeedParams,
  options: { refetchInterval?: number | false } = {},
) {
  return useInfiniteQuery({
    queryKey: keys.feed(params),
    queryFn: async ({ pageParam }) => {
      // Build URL manually to handle repeated query params (signal_type, action_taken)
      const sp = new URLSearchParams();
      for (const t of params.signal_type ?? []) sp.append("signal_type", t);
      for (const a of params.action_taken ?? []) sp.append("action_taken", a);
      if (params.min_score != null) sp.set("min_score", String(params.min_score));
      if (params.date_from) sp.set("date_from", params.date_from);
      if (params.date_to) sp.set("date_to", params.date_to);
      if (params.company_search) sp.set("company_search", params.company_search);
      sp.set("offset", String(pageParam));
      sp.set("limit", String(LIMIT));

      const qs = sp.toString();
      const { data } = await api.get<PaginatedResponse<SignalWithCompany>>(
        `/api/v1/signals${qs ? `?${qs}` : ""}`,
      );
      return data;
    },
    initialPageParam: 0,
    getNextPageParam: (lastPage) => {
      const next = lastPage.offset + lastPage.limit;
      return next < lastPage.total ? next : undefined;
    },
    ...options,
  });
}
