import { useQuery } from "@tanstack/vue-query";

import { apiFetch } from "@/lib/api";
import type { DailyReport } from "@/types/api";

function fetchDailyReport(fromDate?: string, toDate?: string): Promise<DailyReport> {
  const params = new URLSearchParams();
  if (fromDate) params.set("from_date", fromDate);
  if (toDate) params.set("to_date", toDate);
  const query = params.toString();
  const path = query ? `/api/reports/daily?${query}` : "/api/reports/daily";
  return apiFetch<DailyReport>(path);
}

export function useDailyReport(fromDate?: string, toDate?: string) {
  return useQuery({
    queryKey: ["reports", "daily", fromDate, toDate],
    queryFn: () => fetchDailyReport(fromDate, toDate),
  });
}
