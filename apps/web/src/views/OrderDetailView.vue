<script setup lang="ts">
import { AlertCircle, ArrowLeft, CheckCircle2, Sparkles, UserCheck } from "lucide-vue-next";
import { computed, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import DocumentLink from "@/components/DocumentLink.vue";
import FeedbackDialog from "@/components/FeedbackDialog.vue";
import RunAnalysisButton from "@/components/RunAnalysisButton.vue";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatDate, formatMinorUnits } from "@/lib/format";
import { useOrderDetail } from "@/services/orders";
import type { AgentAction, OrderStatus } from "@/types/api";

const route = useRoute();
const router = useRouter();

const orderId = computed(() => route.params.id as string);
const { data: order, isLoading, isError, error } = useOrderDetail(orderId);

const dialogOpen = ref(false);

const canReview = computed(
  () => order.value?.suggestion !== null && order.value?.feedback === null,
);

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
</script>

<template>
  <main class="mx-auto max-w-5xl p-6">
    <Button
      variant="ghost"
      size="sm"
      class="mb-4"
      @click="router.push({ name: 'orders' })"
    >
      <ArrowLeft class="mr-1 h-4 w-4" />
      Back to Review Queue
    </Button>

    <div
      v-if="isError"
      class="flex items-center gap-3 rounded-lg border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive"
    >
      <AlertCircle class="h-4 w-4" />
      <span>{{ (error as Error)?.message ?? "Failed to load order" }}</span>
    </div>

    <p v-else-if="isLoading" class="text-sm text-muted-foreground">Loading…</p>

    <template v-else-if="order">
      <!-- Header -->
      <div class="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p class="text-sm text-muted-foreground">
            Order number <code class="ml-1 rounded bg-muted px-1.5 py-0.5 text-xs">{{ order.orderNumber }}</code>
            · Code <code class="ml-1 rounded bg-muted px-1.5 py-0.5 text-xs">{{ order.code }}</code>
          </p>
          <h1 class="mt-1 text-2xl font-semibold">
            {{ order.retailerName }}
            <span class="text-muted-foreground">→</span>
            {{ order.supplierName }}
          </h1>
          <p class="mt-1 text-sm text-muted-foreground">
            {{ formatDate(order.orderDate) }}
            <template v-if="order.expectedDeliveryDate">
              · delivery {{ formatDate(order.expectedDeliveryDate) }}
            </template>
          </p>
        </div>

        <div class="flex items-center gap-3">
          <Badge :variant="statusVariant(order.status)" class="capitalize">
            {{ prettyValue(order.status) }}
          </Badge>
          <div class="text-right">
            <p class="text-xs uppercase text-muted-foreground">Total</p>
            <p class="text-xl font-semibold">
              {{ formatMinorUnits(order.totalAmount, order.currencyCode) }}
            </p>
          </div>
        </div>
      </div>

      <div class="flex items-center gap-2">
        <Button :disabled="!canReview" @click="dialogOpen = true">
          {{ canReview ? "Review suggestion" : order.feedback ? "Already reviewed" : "No suggestion yet" }}
        </Button>
      </div>

      <!-- Documents -->
      <section v-if="order.documents.length > 0" class="mt-6 space-y-2">
        <h2 class="text-sm font-medium text-muted-foreground">Original document(s)</h2>
        <div class="grid gap-2 sm:grid-cols-2">
          <DocumentLink
            v-for="docId in order.documents"
            :key="docId"
            :document-id="docId"
          />
        </div>
      </section>

      <!-- Agent suggestion + feedback cards -->
      <div class="mt-6 grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader class="flex flex-row items-center justify-between">
            <div>
              <CardTitle class="flex items-center gap-2">
                <Sparkles class="h-4 w-4" />
                Analyst Agent
              </CardTitle>
              <CardDescription v-if="order.suggestion">
                {{ (order.suggestion.confidence * 100).toFixed(0) }}% confidence
              </CardDescription>
              <CardDescription v-else>No suggestion yet</CardDescription>
            </div>
            <Badge
              v-if="order.suggestion"
              :variant="actionVariant(order.suggestion.action)"
              class="capitalize"
            >
              {{ prettyValue(order.suggestion.action) }}
            </Badge>
          </CardHeader>
          <CardContent v-if="order.suggestion" class="space-y-3 text-sm">
            <p class="whitespace-pre-wrap">{{ order.suggestion.reasoning }}</p>
            <div v-if="order.suggestion.anomaliesDetected.length > 0" class="space-y-1">
              <p class="text-xs font-medium uppercase text-muted-foreground">
                Anomalies detected
              </p>
              <ul class="list-disc space-y-1 pl-5">
                <li v-for="a in order.suggestion.anomaliesDetected" :key="a">{{ a }}</li>
              </ul>
            </div>
            <p v-if="order.suggestion.phoenixTraceId" class="text-xs text-muted-foreground">
              Phoenix trace
              <code class="rounded bg-muted px-1 py-0.5">
                {{ order.suggestion.phoenixTraceId.slice(0, 12) }}…
              </code>
            </p>
          </CardContent>
          <CardContent v-else class="space-y-3 text-sm text-muted-foreground">
            <p>Run the Analyst Agent on this order to generate a suggestion.</p>
            <RunAnalysisButton
              v-if="order.status === 'pending_review'"
              :order-id="order.id"
              :order-code="order.code"
              size="default"
              variant="default"
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader class="flex flex-row items-center justify-between">
            <div>
              <CardTitle class="flex items-center gap-2">
                <UserCheck class="h-4 w-4" />
                Operator decision
              </CardTitle>
              <CardDescription v-if="order.feedback">
                {{ formatDate(order.feedback.createdAt) }}
              </CardDescription>
              <CardDescription v-else>No feedback yet</CardDescription>
            </div>
            <div v-if="order.feedback" class="flex items-center gap-2">
              <CheckCircle2 class="h-4 w-4 text-muted-foreground" />
              <Badge variant="outline" class="capitalize">
                {{ prettyValue(order.feedback.operatorDecision) }}
              </Badge>
            </div>
          </CardHeader>
          <CardContent v-if="order.feedback" class="space-y-3 text-sm">
            <div class="flex items-center gap-2">
              <span class="text-xs text-muted-foreground">Final action:</span>
              <Badge
                :variant="actionVariant(order.feedback.finalAction)"
                class="capitalize"
              >
                {{ prettyValue(order.feedback.finalAction) }}
              </Badge>
            </div>
            <p v-if="order.feedback.operatorReason" class="whitespace-pre-wrap">
              {{ order.feedback.operatorReason }}
            </p>
          </CardContent>
          <CardContent v-else class="text-sm text-muted-foreground">
            The operator's review records whether they agreed with the agent and
            the final action taken. Exported to Phoenix as a labelled example.
          </CardContent>
        </Card>
      </div>

      <!-- Line items -->
      <Card class="mt-6">
        <CardHeader>
          <CardTitle>Line items</CardTitle>
          <CardDescription>{{ order.lineItems.length }} item(s)</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead class="w-12">#</TableHead>
                <TableHead>Product code</TableHead>
                <TableHead>Description</TableHead>
                <TableHead class="text-right">Qty</TableHead>
                <TableHead class="text-right">Unit price</TableHead>
                <TableHead class="text-right">Line total</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow v-for="li in order.lineItems" :key="li.lineNumber">
                <TableCell>{{ li.lineNumber }}</TableCell>
                <TableCell>
                  <code class="rounded bg-muted px-1.5 py-0.5 text-xs">{{ li.productCode }}</code>
                </TableCell>
                <TableCell>{{ li.productName ?? "—" }}</TableCell>
                <TableCell class="text-right">{{ li.quantity }}</TableCell>
                <TableCell class="text-right">
                  {{ formatMinorUnits(li.unitPrice, order.currencyCode) }}
                </TableCell>
                <TableCell class="text-right font-medium">
                  {{ formatMinorUnits(li.lineTotal, order.currencyCode) }}
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <!-- Feedback dialog -->
      <FeedbackDialog
        v-model:open="dialogOpen"
        :order-id="order.id"
        :order-code="order.code"
        :suggestion="order.suggestion"
      />
    </template>
  </main>
</template>
