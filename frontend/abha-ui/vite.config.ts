/// <reference types="vitest" />
import { resolve } from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Production build goes straight into the Frappe app's public folder, which Frappe serves at
// /assets/healthcare/. File names are fixed (no hashes); the /abha page adds ?v=<mtime> for cache busting.
export default defineConfig(({ mode }) => ({
  plugins: [react()],
  base: mode === "production" ? "/assets/healthcare/abha-ui/" : "/",
  build: {
    outDir: resolve(__dirname, "../../healthcare/public/abha-ui"),
    emptyOutDir: true,
    cssCodeSplit: false,
    sourcemap: false,
    target: "es2020",
    rollupOptions: {
      input: resolve(__dirname, "src/main.tsx"),
      output: {
        entryFileNames: "assets/abha-ui.js",
        chunkFileNames: "assets/[name].js",
        assetFileNames: "assets/abha-ui[extname]",
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
}));
