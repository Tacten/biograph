import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../../app/App";
import { RdServiceError, type RdClient } from "../../rd/rdService";
import { bootAs, Fail, fakeServer, NO_ABHA, type Handler } from "../../test/fakeServer";

vi.mock("../../ui/image", () => ({
  toJpegBase64: vi.fn(async (f: File) => (f.name.startsWith("front") ? "FRONTB64" : "BACKB64")),
}));

const TERMS = { available: true, title: "Terms and Conditions", text: "TERMS TEXT END", code: "abha-enrollment", version: "1.4", sha256: "h" };
const ROUTES = { aadhaar_otp: true, driving_licence: true, biometric: false, can_approve: false };
const heading = (name: string) => screen.findByRole("heading", { name });
const box = (name: string) => screen.getByRole("textbox", { name });

function server(extra: Record<string, Handler> = {}) {
  return fakeServer({
    get_context: () => ({ ...NO_ABHA, patient: { ...NO_ABHA.patient, patient_name: "Asha Devi Verma", sex: "Female", dob: "1988-11-05" } }),
    get_routes: () => ROUTES,
    get_consent_text: () => TERMS,
    record_consent: () => ({ consent_name: "CONS-1", consent_version: "1.4" }),
    request_document_otp: () => ({ txnId: "D1" }),
    verify_dl_otp: () => ({ txnId: "D2" }),
    submit_for_approval: () => ({ name: "ABHA-DOC-00001", status: "Awaiting approval" }),
    get_status: () => ({ name: "ABHA-DOC-00001", status: "Awaiting approval" }),
    request_enrolment_otp: () => ({ txnId: "E1" }),
    enrol_by_biometric: () => ({ abha_number: "91-1111-2222-3333", abha_address: "x@sbx", mobile_linked: true, txnId: "B1" }),
    get_abha_suggestions: () => ({ suggestions: ["asha.verma@sbx", "asha1988@sbx", "verma.asha@sbx"] }),
    ...extra,
  });
}

async function toMethod(u = userEvent.setup()) {
  await heading("Patient consent");
  await screen.findByText(/TERMS TEXT END/);
  await u.click(screen.getByRole("checkbox"));
  await u.click(screen.getByRole("button", { name: /Record agreement/ }));
  await heading("How should ABDM confirm the patient?");
  return u;
}

beforeEach(() => {
  window.location.hash = "#/create";
  bootAs({ name: "PAT-1", patient_name: "Asha Verma" });
  localStorage.clear();
  sessionStorage.clear();
});
afterEach(() => vi.restoreAllMocks());

describe("the method choice", () => {
  it("offers Aadhaar OTP and driving licence, and no fingerprint until the site enables it", async () => {
    server();
    render(<App />);
    await toMethod();
    expect(screen.getAllByRole("radio").map((r) => r.closest("label")?.querySelector("strong")?.textContent)).toEqual(["Aadhaar OTP", "Driving licence"]);
    expect(screen.getByRole("radio", { name: /Aadhaar OTP/ })).toBeChecked();
  });

  it("offers the fingerprint route when the site enables it", async () => {
    server({ get_routes: () => ({ ...ROUTES, biometric: true }) });
    render(<App />);
    await toMethod();
    expect(await screen.findByRole("radio", { name: /Aadhaar fingerprint/ })).toBeInTheDocument();
  });
});

describe("driving licence", () => {
  async function toDetails(extra: Record<string, Handler> = {}) {
    const s = server(extra);
    render(<App />);
    const u = await toMethod();
    await u.click(screen.getByRole("radio", { name: /Driving licence/ }));
    await u.click(screen.getByRole("button", { name: "Continue" }));
    await heading("Mobile number");
    await u.click(screen.getByRole("button", { name: "Send OTP to the number on the patient record" }));
    await heading("Verify mobile OTP");
    await u.keyboard("123456");
    await heading("Licence details and photos");
    return { u, s };
  }

  it("sends the OTP to the number on the record without asking for it, then verifies it", async () => {
    const { s } = await toDetails();
    expect(s.last("request_document_otp")?.args).toEqual({ patient: "PAT-1", consent_name: "CONS-1" });
    expect(s.last("verify_dl_otp")?.args).toEqual({ patient: "PAT-1", txn_id: "D1", otp: "123456" });
  });

  it("checks a different mobile before any call", async () => {
    const s = server();
    render(<App />);
    const u = await toMethod();
    await u.click(screen.getByRole("radio", { name: /Driving licence/ }));
    await u.click(screen.getByRole("button", { name: "Continue" }));
    await u.click(await screen.findByRole("button", { name: "Use a different mobile" }));
    await u.type(box("Mobile number"), "98765");
    await u.click(screen.getByRole("button", { name: "Send OTP" }));
    expect(await screen.findByText(/exactly 10 digits \(you entered 5\)/)).toBeInTheDocument();
    expect(s.count("request_document_otp")).toBe(0);
    await u.clear(box("Mobile number"));
    await u.type(box("Mobile number"), "98765 55555");
    await u.click(screen.getByRole("button", { name: "Send OTP" }));
    await heading("Verify mobile OTP");
    expect(s.last("request_document_otp")?.args).toEqual({ patient: "PAT-1", consent_name: "CONS-1", mobile: "9876555555" });
  });

  it("starts the details from the patient record and refuses incomplete ones with no call", async () => {
    const { u, s } = await toDetails();
    expect(box("First name")).toHaveValue("Asha");
    expect(box("Middle name")).toHaveValue("Devi");
    expect(box("Last name")).toHaveValue("Verma");
    expect(screen.getByLabelText("Date of birth")).toHaveValue("1988-11-05");
    expect(screen.getByLabelText("Gender")).toHaveValue("F");
    await u.click(screen.getByRole("button", { name: "Send for approval" }));
    expect(await screen.findByText(/Enter the licence number as printed/)).toBeInTheDocument();
    expect(screen.getByText("Add a photograph of the front of the licence.")).toBeInTheDocument();
    expect(screen.getByText("Add a photograph of the back of the licence.")).toBeInTheDocument();
    expect(s.count("submit_for_approval")).toBe(0);
  });

  it("holds the documents for approval, says nothing has gone to ABDM, and never calls it an ABHA", async () => {
    const { u, s } = await toDetails();
    await u.type(box("Licence number"), "MH1320140019054");
    await u.upload(screen.getByLabelText("Photograph of the front"), new File(["x"], "front.jpg", { type: "image/jpeg" }));
    await u.upload(screen.getByLabelText("Photograph of the back"), new File(["y"], "back.jpg", { type: "image/jpeg" }));
    await u.click(screen.getByRole("button", { name: "Send for approval" }));
    await heading("Approval and enrolment number");
    const sent = s.last("submit_for_approval")!.args;
    expect(sent.txn_id).toBe("D2");
    expect(JSON.parse(String(sent.details))).toEqual({ documentId: "MH1320140019054", firstName: "Asha", middleName: "Devi", lastName: "Verma", dob: "1988-11-05", gender: "F" });
    expect([sent.front_photo, sent.back_photo]).toEqual(["FRONTB64", "BACKB64"]);
    expect(await screen.findByText(/Waiting for a second person/)).toBeInTheDocument();
    expect(screen.getByText(/Nothing has gone to ABDM yet/)).toBeInTheDocument();
    expect(screen.queryByText(/ABHA created/)).toBeNull();
    expect(localStorage.length + sessionStorage.length).toBe(0);
  });

  it("shows the enrolment number as not-yet-an-ABHA once ABDM has answered", async () => {
    let n = 0;
    const { u } = await toDetails({ get_status: () => (n++ === 0 ? { status: "Awaiting approval" } : { status: "Submitted", enrolment_number: "91-6087-5423-XXXX", enrolment_state: "VERIFIED" }) });
    await u.type(box("Licence number"), "MH1320140019054");
    await u.upload(screen.getByLabelText("Photograph of the front"), new File(["x"], "front.jpg", { type: "image/jpeg" }));
    await u.upload(screen.getByLabelText("Photograph of the back"), new File(["y"], "back.jpg", { type: "image/jpeg" }));
    await u.click(screen.getByRole("button", { name: "Send for approval" }));
    await screen.findByText(/Waiting for a second person/);
    await u.click(screen.getByRole("button", { name: "Check again" }));
    expect(await screen.findByText(/91-6087-5423-XXXX/)).toBeInTheDocument();
    expect(screen.getByText(/This is not an ABHA yet/)).toBeInTheDocument();
  });

  it("shows a rejection with its reason and lets the collector start again", async () => {
    const { u } = await toDetails({ get_status: () => ({ status: "Rejected", decision_note: "photo does not match" }) });
    await u.type(box("Licence number"), "MH1320140019054");
    await u.upload(screen.getByLabelText("Photograph of the front"), new File(["x"], "front.jpg", { type: "image/jpeg" }));
    await u.upload(screen.getByLabelText("Photograph of the back"), new File(["y"], "back.jpg", { type: "image/jpeg" }));
    await u.click(screen.getByRole("button", { name: "Send for approval" }));
    expect(await screen.findByText(/photo does not match/)).toBeInTheDocument();
    await u.click(screen.getByRole("button", { name: "Start again" }));
    await heading("Patient consent");
  });
});

describe("Aadhaar fingerprint", () => {
  const ON = { get_routes: () => ({ ...ROUTES, biometric: true }) };
  const ok: RdClient = { capture: vi.fn(async () => "<PidData>PID</PidData>") };

  async function toCapture(rd: RdClient, extra: Record<string, Handler> = {}) {
    const s = server({ ...ON, ...extra });
    render(<App rd={rd} />);
    const u = await toMethod();
    await u.click(await screen.findByRole("radio", { name: /Aadhaar fingerprint/ }));
    await u.click(screen.getByRole("button", { name: "Continue" }));
    await heading("Aadhaar number");
    await u.type(box("Aadhaar number"), "1234 5678 9012");
    await u.click(screen.getByRole("button", { name: "Continue" }));
    await heading("Scan fingerprint");
    return { u, s };
  }

  it("takes the Aadhaar without requesting an OTP, scans, and sends the scan with the consent", async () => {
    const { u, s } = await toCapture(ok);
    expect(s.count("request_enrolment_otp")).toBe(0);
    await u.click(screen.getByRole("button", { name: "Scan fingerprint" }));
    await heading("Choose ABHA address"); // ABDM linked the session, so no mobile step
    expect(s.last("enrol_by_biometric")?.args).toEqual({ patient: "PAT-1", aadhaar: "123456789012", pid: "<PidData>PID</PidData>", consent_name: "CONS-1" });
    expect(localStorage.length + sessionStorage.length).toBe(0); // the PID is not kept anywhere
  });

  it("shows why a scan failed and lets the person scan again", async () => {
    const rd: RdClient = { capture: vi.fn().mockRejectedValueOnce(new RdServiceError("The device reported: Finger not placed")).mockResolvedValue("<PidData/>") };
    const { u, s } = await toCapture(rd);
    await u.click(screen.getByRole("button", { name: "Scan fingerprint" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Finger not placed");
    expect(s.count("enrol_by_biometric")).toBe(0);
    await u.click(screen.getByRole("button", { name: "Scan again" }));
    await heading("Choose ABHA address");
  });

  it("shows ABDM's own reason when the scan is refused", async () => {
    const { u } = await toCapture(ok, { enrol_by_biometric: () => { throw new Fail("ABDM-1094: access to this feature is refused"); } });
    await u.click(screen.getByRole("button", { name: "Scan fingerprint" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("ABDM-1094");
    expect(screen.getByRole("button", { name: "Scan again" })).toBeEnabled();
  });
});
