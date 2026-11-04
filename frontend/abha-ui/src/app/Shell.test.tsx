import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { bootAs, fakeServer, NO_ABHA } from "../test/fakeServer";
import { App } from "./App";
import { parseHash } from "./router";

const rows = [
  { name: "PAT-1", patient_name: "Asha Verma", mobile: "x", abha_number: null },
  { name: "PAT-2", patient_name: "Asha Menon", mobile: null, abha_number: "y" },
];

beforeEach(() => {
  window.location.hash = "";
  bootAs();
});
afterEach(() => vi.restoreAllMocks());

describe("router", () => {
  it("falls back to Create for unknown hashes", () => {
    expect(parseHash("#/nonsense")).toBe("create");
    expect(parseHash("")).toBe("create");
    expect(parseHash("#/verify")).toBe("verify");
    expect(parseHash("#/profile?x=1")).toBe("profile");
  });
});

describe("shell", () => {
  it("asks for a patient first and marks the current task", () => {
    render(<App />);
    expect(screen.getByText("Select a patient to begin")).toBeInTheDocument();
    const nav = screen.getByRole("navigation", { name: "ABHA tasks" });
    expect(within(nav).getByRole("link", { name: "Create ABHA" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("navigation", { name: "Breadcrumb" })).toHaveTextContent("Patient registration");
  });

  it("starts with the patient from the boot data and lets the user clear it", async () => {
    bootAs({ name: "PAT-9", patient_name: "Boot Patient" });
    fakeServer({ get_context: () => NO_ABHA, get_consent_text: () => ({ available: true, title: "T", text: "t", code: "c", version: "1.0", sha256: "x" }) });
    render(<App />);
    expect(screen.getByTestId("patient-chip")).toHaveTextContent("Boot Patient");
    expect(await screen.findByRole("list", { name: "Create ABHA steps" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Clear patient/ }));
    expect(screen.getByText("Select a patient to begin")).toBeInTheDocument();
  });

  it("searches after two characters, picks with the keyboard, and shows the step rail", async () => {
    const server = fakeServer({ get_list: () => rows, get_context: () => NO_ABHA, get_consent_text: () => ({ available: true, title: "Terms and Conditions", text: "t", code: "c", version: "1.0", sha256: "x" }) });
    render(<App />);
    const box = screen.getByRole("combobox", { name: "Find patient" });
    await userEvent.type(box, "a");
    expect(server.count("get_list")).toBe(0);
    await userEvent.type(box, "sh");
    const list = await screen.findByRole("listbox", { name: "Matching patients" });
    await waitFor(() => expect(within(list).getAllByRole("option")).toHaveLength(2));
    await userEvent.keyboard("{ArrowDown}{Enter}");
    expect(screen.getByTestId("patient-chip")).toHaveTextContent("Asha Menon");
    expect(await screen.findByRole("list", { name: "Create ABHA steps" })).toBeInTheDocument();
  });

  it("says so when nothing matches and when the search fails", async () => {
    fakeServer({ get_list: () => [] });
    render(<App />);
    await userEvent.type(screen.getByRole("combobox", { name: "Find patient" }), "zzz");
    expect(await screen.findByText("No patient found.")).toBeInTheDocument();

    vi.restoreAllMocks();
    vi.spyOn(window, "fetch").mockRejectedValue(new TypeError("offline"));
    await userEvent.type(screen.getByRole("combobox", { name: "Find patient" }), "z");
    expect(await screen.findByRole("alert")).toHaveTextContent(/Could not reach the server/);
  });

  it("marks the first step as current for a fresh patient", async () => {
    bootAs({ name: "P", patient_name: "P" });
    fakeServer({ get_context: () => NO_ABHA, get_consent_text: () => ({ available: true, title: "T", text: "t", code: "c", version: "1.0", sha256: "x" }) });
    render(<App />);
    const rail = await screen.findByRole("list", { name: "Create ABHA steps" });
    expect(within(rail).queryByText("(not needed)")).toBeNull();
    expect(within(rail).getByText("Patient consent").closest("li")).toHaveAttribute("aria-current", "step");
  });
});
