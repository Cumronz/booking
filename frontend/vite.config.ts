import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// В dev-режиме запросы к /api и /media проксируются на Django (порт 8000)
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/media": "http://127.0.0.1:8000",
    },
  },
});
