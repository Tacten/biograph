import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../app/App";
import { bootAs, fakeServer, NO_ABHA } from "../test/fakeServer";

function server() {
  return fakeServer({
    get_context: () => NO_ABHA,
    get_consent_text: () => ({ available: true, title: "Terms and Conditions", text: "TERMS TEXT END", code: "abha-enrollment", version: "1.0", sha256: "h" }),
    record_consent: () => ({ consent_name: "CONS-1", consent_version: "1.0" }),
    request_enrolment_otp: () => ({ txnId: "T1" }),
  });
}
const WRITES = ["complete_enrolment", "set_abha_address", "send_mobile_otp", "verify_mobile_otp"];

beforeEach(() => {
  window.location.hash = "#/create";
  bootAs({ name: "PAT-1", patient_name: "Asha Verma" });
});
afterEach(() => vi.restoreAllMocks());

describe("a journey completes without an ABHA", () => {
  it("from the first screen: finishes with the facility patient id and records nothing", async () => {
    const s = server();
    render(<App />);
    await screen.findByRole("heading", { name: "Patient consent" });
    await userEvent.setup().click(screen.getByRole("button", { name: "Continue without an ABHA" }));
    expect(await screen.findByRole("heading", { name: "Continuing without an ABHA" })).toBeInTheDocument();
    expect(within(screen.getByRole("main")).getByText("PAT-1")).toBeInTheDocument();
    expect(s.count("record_consent")).toBe(0);
    expect(s.count("request_enrolment_otp")).toBe(0);
    for (const w of WRITES) expect(s.count(w)).toBe(0);
  });

  it("after an OTP was already sent: leaves without creating or changing anything", async () => {
    const s = server();
    render(<App />);
    const u = userEvent.setup();
    await screen.findByText(/TERMS TEXT END/);
    await u.click(screen.getByRole("checkbox"));
    await u.click(screen.getByRole("button", { name: /Record agreement/ }));
    await u.click(await screen.findByRole("button", { name: "Continue" }));
    await u.type(await screen.findByRole("textbox", { name: "Aadhaar number" }), "123456789012");
    await u.click(screen.getByRole("button", { name: "Send OTP" }));
    await screen.findByRole("heading", { name: "Verify Aadhaar OTP" });
    await u.click(screen.getByRole("button", { name: "Continue without an ABHA" }));
    expect(await screen.findByRole("heading", { name: "Continuing without an ABHA" })).toBeInTheDocument();
    for (const w of WRITES) expect(s.count(w)).toBe(0);
  });

  it("lets the desk register another patient from there", async () => {
    server();
    render(<App />);
    const u = userEvent.setup();
    await screen.findByRole("heading", { name: "Patient consent" });
    await u.click(screen.getByRole("button", { name: "Continue without an ABHA" }));
    await u.click(await screen.findByRole("button", { name: "Register another patient" }));
    expect(await screen.findByText("Select a patient to begin")).toBeInTheDocument();
  });
});
