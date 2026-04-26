<script setup lang="ts">
import { Sparkles } from "lucide-vue-next";
import { toast } from "vue-sonner";

import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { useRunAnalystOnOrder } from "@/services/agents";

const props = withDefaults(
  defineProps<{
    orderId: string;
    orderCode?: string;
    size?: "sm" | "default";
    variant?: "default" | "outline" | "secondary";
  }>(),
  {
    orderCode: undefined,
    size: "sm",
    variant: "outline",
  },
);

const emit = defineEmits<{ (e: "completed"): void }>();

const mutation = useRunAnalystOnOrder();

async function handleClick(event: MouseEvent) {
  // Prevent the parent row click handler (drill-into-detail) from firing
  // when the button is rendered inside a clickable table row.
  event.stopPropagation();
  try {
    const result = await mutation.mutateAsync(props.orderId);
    toast.success(
      `Analyst ran${props.orderCode ? ` on ${props.orderCode}` : ""}`,
      {
        description: `Action: ${result.action.replaceAll("_", " ")} · ${(result.confidence * 100).toFixed(0)}% confidence`,
      },
    );
    emit("completed");
  } catch (err) {
    const message =
      err instanceof ApiError
        ? err.message
        : err instanceof Error
          ? err.message
          : "Unknown error";
    toast.error("Analyst run failed", { description: message });
  }
}
</script>

<template>
  <Button :variant="variant" :size="size" :disabled="mutation.isPending.value" @click="handleClick">
    <Sparkles class="size-3.5" />
    {{ mutation.isPending.value ? "Analysing…" : "Run analysis" }}
  </Button>
</template>
