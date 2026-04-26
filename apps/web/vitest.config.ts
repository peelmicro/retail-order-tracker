import { defineConfig, mergeConfig } from "vitest/config";

import viteConfig from "./vite.config";

// Test config lives in its own file so vite.config.ts can import strictly
// from "vite" — keeps vue-tsc happy when vitest's bundled vite version
// differs from the project's (which trips an inconsistent-PluginOption
// error during the production docker build's `npm run build` step).
export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      globals: true,
      environment: "jsdom",
      setupFiles: ["./src/test/setup.ts"],
      css: false,
      include: ["src/**/*.{test,spec}.ts"],
    },
  }),
);
