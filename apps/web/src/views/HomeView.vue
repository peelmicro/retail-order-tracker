<script setup lang="ts">
import { AlertCircle, Package, Receipt, Sparkles, UserCheck } from "lucide-vue-next";
import { computed } from "vue";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatCount, formatDate, formatMinorUnits } from "@/lib/format";
import { useDailyReport } from "@/services/reports";

const { data, isLoading, isError, error } = useDailyReport();

const report = computed(() => data.value);

const statusEntries = computed(() =>
  report.value ? Object.entries(report.value.ordersByStatus) : [],
);

const actionEntries = computed(() =>
  report.value ? Object.entries(report.value.ordersByAgentAction) : [],
);

const statusVariant = (status: string): "default" | "secondary" | "destructive" | "outline" => {
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
  action: string,
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

const prettyStatus = (s: string) => s.replaceAll("_", " ");
</script>

<template>
  <main class="mx-auto max-w-6xl p-6">
    <div class="mb-6">
      <h1 class="text-3xl font-semibold">Daily Report</h1>
      <p v-if="report" class="mt-1 text-sm text-muted-foreground">
        {{ formatDate(report.fromDate) }}
        <template v-if="report.fromDate !== report.toDate">
          — {{ formatDate(report.toDate) }}
        </template>
      </p>
      <p v-else-if="isLoading" class="mt-1 text-sm text-muted-foreground">Loading…</p>
    </div>

    <div
      v-if="isError"
      class="mb-6 flex items-center gap-3 rounded-lg border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive"
    >
      <AlertCircle class="h-4 w-4" />
      <span>{{ (error as Error)?.message ?? "Failed to load report" }}</span>
    </div>

    <!-- KPI cards -->
    <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <Card>
        <CardHeader class="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle class="text-sm font-medium">Total Orders</CardTitle>
          <Package class="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div class="text-2xl font-bold">
            {{ report ? formatCount(report.totalOrders) : "—" }}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader class="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle class="text-sm font-medium">Total Volume</CardTitle>
          <Receipt class="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div class="text-2xl font-bold">
            {{ report ? formatMinorUnits(report.totalAmount) : "—" }}
          </div>
          <p v-if="report" class="mt-1 text-xs text-muted-foreground">
            Avg {{ formatMinorUnits(report.averageAmount) }}
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader class="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle class="text-sm font-medium">Agent Suggestions</CardTitle>
          <Sparkles class="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div class="text-2xl font-bold">
            {{ report ? formatCount(report.suggestionsCount) : "—" }}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader class="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle class="text-sm font-medium">Operator Feedbacks</CardTitle>
          <UserCheck class="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div class="text-2xl font-bold">
            {{ report ? formatCount(report.feedbacksCount) : "—" }}
          </div>
        </CardContent>
      </Card>
    </div>

    <!-- Status + agent action breakdowns -->
    <div class="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Orders by Status</CardTitle>
          <CardDescription>Distribution across review lifecycle</CardDescription>
        </CardHeader>
        <CardContent>
          <div v-if="statusEntries.length > 0" class="flex flex-col gap-2">
            <div
              v-for="[status, count] in statusEntries"
              :key="status"
              class="flex items-center justify-between"
            >
              <Badge :variant="statusVariant(status)" class="capitalize">
                {{ prettyStatus(status) }}
              </Badge>
              <span class="text-sm font-medium">{{ formatCount(count) }}</span>
            </div>
          </div>
          <p v-else class="text-sm text-muted-foreground">No orders yet.</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Orders by Agent Action</CardTitle>
          <CardDescription>What the Analyst Agent recommended</CardDescription>
        </CardHeader>
        <CardContent>
          <div v-if="actionEntries.length > 0" class="flex flex-col gap-2">
            <div
              v-for="[action, count] in actionEntries"
              :key="action"
              class="flex items-center justify-between"
            >
              <Badge :variant="actionVariant(action)" class="capitalize">
                {{ prettyStatus(action) }}
              </Badge>
              <span class="text-sm font-medium">{{ formatCount(count) }}</span>
            </div>
          </div>
          <p v-else class="text-sm text-muted-foreground">No suggestions yet.</p>
        </CardContent>
      </Card>
    </div>

    <!-- Top retailers -->
    <Card class="mt-6">
      <CardHeader>
        <CardTitle>Top Retailers by Orders</CardTitle>
        <CardDescription>Ranked by order count, newest first tie-broken by code</CardDescription>
      </CardHeader>
      <CardContent>
        <Table v-if="report && report.ordersByRetailer.length > 0">
          <TableHeader>
            <TableRow>
              <TableHead>Retailer</TableHead>
              <TableHead>Code</TableHead>
              <TableHead class="text-right">Orders</TableHead>
              <TableHead class="text-right">Volume</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow v-for="row in report.ordersByRetailer" :key="row.retailerCode">
              <TableCell class="font-medium">{{ row.retailerName }}</TableCell>
              <TableCell>
                <code class="rounded bg-muted px-1.5 py-0.5 text-xs">
                  {{ row.retailerCode }}
                </code>
              </TableCell>
              <TableCell class="text-right">{{ formatCount(row.ordersCount) }}</TableCell>
              <TableCell class="text-right">{{ formatMinorUnits(row.totalAmount) }}</TableCell>
            </TableRow>
          </TableBody>
        </Table>
        <p v-else-if="!isLoading" class="text-sm text-muted-foreground">
          No orders for this date range.
        </p>
      </CardContent>
    </Card>
  </main>
</template>
