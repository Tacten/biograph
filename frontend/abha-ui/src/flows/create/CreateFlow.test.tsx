import { StrictMode } from "react";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../../app/App";
import { bootAs, Fail, fakeServer, HAS_ABHA, NO_ABHA, type Handler } from "../../test/fakeServer";

const TERMS = "I voluntarily consent to collecting my identity information. FULL TEXT END.";
const PROFILE = { abha_number: "91-1111-2222-3333", abha_address: "asha.verma@sbx", name: "Asha Devi Verma", mobile: "3210XXXXXX", email: "as***@example.com", gender: "F", dob: "1988-11-05", status: "ACTIVE", photo: "/files/PAT-1-abha-photo.jpg" };

function happy(extra: Record<string, Handler> = {}) {
  return fakeServer({
    get_context: () => NO_ABHA,
    get_consent_text: () => ({ available: true, title: "Terms and Conditions", text: TERMS, code: "abha-enrollment", version: "1.0", sha256: "h" }),
    record_consent: () => ({ consent_name: "CONS-1", consent_version: "1.0", message: "Consent recorded" }),
    request_enrolment_otp: () => ({ txnId: "T1" }),
    resend_aadhaar_otp: () => ({ message: "OTP resent successfully" }),
    complete_enrolment: () => ({ abha_number: "91-1111-2222-3333", abha_address: "1111@sbx", status: "UNVERIFIED", mobile_linked: true, txnId: "T2" }),
    send_mobile_otp: () => ({ txnId: "T3" }),
    verify_mobile_otp: () => ({ message: "Mobile verified. ABHA is now active." }),
    get_abha_suggestions: () => ({ suggestions: ["asha.verma@sbx", "asha1988@sbx", "verma.asha@sbx"] }),
    set_abha_address: (a) => ({ message: "ABHA address confirmed", abha_address: String(a.abha_address) }),
    get_abha_profile: () => PROFILE,
    ...extra,
  });
}

const ui = () => userEvent.setup();
const heading = (name: string) => screen.findByRole("heading", { name });
const box = (name: string) => screen.getByRole("textbox", { name });

async function agree(u = ui()) {
  await heading("Patient consent");
  await screen.findByText(/FULL TEXT END/);
  await u.click(screen.getByRole("checkbox"));
  await u.click(screen.getByRole("button", { name: /Record agreement/ }));
  await heading("How should ABDM confirm the patient?");
  await u.click(screen.getByRole("button", { name: "Continue" })); // Aadhaar OTP is the default route
  await heading("Aadhaar number");
  return u;
}
async function toOtp() {
  const u = await agree();
  await u.type(box("Aadhaar number"), "1234 5678 9012");
  await u.click(screen.getByRole("button", { name: "Send OTP" }));
  await heading("Verify Aadhaar OTP");
  return u;
}
async function toAddress(extra: Record<string, Handler> = {}) {
  const server = happy(extra);
  render(<App />);
  const u = await toOtp();
  await u.keyboard("123456");
  await heading("Choose ABHA address");
  return { u, server };
}

beforeEach(() => {
  window.location.hash = "#/create";
  bootAs({ name: "PAT-1", patient_name: "Asha Verma" });
});
afterEach(() => vi.restoreAllMocks());

describe("create wizard", () => {
  it("shows the full terms before anything else, and asks for Aadhaar only after agreement is recorded", async () => {
    const server = happy();
    render(<App />);
    await heading("Patient consent");
    expect(await screen.findByText(/FULL TEXT END/)).toBeInTheDocument(); // not truncated
    expect(screen.queryByRole("textbox", { name: "Aadhaar number" })).toBeNull();
    const go = screen.getByRole("button", { name: /Record agreement/ });
    expect(go).toBeDisabled(); // "I agree" is required
    await ui().click(screen.getByRole("checkbox"));
    expect(go).toBeEnabled();
    await ui().click(go);
    await heading("How should ABDM confirm the patient?");
    expect(server.last("record_consent")?.args).toEqual({ patient: "PAT-1", consent_type: "ABHA Creation", source: "Registration Desk" });
    expect(server.count("request_enrolment_otp")).toBe(0);
  });

  it("says so, and blocks the agreement, when the site cannot record consent", async () => {
    const server = happy({ get_consent_text: () => ({ available: false, title: "Terms and Conditions", text: TERMS, code: "abha-enrollment", version: "1.0", sha256: "h" }) });
    render(<App />);
    await heading("Patient consent");
    expect(await screen.findByRole("alert")).toHaveTextContent(/consent app \(frappe_abdm\) is not installed/);
    expect(screen.getByRole("checkbox")).toBeDisabled();
    expect(server.count("record_consent")).toBe(0);
  });

  it("refuses a bad Aadhaar number before any call, then sends the OTP with the consent name", async () => {
    const server = happy();
    render(<App />);
    const u = await agree();
    await u.type(box("Aadhaar number"), "12345678901");
    await u.click(screen.getByRole("button", { name: "Send OTP" }));
    expect(await screen.findByText(/exactly 12 digits \(you entered 11\)/)).toBeInTheDocument();
    expect(server.count("request_enrolment_otp")).toBe(0);
    await u.clear(box("Aadhaar number"));
    await u.type(box("Aadhaar number"), "1234 5678 9012");
    await u.click(screen.getByRole("button", { name: "Send OTP" }));
    await heading("Verify Aadhaar OTP");
    expect(server.last("request_enrolment_otp")?.args).toEqual({ patient: "PAT-1", aadhaar: "123456789012", consent_name: "CONS-1" });
  });

  it("shows the server's reason when the Aadhaar is refused (for example the checksum)", async () => {
    happy({ request_enrolment_otp: () => { throw new Fail("Invalid Aadhaar number. Please check and re-enter."); } });
    render(<App />);
    const u = await agree();
    await u.type(box("Aadhaar number"), "123456789012");
    await u.click(screen.getByRole("button", { name: "Send OTP" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid Aadhaar number. Please check and re-enter.");
  });

  it("verifies by itself when the sixth digit is typed, once, without asking for the mobile", async () => {
    const server = happy();
    render(<App />);
    const u = await toOtp();
    await u.keyboard("12345");
    expect(server.count("complete_enrolment")).toBe(0);
    await u.keyboard("6");
    await heading("Choose ABHA address"); // mobile was linked by ABDM: no mobile step
    expect(server.count("complete_enrolment")).toBe(1);
    expect(server.last("complete_enrolment")?.args).toEqual({ patient: "PAT-1", txn_id: "T1", otp: "123456" });
    expect(server.count("send_mobile_otp")).toBe(0);
  });

  it("accepts a pasted code", async () => {
    const server = happy();
    render(<App />);
    const u = await toOtp();
    await u.paste("654321");
    await heading("Choose ABHA address");
    expect(server.last("complete_enrolment")?.args.otp).toBe("654321");
  });

  it("shows ABDM's reason for a wrong OTP, clears the boxes and lets the person try again", async () => {
    let n = 0;
    happy({ complete_enrolment: () => { if (n++ === 0) throw new Fail("ABHA API Error (400)<br>OTP is invalid"); return { abha_number: "91-1111-2222-3333", mobile_linked: true, txnId: "T2" }; } });
    render(<App />);
    const u = await toOtp();
    await u.keyboard("111111");
    expect(await screen.findByRole("alert")).toHaveTextContent("ABHA API Error (400) OTP is invalid");
    expect(screen.getAllByRole("textbox", { name: /Digit/ }).map((b) => (b as HTMLInputElement).value).join("")).toBe("");
    await u.keyboard("222222");
    await heading("Choose ABHA address");
  });

  it("locks Resend after the first send, counting it once even when React runs effects twice", async () => {
    happy();
    render(<StrictMode><App /></StrictMode>);
    await toOtp();
    expect(screen.getByRole("button", { name: /Resend OTP in \d+s/ })).toBeDisabled();
    expect(screen.getByText(/2 resends left/)).toBeInTheDocument();
  });

  it("marks the Aadhaar step done, not skipped, once the person has filled it in", async () => {
    happy();
    render(<App />);
    await toOtp();
    const rail = screen.getByRole("list", { name: "Create ABHA steps" });
    expect(within(rail).getByText("Aadhaar number").closest("li")).toHaveAttribute("data-state", "done");
    expect(within(rail).queryByText("(not needed)")).toBeNull();
  });

  describe("when ABDM did not link the mobile by itself", () => {
    const unlinked = { complete_enrolment: () => ({ abha_number: "91-1111-2222-3333", mobile_linked: false, txnId: "T2" }) };

    it("activates with an OTP to the number on the patient record, without typing it", async () => {
      const server = happy(unlinked);
      render(<App />);
      const u = await toOtp();
      await u.keyboard("123456");
      await heading("Confirm mobile");
      await u.click(screen.getByRole("button", { name: "Send OTP to the number on the patient record" }));
      await heading("Verify mobile OTP");
      expect(server.last("send_mobile_otp")?.args).toEqual({ patient: "PAT-1", txn_id: "T2" });
      await u.keyboard("123456");
      await heading("Choose ABHA address");
      expect(server.last("verify_mobile_otp")?.args).toEqual({ patient: "PAT-1", txn_id: "T3", otp: "123456" });
    });

    it("checks a different mobile before any call", async () => {
      const server = happy(unlinked);
      render(<App />);
      const u = await toOtp();
      await u.keyboard("123456");
      await heading("Confirm mobile");
      await u.click(screen.getByRole("button", { name: "Use a different mobile" }));
      await u.type(box("Mobile number"), "98765");
      await u.click(screen.getByRole("button", { name: "Send OTP" }));
      expect(await screen.findByText(/exactly 10 digits \(you entered 5\)/)).toBeInTheDocument();
      expect(server.count("send_mobile_otp")).toBe(0);
      await u.clear(box("Mobile number"));
      await u.type(box("Mobile number"), "98765 55555");
      await u.click(screen.getByRole("button", { name: "Send OTP" }));
      await heading("Verify mobile OTP");
      expect(server.last("send_mobile_otp")?.args).toEqual({ patient: "PAT-1", txn_id: "T2", mobile: "9876555555" });
    });

    it("asks for a number only when the patient record has none", async () => {
      happy({ ...unlinked, get_context: () => ({ ...NO_ABHA, patient: { ...NO_ABHA.patient, has_mobile: false } }) });
      render(<App />);
      const u = await toOtp();
      await u.keyboard("123456");
      await heading("Confirm mobile");
      expect(screen.getByRole("textbox", { name: "Mobile number" })).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: /number on the patient record/ })).toBeNull();
    });
  });

  it("offers three suggestions and a custom address, and checks the custom one against the policy", async () => {
    const { u, server } = await toAddress();
    expect(screen.getAllByRole("radio")).toHaveLength(4);
    expect(screen.getByRole("radio", { name: "asha.verma@sbx" })).toBeChecked();
    await u.click(screen.getByRole("radio", { name: "Write my own" }));
    expect(screen.getByText("Cannot begin with a digit")).toBeInTheDocument(); // the rules are on screen
    for (const [bad, msg] of [["1asha", /^The address cannot begin with a digit/], [".asha", /^The address cannot begin or end with a dot/], ["9876543210", /^A mobile number cannot be used as the ABHA address/]] as const) {
      await u.clear(screen.getByLabelText("Your address"));
      await u.type(screen.getByLabelText("Your address"), bad);
      await u.click(screen.getByRole("button", { name: "Create this address" }));
      expect(await screen.findByText(msg)).toBeInTheDocument();
    }
    expect(server.count("set_abha_address")).toBe(0);
    await u.clear(screen.getByLabelText("Your address"));
    await u.type(screen.getByLabelText("Your address"), "Asha.V");
    await u.click(screen.getByRole("button", { name: "Create this address" }));
    await heading("ABHA created");
    expect(server.last("set_abha_address")?.args).toEqual({ patient: "PAT-1", abha_address: "asha.v@sbx" });
  });

  it("keeps the alternatives on screen when an address is taken", async () => {
    const { u } = await toAddress({ set_abha_address: () => { throw new Fail("ABHA address is already taken"); } });
    await u.click(screen.getByRole("button", { name: "Create this address" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("already taken");
    expect(screen.getAllByRole("radio")).toHaveLength(4);
  });

  it("ends by showing what ABDM holds, read now, and says the patient record was already updated", async () => {
    const { u, server } = await toAddress();
    await u.click(screen.getByRole("button", { name: "Create this address" }));
    await heading("ABHA created");
    expect(await screen.findByText("Asha Devi Verma")).toBeInTheDocument();
    expect(screen.getByText("Female")).toBeInTheDocument();
    expect(screen.getByText("3210XXXXXX")).toBeInTheDocument(); // masked by the server, shown as received
    expect(screen.getByRole("img", { name: "Photograph of Asha Verma" })).toHaveAttribute("src", "/files/PAT-1-abha-photo.jpg");
    expect(screen.getByText(/patient record has already been updated/)).toBeInTheDocument();
    expect(server.calls.some((c) => /apply|update_abha_profile/.test(c.method))).toBe(false); // the page writes nothing itself
  });

  it("offers the card and QR code, loaded only when asked", async () => {
    URL.createObjectURL = vi.fn(() => "blob:x");
    URL.revokeObjectURL = vi.fn();
    const { u, server } = await toAddress({ download_abha_card: () => ({ card_b64: btoa("PNG") }), get_abha_qr_code: () => ({ qr_code: btoa("PNG") }) });
    await u.click(screen.getByRole("button", { name: "Create this address" }));
    await heading("ABHA created");
    expect(server.count("download_abha_card")).toBe(0);
    await u.click(screen.getByRole("button", { name: "Show ABHA card" }));
    expect(await screen.findByRole("link", { name: "Download ABHA card" })).toHaveAttribute("download", "abha-card.png");
    expect(server.count("get_abha_qr_code")).toBe(0);
  });

  it("does not start a second ABHA for a patient who already has one", async () => {
    const server = happy({ get_context: () => HAS_ABHA });
    render(<App />);
    expect(await screen.findByRole("heading", { name: /already has an ABHA/ })).toBeInTheDocument();
    expect(screen.getByText(/ending 3333/)).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Patient consent" })).toBeNull();
    expect(server.count("record_consent")).toBe(0);
  });

  it("goes back to the agreement when the server says it has lapsed", async () => {
    happy({ request_enrolment_otp: () => { throw new Fail("Record the patient's agreement to the terms before requesting the OTP."); } });
    render(<App />);
    const u = await agree();
    await u.type(box("Aadhaar number"), "123456789012");
    await u.click(screen.getByRole("button", { name: "Send OTP" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/agreement/);
    await u.click(screen.getByRole("button", { name: "Record the agreement again" }));
    await heading("Patient consent");
  });
});
