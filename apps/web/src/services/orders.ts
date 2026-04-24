import { useQuery } from "@tanstack/vue-query";
import { computed, type MaybeRefOrGetter, toValue } from "vue";

import { apiFetch } from "@/lib/api";
import type { OrderDetailResponse, OrderListResponse, OrderStatus } from "@/types/api";

export interface OrdersListParams {
  status?: OrderStatus | "all" | null;
  retailerCode?: string | null;
  supplierCode?: string | null;
  page?: number;
  pageSize?: number;
}

function buildQuery(params: OrdersListParams): string {
  const search = new URLSearchParams();
  if (params.status && params.status !== "all") search.set("status", params.status);
  if (params.retailerCode) search.set("retailer_code", params.retailerCode);
  if (params.supplierCode) search.set("supplier_code", params.supplierCode);
  if (params.page !== undefined) search.set("page", String(params.page));
  if (params.pageSize !== undefined) search.set("page_size", String(params.pageSize));
  const s = search.toString();
  return s ? `?${s}` : "";
}

export function useOrdersList(params: MaybeRefOrGetter<OrdersListParams>) {
  const queryKey = computed(() => ["orders", "list", toValue(params)]);
  return useQuery({
    queryKey,
    queryFn: () => apiFetch<OrderListResponse>(`/api/orders${buildQuery(toValue(params))}`),
    placeholderData: (previousData) => previousData,
  });
}

export function useOrderDetail(id: MaybeRefOrGetter<string>) {
  const queryKey = computed(() => ["orders", "detail", toValue(id)]);
  return useQuery({
    queryKey,
    queryFn: () => apiFetch<OrderDetailResponse>(`/api/orders/${toValue(id)}`),
  });
}

export const ordersQueryKeys = {
  detail: (id: string) => ["orders", "detail", id] as const,
  list: () => ["orders", "list"] as const,
};
