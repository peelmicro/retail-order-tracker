<script setup lang="ts">
import { AlertCircle, ChevronLeft, ChevronRight } from "lucide-vue-next";
import { computed, ref, watch } from "vue";
import { useRouter } from "vue-router";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { formatCount, formatDate, formatMinorUnits } from "@/lib/format";
import { useOrdersList } from "@/services/orders";
import type { AgentAction, OrderStatus } from "@/types/api";

type StatusFilter = OrderStatus | "all";

const router = useRouter();

const statusFilter = ref<StatusFilter>("pending_review");
const page = ref(1);
const pageSize = ref(25);

// Reset to page 1 when the filter changes
watch(statusFilter, () => {
  page.value = 1;
});

const params = computed(() => ({
  status: statusFilter.value,
  page: page.value,
  pageSize: pageSize.value,
}));

const { data, isLoading, isError, error, isFetching } = useOrdersList(params);

const items = computed(() => data.value?.items ?? []);
const totalPages = computed(() => data.value?.totalPages ?? 0);
const total = computed(() => data.value?.total ?? 0);

const statusVariant = (
  status: OrderStatus,
): "default" | "secondary" | "destructive" | "outline" => {
  switch (status) {
    case "approved":
      return "default";
    case "pending_review":
      return "secondary";
    case "escalated":
    case "rejected_by_operator":
      return "destructive";
    default:
      return "outline";
  }
};

const actionVariant = (
  action: AgentAction,
): "default" | "secondary" | "destructive" | "outline" => {
  switch (action) {
    case "approve":
      return "default";
    case "request_clarification":
      return "secondary";
    case "escalate":
      return "destructive";
    default:
      return "outline";
  }
};

const prettyValue = (v: string) => v.replaceAll("_", " ");

function openOrder(id: string) {
  router.push({ name: "order-detail", params: { id } });
}

function prevPage() {
  if (page.value > 1) page.value -= 1;
}

function nextPage() {
  if (page.value < totalPages.value) page.value += 1;
}
</script>

<template>
  <main class="mx-auto max-w-6xl p-6">
    <div class="mb-4">
      <h1 class="text-3xl font-semibold">Review Queue</h1>
      <p class="mt-1 text-sm text-muted-foreground">
        Orders awaiting an operator decision on the Analyst Agent's suggestion.
      </p>
    </div>

    <Tabs v-model="statusFilter" class="mb-4">
      <TabsList>
        <TabsTrigger value="pending_review">Pending</TabsTrigger>
        <TabsTrigger value="approved">Approved</TabsTrigger>
        <TabsTrigger value="clarification_requested">Clarification</TabsTrigger>
        <TabsTrigger value="escalated">Escalated</TabsTrigger>
        <TabsTrigger value="rejected_by_operator">Rejected</TabsTrigger>
        <TabsTrigger value="all">All</TabsTrigger>
      </TabsList>
    </Tabs>

    <div
      v-if="isError"
      class="mb-4 flex items-center gap-3 rounded-lg border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive"
    >
      <AlertCircle class="h-4 w-4" />
      <span>{{ (error as Error)?.message ?? "Failed to load orders" }}</span>
    </div>

    <div class="rounded-lg border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Code</TableHead>
            <TableHead>Retailer</TableHead>
            <TableHead>Supplier</TableHead>
            <TableHead class="text-right">Total</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Agent</TableHead>
            <TableHead>Date</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow
            v-for="order in items"
            :key="order.id"
            class="cursor-pointer"
            @click="openOrder(order.id)"
          >
            <TableCell>
              <code class="rounded bg-muted px-1.5 py-0.5 text-xs">{{ order.code }}</code>
            </TableCell>
            <TableCell class="font-medium">{{ order.retailerName }}</TableCell>
            <TableCell>{{ order.supplierName }}</TableCell>
            <TableCell class="text-right font-medium">
              {{ formatMinorUnits(order.totalAmount, order.currencyCode) }}
            </TableCell>
            <TableCell>
              <Badge :variant="statusVariant(order.status)" class="capitalize">
                {{ prettyValue(order.status) }}
              </Badge>
            </TableCell>
            <TableCell>
              <div v-if="order.hasSuggestion && order.suggestionAction" class="flex items-center gap-2">
                <Badge :variant="actionVariant(order.suggestionAction)" class="capitalize">
                  {{ prettyValue(order.suggestionAction) }}
                </Badge>
                <span v-if="order.suggestionConfidence !== null" class="text-xs text-muted-foreground">
                  {{ (order.suggestionConfidence * 100).toFixed(0) }}%
                </span>
              </div>
              <span v-else class="text-xs text-muted-foreground">—</span>
            </TableCell>
            <TableCell class="text-muted-foreground">
              {{ formatDate(order.orderDate) }}
            </TableCell>
          </TableRow>
          <TableRow v-if="!isLoading && items.length === 0">
            <TableCell colspan="7" class="py-8 text-center text-sm text-muted-foreground">
              No orders match this filter.
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </div>

    <footer class="mt-4 flex items-center justify-between text-sm text-muted-foreground">
      <span>
        <template v-if="total > 0">
          Page {{ page }} of {{ totalPages }} — {{ formatCount(total) }} order(s)
        </template>
        <template v-else-if="isLoading">Loading…</template>
      </span>
      <div class="flex items-center gap-2">
        <Button variant="outline" size="sm" :disabled="page <= 1 || isFetching" @click="prevPage">
          <ChevronLeft class="mr-1 h-4 w-4" />
          Previous
        </Button>
        <Button
          variant="outline"
          size="sm"
          :disabled="page >= totalPages || isFetching"
          @click="nextPage"
        >
          Next
          <ChevronRight class="ml-1 h-4 w-4" />
        </Button>
      </div>
    </footer>
  </main>
</template>
