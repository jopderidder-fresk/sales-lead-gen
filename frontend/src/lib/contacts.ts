import { useQuery } from "@tanstack/react-query";
import api from "./api";
import type {
  ContactListParams,
  ContactWithCompanyResponse,
  PaginatedResponse,
} from "@/types/api";

const keys = {
  all: ["contacts"] as const,
  list: (params: ContactListParams) => ["contacts", "list", params] as const,
};

export function useContacts(params: ContactListParams = {}) {
  return useQuery({
    queryKey: keys.list(params),
    queryFn: async () => {
      const query: Record<string, string> = {};
      if (params.offset != null) query.offset = String(params.offset);
      if (params.limit != null) query.limit = String(params.limit);
      if (params.search) query.search = params.search;
      if (params.email_status) query.email_status = params.email_status;
      if (params.company_id != null) query.company_id = String(params.company_id);
      if (params.sort) query.sort = params.sort;
      if (params.order) query.order = params.order;

      const { data } = await api.get<PaginatedResponse<ContactWithCompanyResponse>>(
        "/api/v1/contacts",
        { params: query },
      );
      return data;
    },
  });
}

export type { ContactWithCompanyResponse, ContactListParams };
