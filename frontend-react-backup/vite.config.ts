import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      injectRegister: "inline",
      includeAssets: ["icons/icon-192.png", "icons/icon-512.png"],
      workbox: {
        navigateFallback: "index.html",
        navigateFallbackDenylist: [/^\/api/, /^\/ws/],
        runtimeCaching: [
          {
            urlPattern: /\/(index\.html)?$/,
            handler: "NetworkFirst",
            options: {
              cacheName: "pages",
              expiration: { maxEntries: 10, maxAgeSeconds: 60 },
            },
          },
        ],
      },
      manifest: {
        name: "Mis Tareas",
        short_name: "Tareas",
        description: "Gestor de tareas con recordatorios y kanban",
        theme_color: "#667eea",
        background_color: "#0a0a0b",
        display: "standalone",
        orientation: "portrait",
        icons: [
          { src: "icons/icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "icons/icon-512.png", sizes: "512x512", type: "image/png" },
        ],
      },
    }),
  ],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:8077", changeOrigin: true },
      "/ws": { target: "ws://localhost:8077", ws: true },
    },
  },
  build: {
    outDir: "../web",
    emptyOutDir: true,
  },
});
