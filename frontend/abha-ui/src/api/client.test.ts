import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, call, readServerMessages, setBoot, stripHtml } from "./client";

const boot = { csrf_token: "CSRF-1", user: { name: "u", full_name: "U", roles: ["Physician"] }, patient: null, site: "s" };

function reply(status: number, body: unknown) {
  return Promise.resolve(new Response(typeof body === "string" ? body : JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }));
}

beforeEach(() => setBoot(boot));
afterEach(() => vi.unstubAllGlobals());

describe("call", () => {
  it("posts JSON with the session cookie and CSRF token, and resolves with message", async () => {
    const fetchMock = vi.fn(() => reply(200, { message: { txnId: "T1" } }));
    vi.stubGlobal("fetch", fetchMock);
    const out = await call<{ txnId: string }>("a.b.c", { patient: "P1" });
    expect(out).toEqual({ txnId: "T1" });
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/method/a.b.c");
    expect(init.method).toBe("POST");
    expect(init.credentials).toBe("same-origin");
    expect((init.headers as Record<string, string>)["X-Frappe-CSRF-Token"]).toBe("CSRF-1");
    expect(JSON.parse(String(init.body))).toEqual({ patient: "P1" });
  });

  it("surfaces ABDM's own reason from Frappe's nested server messages, without HTML", async () => {
    const inner = JSON.stringify({ message: "<b>ABHA API Error (400)</b><br>loginId: LoginId is invalid", title: "x" });
    vi.stubGlobal("fetch", vi.fn(() => reply(417, { exc_type: "ValidationError", _server_messages: JSON.stringify([inner]) })));
    const err = await call("a.b", {}).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).message).toBe("ABHA API Error (400) loginId: LoginId is invalid");
    expect((err as ApiError).kind).toBe("abdm");
    expect((err as ApiError).status).toBe(417);
  });

  it("treats \"The login session has expired\" as an expired ABHA session, but not an expired OTP", async () => {
    vi.stubGlobal("fetch", vi.fn(() => reply(417, { _server_messages: JSON.stringify([JSON.stringify({ message: "The login session has expired. Please request a new OTP." })]) })));
    expect(((await call("a", {}).catch((e) => e)) as ApiError).kind).toBe("auth");
    vi.stubGlobal("fetch", vi.fn(() => reply(417, { _server_messages: JSON.stringify([JSON.stringify({ message: "The OTP has expired." })]) })));
    expect(((await call("a", {}).catch((e) => e)) as ApiError).kind).toBe("abdm");
  });

  it("treats the branch's \"No active ABHA session found\" as an expired session", async () => {
    vi.stubGlobal("fetch", vi.fn(() => reply(417, { _server_messages: JSON.stringify([JSON.stringify({ message: "No active ABHA session found. Use <b>ABDM → Verify ABHA</b> first, then try again." })]) })));
    expect(((await call("a", {}).catch((e) => e)) as ApiError).kind).toBe("auth");
  });

  it("classifies a CSRF failure, an expired ABHA session, and a permission failure", async () => {
    vi.stubGlobal("fetch", vi.fn(() => reply(400, { exc_type: "CSRFTokenError", _server_messages: JSON.stringify([JSON.stringify({ message: "Invalid Request" })]) })));
    expect(((await call("a", {}).catch((e) => e)) as ApiError).kind).toBe("csrf");

    vi.stubGlobal("fetch", vi.fn(() => reply(417, { _server_messages: JSON.stringify([JSON.stringify({ message: "No valid X-Token found for this patient. Please re-authenticate." })]) })));
    expect(((await call("a", {}).catch((e) => e)) as ApiError).kind).toBe("auth");

    vi.stubGlobal("fetch", vi.fn(() => reply(403, { exc_type: "PermissionError", _server_messages: JSON.stringify([JSON.stringify({ message: "Access denied." })]) })));
    expect(((await call("a", {}).catch((e) => e)) as ApiError).kind).toBe("permission");
  });

  it("reports a network failure and a non-JSON server error plainly", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new TypeError("Failed to fetch"))));
    const net = (await call("a", {}).catch((e) => e)) as ApiError;
    expect(net.kind).toBe("network");
    expect(net.message).toMatch(/could not reach the server/i);

    vi.stubGlobal("fetch", vi.fn(() => reply(502, "<html>Bad gateway</html>")));
    const srv = (await call("a", {}).catch((e) => e)) as ApiError;
    expect(srv.kind).toBe("server");
    expect(srv.message).toMatch(/server had a problem/i);
  });

  it("times out a request that never answers", async () => {
    vi.useFakeTimers();
    vi.stubGlobal(
      "fetch",
      vi.fn((_u: string, init: RequestInit) => new Promise((_res, rej) => init.signal?.addEventListener("abort", () => rej(new DOMException("Aborted", "AbortError"))))),
    );
    const p = call("a", {}, { timeoutMs: 1000 }).catch((e) => e);
    await vi.advanceTimersByTimeAsync(1001);
    expect(((await p) as ApiError).kind).toBe("timeout");
    vi.useRealTimers();
  });

  it("never puts what was sent (Aadhaar, OTP) into an error message", async () => {
    vi.stubGlobal("fetch", vi.fn(() => reply(417, { _server_messages: JSON.stringify([JSON.stringify({ message: "Invalid OTP value" })]) })));
    const err = (await call("a", { aadhaar: "123412341234", otp: "847145" }).catch((e) => e)) as ApiError;
    expect(err.message).not.toMatch(/123412341234|847145/);
  });
});

describe("message helpers", () => {
  it("reads nested server messages and tolerates junk", () => {
    expect(readServerMessages(JSON.stringify([JSON.stringify({ message: "<p>One</p>" }), JSON.stringify({ message: "Two" })]))).toEqual(["One", "Two"]);
    expect(readServerMessages("not json")).toEqual([]);
    expect(readServerMessages(undefined)).toEqual([]);
  });
  it("strips tags and decodes the common entities", () => {
    expect(stripHtml("A&nbsp;&amp;<br/>B <i>c</i> &lt;x&gt;")).toBe("A & B c <x>");
  });
});
