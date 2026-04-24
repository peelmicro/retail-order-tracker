<script setup lang="ts">
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const router = useRouter();
const route = useRoute();

const username = ref("admin");
const password = ref("admin123");
const error = ref<string | null>(null);
const submitting = ref(false);

async function handleSubmit() {
  error.value = null;
  submitting.value = true;
  try {
    await auth.login(username.value, password.value);
    const next = typeof route.query.next === "string" ? route.query.next : "/";
    await router.replace(next);
  } catch (err) {
    error.value =
      err instanceof ApiError
        ? err.message
        : err instanceof Error
          ? err.message
          : "Unknown error";
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <main class="flex min-h-screen items-center justify-center bg-muted/30 p-6">
    <Card class="w-full max-w-sm">
      <CardHeader class="space-y-1 text-center">
        <CardTitle class="text-2xl">Retail Order Tracker</CardTitle>
        <CardDescription>Sign in to review orders</CardDescription>
      </CardHeader>

      <CardContent>
        <form class="space-y-4" @submit.prevent="handleSubmit">
          <div class="space-y-2">
            <Label for="username">Username</Label>
            <Input
              id="username"
              v-model="username"
              type="text"
              autocomplete="username"
              :disabled="submitting"
            />
          </div>
          <div class="space-y-2">
            <Label for="password">Password</Label>
            <Input
              id="password"
              v-model="password"
              type="password"
              autocomplete="current-password"
              :disabled="submitting"
            />
          </div>

          <Badge v-if="error" variant="destructive" class="w-full justify-center py-2">
            {{ error }}
          </Badge>

          <Button type="submit" class="w-full" :disabled="submitting">
            {{ submitting ? "Signing in…" : "Sign in" }}
          </Button>
        </form>

        <p class="mt-6 text-center text-xs text-muted-foreground">
          Demo credentials:
          <code class="rounded bg-muted px-1 py-0.5">admin</code> /
          <code class="rounded bg-muted px-1 py-0.5">admin123</code>
        </p>
      </CardContent>
    </Card>
  </main>
</template>
