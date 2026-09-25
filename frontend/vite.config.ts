import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Vitest is configured inline so `npm test` needs no extra config file.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test-setup.ts"],
  },
});
