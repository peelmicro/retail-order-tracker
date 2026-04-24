import { VueQueryPlugin } from "@tanstack/vue-query";
import { createPinia } from "pinia";
import { createApp } from "vue";

import App from "./App.vue";
import router from "./router";
import "./style.css";
// vue-sonner ships its own CSS for the toaster overlay container (fixed
// positioning, z-index, CSS vars). Without this, toasts render as plain
// inline text at the bottom of the document.
import "vue-sonner/style.css";

const app = createApp(App);

app.use(createPinia());
app.use(router);
app.use(VueQueryPlugin, {
  queryClientConfig: {
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        refetchOnWindowFocus: false,
      },
    },
  },
});

app.mount("#app");
