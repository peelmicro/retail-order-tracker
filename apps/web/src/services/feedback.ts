import { useMutation, useQueryClient } from "@tanstack/vue-query";

import { apiFetch } from "@/lib/api";
import type { FeedbackRequest, FeedbackSubmittedResponse } from "@/types/api";

import { ordersQueryKeys } from "./orders";

export function useSubmitFeedback() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (request: FeedbackRequest) =>
      apiFetch<FeedbackSubmittedResponse>("/api/feedback", {
        method: "POST",
        body: request as unknown as Record<string, unknown>,
      }),
    onSuccess: (result) => {
      // Refetch the specific order's detail + invalidate any list caches so
      // the status badge updates everywhere.
      queryClient.invalidateQueries({
        queryKey: ordersQueryKeys.detail(result.orderId),
      });
      queryClient.invalidateQueries({ queryKey: ordersQueryKeys.list() });
      queryClient.invalidateQueries({ queryKey: ["reports"] });
    },
  });
}
