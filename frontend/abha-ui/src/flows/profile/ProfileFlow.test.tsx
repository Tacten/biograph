import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../../app/App";
import { bootAs, Fail, fakeServer, HAS_ABHA, NO_ABHA, type Handler } from "../../test/fakeServer";

const PROFILE = { abha_number: "91-1111-2222-3333", abha_address: "asha@sbx", name: "Asha Devi Verma", mobile: "3210XXXXXX", email: "", gender: "F", dob: "1988-11-05", status: "ACTIVE", photo: "/files/PAT-1-abha-photo.jpg" };

function server(extra: Record<string, Handler> = {}) {
  return fakeServer({
    get_context: () => HAS_ABHA,
    get_abha_profile: () => PROFILE,
    download_abha_card: () => ({ card_b64: btoa("PNG") }),
    get_abha_qr_code: () => ({ qr_code: btoa("PNG") }),
    ...extra,
  });
}

beforeEach(() => {
  window.location.hash = "#/profile";
  bootAs({ name: "PAT-1", patient_name: "Asha Verma" });
  URL.createObjectURL = vi.fn(() => "blob:x");
  URL.revokeObjectURL = vi.fn();
  localStorage.clear();
  sessionStorage.clear();
});
afterEach(() => vi.restoreAllMocks());

describe("profile view", () => {
  it("shows the photograph and the details the server returns, leaving out empty ones", async () => {
    server();
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Profile and photograph" })).toBeInTheDocument();
    expect(await screen.findByText("Asha Devi Verma")).toBeInTheDocument();
    expect(screen.getByText("91-1111-2222-3333")).toBeInTheDocument();
    expect(screen.getByText("Female")).toBeInTheDocument();
    expect(screen.queryByText("Email")).toBeNull(); // empty: not shown as a blank row
    expect(screen.getByRole("img", { name: "Photograph of Asha Verma" })).toHaveAttribute("src", "/files/PAT-1-abha-photo.jpg");
  });

  it("stores nothing in the browser", async () => {
    server();
    render(<App />);
    await screen.findByText("Asha Devi Verma");
    await userEvent.setup().click(screen.getByRole("button", { name: "Show ABHA card" }));
    await screen.findByRole("link", { name: "Download ABHA card" });
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
  });

  it("fetches the card and the QR code only when asked, each with a download", async () => {
    const s = server();
    render(<App />);
    const u = userEvent.setup();
    await screen.findByText("Asha Devi Verma");
    expect(s.count("download_abha_card") + s.count("get_abha_qr_code")).toBe(0);
    await u.click(screen.getByRole("button", { name: "Show QR code" }));
    expect(await screen.findByRole("link", { name: "Download QR code" })).toHaveAttribute("download", "abha-qr.png");
    expect(s.count("download_abha_card")).toBe(0);
  });

  it("explains when there is no active ABHA session, instead of showing details", async () => {
    server({ get_abha_profile: () => { throw new Fail("No active ABHA session found. Use ABDM → Verify ABHA first, then try again."); } });
    render(<App />);
    expect(await screen.findByRole("heading", { name: "The ABHA session has expired" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Verify the patient" })).toHaveAttribute("href", "#/verify");
    expect(screen.queryByText("Asha Devi Verma")).toBeNull();
  });

  it("shows other failures as they are, with a retry", async () => {
    let n = 0;
    server({ get_abha_profile: () => { if (n++ === 0) throw new Fail("ABDM is not reachable right now."); return PROFILE; } });
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("not reachable");
    await userEvent.setup().click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Asha Devi Verma")).toBeInTheDocument();
  });

  it("points a patient without an ABHA to creation, without calling ABDM", async () => {
    const s = server({ get_context: () => NO_ABHA });
    render(<App />);
    expect(await screen.findByRole("heading", { name: /has no ABHA yet/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Create an ABHA" })).toHaveAttribute("href", "#/create");
    expect(s.count("get_abha_profile")).toBe(0);
  });
});
