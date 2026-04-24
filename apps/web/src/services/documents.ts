import { useQuery } from "@tanstack/vue-query";
import { computed, type MaybeRefOrGetter, toValue } from "vue";

import { apiFetch } from "@/lib/api";
import type { DocumentResponse } from "@/types/api";

export function useDocument(id: MaybeRefOrGetter<string>) {
  const queryKey = computed(() => ["documents", "detail", toValue(id)]);
  return useQuery({
    queryKey,
    queryFn: () => apiFetch<DocumentResponse>(`/api/documents/${toValue(id)}`),
  });
}
