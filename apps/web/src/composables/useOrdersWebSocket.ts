import { useQueryClient } from "@tanstack/vue-query";
import { useWebSocket } from "@vueuse/core";
import { computed, watch } from "vue";
import { useRouter } from "vue-router";
import { toast } from "vue-sonner";

import { ordersQueryKeys } from "@/services/orders";
import { useAuthStore } from "@/stores/auth";
import type { OrderEvent } from "@/types/api";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
// http:// → ws://, https:// → wss://
const WS_BASE = API_URL.replace(/^http/, "ws") + "/ws/orders";

/** Single app-wide WebSocket connection. Call once from App.vue.
 *
 * - Opens automatically when the user is authenticated (reactive URL).
 * - Closes when they sign out.
 * - Auto-reconnects on transient drops.
 * - Parses incoming messages, fires toasts, invalidates TanStack Query caches.
 */
export function useOrdersWebSocket() {
  const auth = useAuthStore();
  const queryClient = useQueryClient();
  const router = useRouter();

  // An empty URL keeps useWebSocket() idle — exactly what we want when
  // the user signs out.
  const url = computed(() =>
    auth.token ? `${WS_BASE}?token=${encodeURIComponent(auth.token)}` : "",
  );

  const { status, data } = useWebSocket(url, {
    autoReconnect: {
      retries: Number.POSITIVE_INFINITY,
      delay: 2000,
    },
    immediate: true,
  });

  // Watching the `data` ref fires on every incoming frame — more reliable
  // than the `onMessage` option in current @vueuse/core builds.
  watch(data, (raw) => {
    if (!raw || typeof raw !== "string") return;
    let parsed: OrderEvent | null = null;
    try {
      parsed = JSON.parse(raw) as OrderEvent;
    } catch {
      return;
    }
    if (!parsed || typeof parsed !== "object" || !("eventType" in parsed)) return;
    dispatchEvent(parsed);
  });

  function dispatchEvent(event: OrderEvent) {
    if (event.eventType === "order.created") {
      toast.info(`New order · ${event.orderCode}`, {
        description: `${event.retailerName} → ${event.supplierName}`,
        action: {
          label: "View",
          onClick: () => router.push({ name: "order-detail", params: { id: event.orderId } }),
        },
      });
      queryClient.invalidateQueries({ queryKey: ordersQueryKeys.list() });
      queryClient.invalidateQueries({ queryKey: ["reports"] });
    } else if (event.eventType === "order.status_changed") {
      toast.info(`Order ${event.orderCode} → ${event.newStatus.replaceAll("_", " ")}`, {
        description: `Operator action: ${event.finalAction.replaceAll("_", " ")}`,
        action: {
          label: "View",
          onClick: () => router.push({ name: "order-detail", params: { id: event.orderId } }),
        },
      });
      queryClient.invalidateQueries({ queryKey: ordersQueryKeys.list() });
      queryClient.invalidateQueries({ queryKey: ordersQueryKeys.detail(event.orderId) });
      queryClient.invalidateQueries({ queryKey: ["reports"] });
    }
  }

  return {
    status,
    lastMessage: data,
  };
}
