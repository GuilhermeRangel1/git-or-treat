import { fileURLToPath, URL } from "node:url";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vitest/config";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    watch: {
      usePolling: process.env.DEV_USE_POLLING === "true",
      interval: 300,
    },
    proxy: {
      "/api": {
        target: process.env.API_PROXY_TARGET || "http://127.0.0.1:8000",
        changeOrigin: true,
        configure(proxy) {
          proxy.on("proxyReq", (proxyReq, req) => {
            const path = (req.url ?? "").split("?")[0];
            const operational =
              /^\/api\/v1\/inspections\/(orders(?:\/|$)|queue\/[^/]+\/orders$)/.test(
                path,
              );
            const origin = req.headers.origin;
            const sameOrigin =
              !origin ||
              origin === `http://${req.headers.host}` ||
              origin === `https://${req.headers.host}`;
            // Development server only; never expose the service token in VITE_* or browser storage.
            if (
              operational &&
              sameOrigin &&
              process.env.ORDERS_DEV_PROXY_TOKEN
            ) {
              proxyReq.setHeader(
                "Authorization",
                `Bearer ${process.env.ORDERS_DEV_PROXY_TOKEN}`,
              );
            }
          });
        },
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    restoreMocks: true,
    unstubEnvs: true,
    unstubGlobals: true,
  },
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
});
