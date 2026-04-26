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

  // useWebSocket() only skips connecting when the URL is undefined.
  // Returning "" makes Chrome silently fail but Firefox throws
  // `DOMException: An invalid or illegal string was specified` synchronously
  // from new WebSocket(""), crashing App.vue's setup. undefined keeps the
  // composable cleanly idle until the user signs in.
  const url = computed(() =>
    auth.token
      ? `${WS_BASE}?token=${encodeURIComponent(auth.token)}`
      : undefined,
  );

  const { status, data } = useWebSocket(url, {
    autoReconnect: {
      retries: Number.POSITIVE_INFINITY,
      delay: 2000,
    },
    immediate: true,
  });

  // The HTTP path fires `api:unauthorized` on a 401 from apiFetch, but a
  // WebSocket upgrade rejection (e.g. JWT expired → server returns 403)
  // doesn't go through apiFetch. Without the cleanup, useWebSocket retries
  // every 2 s forever with the now-stale token. Track consecutive CLOSED
  // transitions and treat 3 in a row as "the server doesn't like our
  // token" — fire api:unauthorized so the auth store logs us out and the
  // App.vue watcher pushes to /login. The threshold (≈ 6 s) is well above
  // a transient network blip and well below "user wandered off".
  let consecutiveCloses = 0;
  const FAILURE_THRESHOLD = 3;
  watch(status, (s) => {
    if (s === "OPEN") {
      consecutiveCloses = 0;
      return;
    }
    if (s === "CLOSED" && auth.token) {
      consecutiveCloses += 1;
      if (consecutiveCloses >= FAILURE_THRESHOLD) {
        consecutiveCloses = 0;
        window.dispatchEvent(new CustomEvent("api:unauthorized"));
      }
    }
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
