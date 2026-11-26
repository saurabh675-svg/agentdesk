import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"

// Root config for the Vite dev server + production build.
// The app lives in frontend/ (index.html + src/main.tsx); dist goes to frontend/dist.
export default defineConfig({
  root: "frontend",
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
})
