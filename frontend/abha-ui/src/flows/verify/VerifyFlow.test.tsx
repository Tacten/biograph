import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../../app/App";
import { bootAs, Fail, fakeServer, HAS_ABHA, NO_ABHA, type Handler } from "../../test/fakeServer";

const PROFILE = { abha_number: "91-1111-2222-3333", abha_address: "asha@sbx", name: "Asha Devi Verma", mobile: "3210XXXXXX", email: "", gender: "F", dob: "1988-11-05", status: "ACTIVE", photo: null };
const LOGIN = { abha_number: "91111122223333", abha_address: "asha@sbx", name: "Asha Devi Verma", gender: "F", mobile: "", dob: "1988-11-05" };
const LINKED = { ...HAS_ABHA, abha: { ...HAS_ABHA.abha, abha_address: "asha@sbx" } };

function server(extra: Record<string, Handler> = {}) {
  return fakeServer({
    get_context: () => LINKED,
    request_abha_login_otp: () => ({ txnId: "L1" }),
    verify_abha_login_otp: () => LOGIN,
    request_abha_address_otp: () => ({ txnId: "A1" }),
    verify_abha_address_otp: () => LOGIN,
    get_abha_profile: () => PROFILE,
    get_consent_text: () => ({ available: true, title: "Terms and Conditions", text: "TERMS TEXT END", code: "abha-enrollment", version: "1.0", sha256: "h" }),
    record_consent: () => ({ consent_name: "CONS-1", consent_version: "1.0" }),
    request_enrolment_otp: () => ({ txnId: "E1" }),
    ...extra,
  });
}
const heading = (name: string) => screen.findByRole("heading", { name });

beforeEach(() => {
  window.location.hash = "#/verify";
  bootAs({ name: "PAT-1", patient_name: "Asha Verma" });
});
afterEach(() => vi.restoreAllMocks());

describe("verify in the app", () => {
  it("uses the ABHA number already on the record: shown masked, nothing typed", async () => {
    const s = server();
    render(<App />);
    await heading("Identify the patient");
    expect(screen.getByTestId("known-identifier")).toHaveTextContent("91-XXXX-XXXX-3333");
    expect(screen.queryByRole("textbox")).toBeNull();
    await userEvent.setup().click(screen.getByRole("button", { name: "Continue" }));
    await heading("Verify OTP");
    expect(s.last("request_abha_login_otp")?.args).toEqual({ patient: "PAT-1", login_id: "91111122223333", login_hint: "abha-number" });
  });

  it("offers only the identifiers on the record to a patient who has an ABHA, never Aadhaar", async () => {
    server();
    render(<App />);
    await heading("Identify the patient");
    expect(screen.getAllByRole("radio").map((r) => r.closest("label")?.textContent)).toEqual(["ABHA number", "ABHA address"]);
  });

  it("verifies at the sixth digit, then shows what ABDM holds and offers the card", async () => {
    const s = server();
    render(<App />);
    const u = userEvent.setup();
    await heading("Identify the patient");
    await u.click(screen.getByRole("button", { name: "Continue" }));
    await heading("Verify OTP");
    await u.keyboard("123456");
    await heading("ABHA verified");
    expect(s.last("verify_abha_login_otp")?.args).toEqual({ patient: "PAT-1", txn_id: "L1", otp: "123456", login_hint: "abha-number" });
    expect(await screen.findByText("Asha Devi Verma")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Show ABHA card" })).toBeInTheDocument();
    expect(screen.getByText(/verified for this session/)).toBeInTheDocument();
  });

  it("verifies with the ABHA address on the record, asking which kind of OTP", async () => {
    const s = server();
    render(<App />);
    const u = userEvent.setup();
    await heading("Identify the patient");
    await u.click(screen.getByRole("radio", { name: "ABHA address" }));
    expect(screen.getByTestId("known-identifier")).toHaveTextContent("asha@sbx");
    await u.click(screen.getByRole("button", { name: "Continue" }));
    await heading("Choose OTP method");
    await u.click(screen.getByRole("radio", { name: /Aadhaar OTP/ }));
    await u.click(screen.getByRole("button", { name: "Send OTP" }));
    await heading("Verify OTP");
    expect(s.last("request_abha_address_otp")?.args).toEqual({ patient: "PAT-1", abha_address: "asha@sbx", otp_system: "aadhaar" });
    await u.keyboard("123456");
    await heading("ABHA verified");
    expect(s.last("verify_abha_address_otp")?.args).toEqual({ patient: "PAT-1", txn_id: "A1", otp: "123456", otp_system: "aadhaar" });
  });

  it("shows ABDM's reason for a wrong OTP and clears the boxes", async () => {
    server({ verify_abha_login_otp: () => { throw new Fail("ABHA API Error (400)<br>OTP is invalid"); } });
    render(<App />);
    const u = userEvent.setup();
    await heading("Identify the patient");
    await u.click(screen.getByRole("button", { name: "Continue" }));
    await heading("Verify OTP");
    await u.keyboard("111111");
    expect(await screen.findByRole("alert")).toHaveTextContent("ABHA API Error (400) OTP is invalid");
    expect(screen.getAllByRole("textbox", { name: /Digit/ }).map((b) => (b as HTMLInputElement).value).join("")).toBe("");
  });

  it("warns, rather than celebrating, when ABDM verified a different ABHA than the one on the record", async () => {
    server({ verify_abha_login_otp: () => ({ ...LOGIN, abha_number: "91999988887777" }) });
    render(<App />);
    const u = userEvent.setup();
    await heading("Identify the patient");
    await u.click(screen.getByRole("button", { name: "Continue" }));
    await heading("Verify OTP");
    await u.keyboard("123456");
    await heading("ABHA verified");
    expect(screen.getByText(/different number than the one on this patient's record/)).toBeInTheDocument();
    expect(screen.queryByText(/verified for this session/)).toBeNull();
  });

  it("explains an ABHA that another patient record already holds, and offers to open that record", async () => {
    server({ verify_abha_login_otp: () => { throw new Fail("This ABHA number is already linked to a different patient record (Ben B Singh). Please confirm you are verifying the correct patient."); } });
    render(<App />);
    const u = userEvent.setup();
    await heading("Identify the patient");
    await u.click(screen.getByRole("button", { name: "Continue" }));
    await heading("Verify OTP");
    await u.keyboard("123456");
    expect(await screen.findByText(/already belongs to the patient record/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open the record" })).toHaveAttribute("href", "/app/patient/Ben%20B%20Singh");
    await u.click(screen.getByRole("button", { name: "Verify Ben B Singh here" }));
    expect(await screen.findByTestId("patient-chip")).toHaveTextContent("Ben B Singh");
    await heading("Identify the patient");
  });

  describe("for a patient without an ABHA", () => {
    const none = { get_context: () => NO_ABHA };

    it("offers Aadhaar, ABHA number and ABHA address, and refuses a wrong shape with no call", async () => {
      const s = server(none);
      render(<App />);
      const u = userEvent.setup();
      await heading("Identify the patient");
      expect(screen.getAllByRole("radio").map((r) => r.closest("label")?.textContent)).toEqual(["Aadhaar number", "ABHA number", "ABHA address"]);
      const cases: [string, string, RegExp][] = [["Aadhaar number", "12345678901", /exactly 12 digits \(you entered 11\)/], ["ABHA number", "91-1111-2222-333", /exactly 14 digits \(you entered 13\)/], ["ABHA address", "asha", /full ABHA address/]];
      for (const [label, bad, msg] of cases) {
        await u.click(screen.getByRole("radio", { name: label }));
        await u.type(screen.getByRole("textbox", { name: label }), bad);
        await u.click(screen.getByRole("button", { name: "Continue" }));
        expect(await screen.findByText(msg)).toBeInTheDocument();
      }
      expect(s.count("request_abha_login_otp") + s.count("request_abha_address_otp")).toBe(0);
    });

    it("hands an Aadhaar with no ABHA over to creation without asking for the number again", async () => {
      const s = server({ ...none, request_abha_login_otp: () => { throw new Fail("ABDM-1114: No ABHA found for this Aadhaar"); } });
      render(<App />);
      const u = userEvent.setup();
      await heading("Identify the patient");
      await u.type(screen.getByRole("textbox", { name: "Aadhaar number" }), "1234 5678 9012");
      await u.click(screen.getByRole("button", { name: "Continue" }));
      await heading("Verify OTP");
      await u.click(await screen.findByRole("button", { name: "Create an ABHA with this Aadhaar" }));
      await heading("Patient consent");
      await screen.findByText(/TERMS TEXT END/);
      await u.click(screen.getByRole("checkbox"));
      await u.click(screen.getByRole("button", { name: /Record agreement/ }));
      await heading("How should ABDM confirm the patient?");
      await u.click(screen.getByRole("button", { name: "Continue" }));
      await heading("Verify Aadhaar OTP");
      expect(screen.queryByRole("textbox", { name: "Aadhaar number" })).toBeNull();
      expect(s.last("request_enrolment_otp")?.args).toEqual({ patient: "PAT-1", aadhaar: "123456789012", consent_name: "CONS-1" });
      const rail = screen.getByRole("list", { name: "Create ABHA steps" });
      expect(within(rail).getByText("Aadhaar number").closest("li")).toHaveAttribute("data-state", "skipped");
    });
  });
});
