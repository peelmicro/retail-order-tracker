import { useMutation, useQueryClient } from "@tanstack/vue-query";

import { apiFetch } from "@/lib/api";
import type { AnalyseByOrderResponse } from "@/types/api";

import { ordersQueryKeys } from "./orders";

/** Trigger the Analyst Agent on a persisted order, persist the suggestion,
 * and refresh any cached order list/detail so the new suggestion appears
 * everywhere it's displayed. */
export function useRunAnalystOnOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (orderId: string) =>
      apiFetch<AnalyseByOrderResponse>(`/api/agents/analyst/run/by-order/${orderId}`, {
        method: "POST",
      }),
    onSuccess: (result) => {
      queryClient.invalidateQueries({
        queryKey: ordersQueryKeys.detail(result.orderId),
      });
      queryClient.invalidateQueries({ queryKey: ordersQueryKeys.list() });
    },
  });
}
