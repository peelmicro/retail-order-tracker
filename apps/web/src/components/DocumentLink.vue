<script setup lang="ts">
import { FileDown } from "lucide-vue-next";

import { Button } from "@/components/ui/button";
import { useDocument } from "@/services/documents";

const props = defineProps<{
  documentId: string;
}>();

const { data, isLoading } = useDocument(() => props.documentId);
</script>

<template>
  <div class="flex items-center gap-2 rounded-md border p-2">
    <FileDown class="h-4 w-4 text-muted-foreground" />
    <div class="min-w-0 flex-1">
      <p v-if="isLoading" class="text-sm text-muted-foreground">Loading…</p>
      <p v-else-if="data" class="truncate text-sm font-medium">{{ data.filename }}</p>
    </div>
    <Button
      v-if="data?.presignedUrl"
      size="sm"
      variant="outline"
      as-child
    >
      <a :href="data.presignedUrl" target="_blank" rel="noopener">Download</a>
    </Button>
  </div>
</template>
