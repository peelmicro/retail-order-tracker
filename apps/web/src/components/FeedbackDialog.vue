<script setup lang="ts">
import { computed, ref, watch } from "vue";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ApiError } from "@/lib/api";
import { useSubmitFeedback } from "@/services/feedback";
import type { AgentAction, AgentSuggestionResponse, OperatorDecision } from "@/types/api";

const props = defineProps<{
  open: boolean;
  orderId: string;
  orderCode: string;
  suggestion: AgentSuggestionResponse | null;
}>();

const emit = defineEmits<{
  (e: "update:open", value: boolean): void;
  (e: "submitted"): void;
}>();

const openModel = computed({
  get: () => props.open,
  set: (v: boolean) => emit("update:open", v),
});

const decision = ref<OperatorDecision>("accepted");
const finalAction = ref<AgentAction>("approve");
const operatorReason = ref("");
const error = ref<string | null>(null);

// Whenever the dialog opens with a new suggestion, pre-populate final_action
// with the agent's recommendation (operator typically accepts — mapping stays
// one click away).
watch(
  () => [props.open, props.suggestion?.action] as const,
  ([isOpen, suggestedAction]) => {
    if (isOpen) {
      decision.value = "accepted";
      finalAction.value = (suggestedAction as AgentAction | undefined) ?? "approve";
      operatorReason.value = "";
      error.value = null;
    }
  },
);

const submitMutation = useSubmitFeedback();

async function handleSubmit() {
  error.value = null;
  try {
    await submitMutation.mutateAsync({
      orderId: props.orderId,
      operatorDecision: decision.value,
      finalAction: finalAction.value,
      operatorReason: operatorReason.value.trim() || null,
    });
    // Confirmation toast is delivered via the WebSocket broadcast
    // (order.status_changed event) — no need to fire a duplicate here.
    emit("submitted");
    openModel.value = false;
  } catch (err) {
    error.value =
      err instanceof ApiError
        ? err.message
        : err instanceof Error
          ? err.message
          : "Unknown error";
  }
}

const decisionOptions: { value: OperatorDecision; label: string; hint: string }[] = [
  { value: "accepted", label: "Accept", hint: "Agent was right" },
  { value: "modified", label: "Modify", hint: "Action changed" },
  { value: "rejected", label: "Reject", hint: "Agent was wrong" },
];
</script>

<template>
  <Dialog v-model:open="openModel">
    <DialogContent class="sm:max-w-md">
      <DialogHeader>
        <DialogTitle>Review suggestion</DialogTitle>
        <DialogDescription>
          Record your decision on the Analyst Agent's recommendation for
          <code class="rounded bg-muted px-1 py-0.5 text-xs">{{ orderCode }}</code>.
          This feeds the Phoenix evaluator dataset.
        </DialogDescription>
      </DialogHeader>

      <form class="space-y-4" @submit.prevent="handleSubmit">
        <div class="space-y-2">
          <Label>Operator decision</Label>
          <div class="grid grid-cols-3 gap-2">
            <Button
              v-for="opt in decisionOptions"
              :key="opt.value"
              type="button"
              :variant="decision === opt.value ? 'default' : 'outline'"
              class="h-auto flex-col py-3"
              @click="decision = opt.value"
            >
              <span class="text-sm font-medium">{{ opt.label }}</span>
              <span class="text-xs font-normal opacity-70">{{ opt.hint }}</span>
            </Button>
          </div>
        </div>

        <div class="space-y-2">
          <Label for="final-action">Final action</Label>
          <Select v-model="finalAction">
            <SelectTrigger id="final-action">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="approve">Approve order</SelectItem>
              <SelectItem value="request_clarification">Request clarification</SelectItem>
              <SelectItem value="escalate">Escalate to supervisor</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div class="space-y-2">
          <Label for="reason">Reason (optional)</Label>
          <textarea
            id="reason"
            v-model="operatorReason"
            rows="3"
            placeholder="e.g. Quantity anomaly matches supplier's new campaign"
            class="w-full rounded-md border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>

        <p v-if="error" class="text-sm text-destructive">{{ error }}</p>

        <DialogFooter class="gap-2 sm:gap-2">
          <Button
            type="button"
            variant="outline"
            :disabled="submitMutation.isPending.value"
            @click="openModel = false"
          >
            Cancel
          </Button>
          <Button type="submit" :disabled="submitMutation.isPending.value">
            {{ submitMutation.isPending.value ? "Submitting…" : "Submit feedback" }}
          </Button>
        </DialogFooter>
      </form>
    </DialogContent>
  </Dialog>
</template>
