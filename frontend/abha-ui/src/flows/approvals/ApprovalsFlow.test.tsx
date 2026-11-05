import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../../app/App";
import { bootAs, Fail, fakeServer, type Handler } from "../../test/fakeServer";

const PACKET = {
  name: "ABHA-DOC-00001",
  patient: "PAT-1",
  patient_name: "Asha Verma",
  collected_by: "nurse@example.com",
  details: { documentId: "MH1320140019054", firstName: "Anand", lastName: "Sunchu", dob: "1996-07-15", gender: "M" as const, district: "Pune" },
  front_photo: "RlJPTlQ=",
  back_photo: "QkFDSw==",
};

function server(extra: Record<string, Handler> = {}, canApprove = true) {
  return fakeServer({
    get_routes: () => ({ aadhaar_otp: true, driving_licence: true, biometric: false, can_approve: canApprove }),
    list_pending: () => [{ name: "ABHA-DOC-00001", patient: "PAT-1", patient_name: "Asha Verma", requested_by: "nurse@example.com", requested_at: "2026-10-30 12:00:00" }],
    get_for_review: () => PACKET,
    decide: (a) => (a.decision === "approve" ? { name: "ABHA-DOC-00001", status: "Submitted", enrolment_number: "91-6087-5423-XXXX" } : { name: "ABHA-DOC-00001", status: "Rejected" }),
    ...extra,
  });
}

beforeEach(() => {
  window.location.hash = "#/approvals";
  bootAs(null); // no patient chosen: approvals do not need one
});
afterEach(() => vi.restoreAllMocks());

describe("approvals", () => {
  it("works without a patient chosen, and lists what is waiting", async () => {
    server();
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Waiting for approval" })).toBeInTheDocument();
    expect(screen.getByText("Asha Verma")).toBeInTheDocument();
    expect(screen.getByText(/collected by nurse@example.com/)).toBeInTheDocument();
    expect(screen.queryByText("Select a patient to begin")).toBeNull();
  });

  it("shows the details and both photographs, and will not approve until the checks are confirmed", async () => {
    const s = server();
    render(<App />);
    const u = userEvent.setup();
    await u.click(await screen.findByRole("button", { name: "Review" }));
    expect(await screen.findByRole("heading", { name: "Check Asha Verma" })).toBeInTheDocument();
    expect(screen.getByText("MH1320140019054")).toBeInTheDocument();
    expect(screen.getByText("Male")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Front of the licence" })).toHaveAttribute("src", "data:image/jpeg;base64,RlJPTlQ=");
    expect(screen.getByRole("img", { name: "Back of the licence" })).toBeInTheDocument();
    const approve = screen.getByRole("button", { name: "Approve and send to ABDM" });
    expect(approve).toBeDisabled();
    await u.click(screen.getByRole("checkbox"));
    expect(approve).toBeEnabled();
    await u.click(approve);
    expect(await screen.findByText(/Sent to ABDM. Enrolment number 91-6087-5423-XXXX. It is not an ABHA yet./)).toBeInTheDocument();
    expect(s.last("decide")?.args).toEqual({ name: "ABHA-DOC-00001", decision: "approve", note: "" });
  });

  it("needs a reason to reject, and says nothing went to ABDM", async () => {
    const s = server();
    render(<App />);
    const u = userEvent.setup();
    await u.click(await screen.findByRole("button", { name: "Review" }));
    const reject = await screen.findByRole("button", { name: "Reject" });
    expect(reject).toBeDisabled();
    await u.type(screen.getByLabelText("Reason, needed to reject"), "photo does not match");
    await u.click(reject);
    expect(await screen.findByText(/Rejected. Nothing was sent to ABDM/)).toBeInTheDocument();
    expect(s.last("decide")?.args).toEqual({ name: "ABHA-DOC-00001", decision: "reject", note: "photo does not match" });
  });

  it("shows the server's refusal when the collector tries to approve their own documents", async () => {
    server({ get_for_review: () => { throw new Fail("A second person must approve: the person who collected the documents cannot decide."); } });
    render(<App />);
    await userEvent.setup().click(await screen.findByRole("button", { name: "Review" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("A second person must approve");
  });

  it("says why when the user may not see approvals, and says when nothing is waiting", async () => {
    server({ list_pending: () => { throw new Fail("Only a Healthcare Administrator can approve or reject a document enrolment."); } }, false);
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Only a Healthcare Administrator");
  });

  it("lists nothing politely", async () => {
    server({ list_pending: () => [] });
    render(<App />);
    expect(await screen.findByText("Nothing is waiting.")).toBeInTheDocument();
  });

  it("shows Approvals in the menu only to someone who can approve", async () => {
    window.location.hash = "#/create";
    server({}, false);
    const { unmount } = render(<App />);
    await screen.findByText("Select a patient to begin");
    expect(screen.queryByRole("link", { name: "Approvals" })).toBeNull();
    unmount();
    server({}, true);
    render(<App />);
    expect(await screen.findByRole("link", { name: "Approvals" })).toBeInTheDocument();
  });
});
