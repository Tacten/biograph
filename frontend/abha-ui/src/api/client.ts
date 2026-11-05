import type { Boot } from "./types";

export type ApiErrorKind = "abdm" | "validation" | "auth" | "csrf" | "permission" | "network" | "timeout" | "server";

/** An error from the backend, carrying the reason as ABDM or Frappe gave it. Never carries a request body. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly kind: ApiErrorKind,
    readonly status = 0,
    readonly excType?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

let boot: Boot | null = null;

export function setBoot(b: Boot): void {
  boot = b;
}

export function getBoot(): Boot {
  if (!boot) throw new Error("The app was started without boot data.");
  return boot;
}

const TIMEOUT_MS = 60_000;

/** Frappe wraps messages as a JSON string of JSON strings, each holding an HTML message. */
export function readServerMessages(raw: unknown): string[] {
  if (typeof raw !== "string") return [];
  try {
    const list = JSON.parse(raw) as unknown;
    if (!Array.isArray(list)) return [];
    return list
      .map((item) => {
        try {
          const o = JSON.parse(String(item)) as { message?: unknown };
          return typeof o.message === "string" ? o.message : String(item);
        } catch {
          return String(item);
        }
      })
      .map(stripHtml)
      .filter(Boolean);
  } catch {
    return [];
  }
}

export function stripHtml(html: string): string {
  return html
    .replace(/<br\s*\/?>/gi, " ")
    .replace(/<[^>]*>/g, "")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/\s+/g, " ")
    .trim();
}

function classify(status: number, excType: string | undefined, message: string): ApiErrorKind {
  if (excType === "CSRFTokenError" || /csrf/i.test(message)) return "csrf";
  if (status === 401 || /session (has )?expired|no active abha session|please (re-?)?authenticate|x-?token/i.test(message)) return "auth";
  if (status === 403 || excType === "PermissionError") return "permission";
  if (status >= 500 && !message) return "server";
  return "abdm";
}

export interface CallOptions {
  signal?: AbortSignal;
  timeoutMs?: number;
}

/** POST /api/method/<method> with the Frappe session and CSRF token. Resolves with `message`. */
export async function call<T>(method: string, args: Record<string, unknown> = {}, opts: CallOptions = {}): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), opts.timeoutMs ?? TIMEOUT_MS);
  opts.signal?.addEventListener("abort", () => controller.abort());
  let res: Response;
  try {
    res = await fetch(`/api/method/${method}`, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        "X-Frappe-CSRF-Token": getBoot().csrf_token,
      },
      body: JSON.stringify(args),
      signal: controller.signal,
    });
  } catch (e) {
    const aborted = e instanceof DOMException && e.name === "AbortError";
    throw new ApiError(
      aborted ? "The request took too long. Check the connection and try again." : "Could not reach the server. Check the connection and try again.",
      aborted ? "timeout" : "network",
    );
  } finally {
    clearTimeout(timer);
  }

  let body: Record<string, unknown> = {};
  try {
    body = (await res.json()) as Record<string, unknown>;
  } catch {
    /* an empty or non-JSON body: fall through to the status */
  }

  if (res.ok) return body.message as T;

  const excType = typeof body.exc_type === "string" ? body.exc_type : undefined;
  const messages = readServerMessages(body._server_messages);
  // What the server itself said; empty when it said nothing. Classify on this, not on the fallback below.
  const said = messages[messages.length - 1] || (typeof body.message === "string" ? stripHtml(body.message) : "");
  const message = said || (res.status >= 500 ? "The server had a problem. Try again in a moment." : `The request failed (${res.status}).`);
  throw new ApiError(message, classify(res.status, excType, said), res.status, excType);
}
