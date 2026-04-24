<script setup lang="ts">
import { computed } from "vue";

import { Badge } from "@/components/ui/badge";

const props = defineProps<{
  status: "OPEN" | "CONNECTING" | "CLOSED";
}>();

const label = computed(() => {
  switch (props.status) {
    case "OPEN":
      return "Live";
    case "CONNECTING":
      return "Connecting…";
    case "CLOSED":
    default:
      return "Offline";
  }
});

const variant = computed<"default" | "secondary" | "destructive" | "outline">(() => {
  switch (props.status) {
    case "OPEN":
      return "default";
    case "CONNECTING":
      return "secondary";
    case "CLOSED":
    default:
      return "destructive";
  }
});

const dotClass = computed(() => {
  switch (props.status) {
    case "OPEN":
      return "bg-green-500 animate-pulse";
    case "CONNECTING":
      return "bg-amber-500 animate-pulse";
    case "CLOSED":
    default:
      return "bg-red-500";
  }
});
</script>

<template>
  <Badge :variant="variant" class="gap-1.5 pl-1.5">
    <span :class="['h-2 w-2 rounded-full', dotClass]" />
    <span class="text-xs">{{ label }}</span>
  </Badge>
</template>
