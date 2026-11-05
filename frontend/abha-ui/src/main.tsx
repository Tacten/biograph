import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { setBoot } from "./api/client";
import type { Boot } from "./api/types";
import { App } from "./app/App";
import "./styles/tokens.css";
import "./styles/app.css";

function readBoot(): Boot | null {
  const el = document.getElementById("abha-boot");
  if (!el?.textContent) return null;
  try {
    return JSON.parse(el.textContent) as Boot;
  } catch {
    return null;
  }
}

async function start(): Promise<void> {
  const root = document.getElementById("abha-root");
  if (!root) return;
  let boot = readBoot();
  if (!boot && import.meta.env.DEV) {
    // `npm run dev` without Frappe: canned patients, no real calls.
    const dev = await import("./dev/mockApi");
    dev.installMockApi();
    boot = dev.DEV_BOOT;
  }
  if (!boot) {
    root.textContent = "The ABHA page could not start: its session data is missing. Reload the page.";
    return;
  }
  setBoot(boot);
  createRoot(root).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}

void start();
