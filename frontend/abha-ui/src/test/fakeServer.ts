import { vi } from "vitest";
import { setBoot } from "../api/client";

/** Throw from a handler to answer like Frappe does when ABDM or a validation refuses. */
export class Fail extends Error {
  constructor(message: string, readonly status = 417) {
    super(message);
  }
}

export type Handler = (args: Record<string, unknown>) => unknown;
export interface Call {
  method: string;
  args: Record<string, unknown>;
}

const short = (m: string) => m.split(".").pop() ?? m;

/** Stands in for the Frappe site: each `/api/method/<name>` is answered by the handler registered under its last segment. */
export function fakeServer(handlers: Record<string, Handler>) {
  const calls: Call[] = [];
  vi.spyOn(window, "fetch").mockImplementation(async (input, init) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : (input as Request).url;
    const method = short(decodeURIComponent(url.split("/api/method/")[1] ?? ""));
    const args = JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
    calls.push({ method, args });
    const handler = handlers[method];
    if (!handler) return new Response(JSON.stringify({ exc_type: "ValidationError", _server_messages: JSON.stringify([JSON.stringify({ message: `no handler for ${method}` })]) }), { status: 417 });
    try {
      return new Response(JSON.stringify({ message: await handler(args) }), { status: 200 });
    } catch (e) {
      if (e instanceof Fail) {
        return new Response(JSON.stringify({ exc_type: "ValidationError", _server_messages: JSON.stringify([JSON.stringify({ message: e.message })]) }), { status: e.status });
      }
      throw e;
    }
  });
  return { calls, count: (m: string) => calls.filter((c) => c.method === m).length, last: (m: string) => [...calls].reverse().find((c) => c.method === m) };
}

export function bootAs(patient: { name: string; patient_name: string } | null = null) {
  setBoot({ csrf_token: "t", user: { name: "u", full_name: "Desk Nurse", roles: [] }, patient, site: "s" });
}

export const NO_ABHA = { patient: { name: "PAT-1", patient_name: "Asha Verma", sex: null, dob: null, has_mobile: true }, abha: { linked: false, abha_number: null, abha_number_masked: null, abha_address: null, status: null, verified_at: null } };
export const HAS_ABHA = { ...NO_ABHA, abha: { linked: true, abha_number: "91-1111-2222-3333", abha_number_masked: "91-XXXX-XXXX-3333", abha_address: "a@sbx", status: "ACTIVE", verified_at: null } };
