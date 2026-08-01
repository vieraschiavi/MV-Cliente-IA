import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// En dev, /api se proxya al backend FastAPI (puerto 8810).
// En producción el propio backend sirve dist/, así que /api es same-origin.
// base: "./" — hace falta para el APK: dentro del WebView de Capacitor los
// archivos se sirven desde capacitor://localhost y las rutas absolutas (/assets)
// quedan fuera del bundle, así que la app arranca en blanco.
export default defineConfig({
  base: "./",
  plugins: [react()],
  server: { proxy: { "/api": "http://localhost:8810" } },
  build: { outDir: "dist", emptyOutDir: true },
});
