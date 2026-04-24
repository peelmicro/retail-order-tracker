<script setup lang="ts">
import { onMounted } from "vue";
import { RouterView, useRouter } from "vue-router";

import ConnectionBadge from "@/components/ConnectionBadge.vue";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Toaster } from "@/components/ui/sonner";
import { useOrdersWebSocket } from "@/composables/useOrdersWebSocket";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const router = useRouter();
const { status: wsStatus } = useOrdersWebSocket();

onMounted(async () => {
  // If a token was loaded from localStorage, fetch the user eagerly so the
  // header shows the username without a flicker.
  if (auth.isAuthenticated && auth.user === null) {
    try {
      await auth.fetchCurrentUser();
    } catch {
      // The 401 handler in the store already clears the token.
    }
  }
});

async function handleLogout() {
  auth.logout();
  await router.push({ name: "login" });
}
</script>

<template>
  <div class="min-h-screen bg-background text-foreground">
    <header
      v-if="auth.isAuthenticated"
      class="sticky top-0 z-10 border-b bg-background/95 backdrop-blur"
    >
      <div class="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
        <div class="flex items-center gap-6">
          <RouterLink :to="{ name: 'home' }" class="text-sm font-semibold">
            Retail Order Tracker
          </RouterLink>
          <nav class="flex items-center gap-4 text-sm">
            <RouterLink
              :to="{ name: 'home' }"
              class="text-muted-foreground hover:text-foreground"
              active-class="text-foreground font-medium"
              :class="{ 'text-foreground font-medium': $route.name === 'home' }"
            >
              Dashboard
            </RouterLink>
            <RouterLink
              :to="{ name: 'orders' }"
              class="text-muted-foreground hover:text-foreground"
              :class="{ 'text-foreground font-medium': $route.name === 'orders' || $route.name === 'order-detail' }"
            >
              Review Queue
            </RouterLink>
          </nav>
        </div>
        <div class="flex items-center gap-3">
          <ConnectionBadge :status="wsStatus" />
          <template v-if="auth.user">
            <span class="text-sm text-muted-foreground">{{ auth.user.username }}</span>
            <Badge
              :variant="auth.user.role === 'admin' ? 'default' : 'secondary'"
              class="capitalize"
            >
              {{ auth.user.role }}
            </Badge>
          </template>
          <Button variant="outline" size="sm" @click="handleLogout">Sign out</Button>
        </div>
      </div>
    </header>

    <RouterView />
    <Toaster position="top-right" rich-colors />
  </div>
</template>
