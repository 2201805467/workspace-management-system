import { defineConfig } from "@playwright/test";
import path from "node:path";

export default defineConfig({
  testDir: "./tests",
  workers: 1,
  use: {
    baseURL: "http://localhost:5174",
    channel: process.env.PLAYWRIGHT_CHANNEL || "msedge",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: process.env.TEST_PYTHON
        ? `"${process.env.TEST_PYTHON}" -m tests.serve_browser`
        : `"${path.resolve(import.meta.dirname, "../backend", process.platform === "win32" ? ".venv/Scripts/python.exe" : ".venv/bin/python")}" -m tests.serve_browser`,
      cwd: path.resolve(import.meta.dirname, "../backend"),
      url: "http://127.0.0.1:8001/api/health",
      reuseExistingServer: false,
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 5174 --strictPort",
      env: { API_PROXY_TARGET: "http://127.0.0.1:8001" },
      url: "http://localhost:5174",
      reuseExistingServer: false,
    },
  ],
});
