import { describe, expect, it } from "vitest";
import { knownReducer, type Known } from "./known";

const p1 = { name: "P1", patient_name: "One" };

describe("knownReducer", () => {
  it("learns facts and forgets them", () => {
    let k: Known = knownReducer({}, { type: "patient", patient: p1 });
    k = knownReducer(k, { type: "learn", patch: { abhaNumber: "91-0000-0000-0000", aadhaar: "123412341234" } });
    expect(k.abhaNumber).toBe("91-0000-0000-0000");
    k = knownReducer(k, { type: "forget", keys: ["abhaNumber"] });
    expect(k.abhaNumber).toBeUndefined();
    expect(k.patient).toEqual(p1);
  });

  it("clears the Aadhaar, mobiles, email and txnId but keeps the rest", () => {
    let k: Known = { patient: p1, aadhaar: "1", mobile: "2", communicationMobile: "3", email: "e", txnId: "t", abhaNumber: "n", abhaAddress: "a" };
    k = knownReducer(k, { type: "forgetSensitive" });
    expect(k).toEqual({ patient: p1, abhaNumber: "n", abhaAddress: "a" });
  });

  it("starts from nothing when the patient changes, so nothing leaks onto another person", () => {
    const k = knownReducer({ patient: p1, abhaNumber: "n", aadhaar: "1" }, { type: "patient", patient: { name: "P2", patient_name: "Two" } });
    expect(k).toEqual({ patient: { name: "P2", patient_name: "Two" } });
    expect(knownReducer(k, { type: "patient", patient: undefined })).toEqual({});
  });

  it("resets, optionally keeping the patient", () => {
    const k: Known = { patient: p1, abhaNumber: "n" };
    expect(knownReducer(k, { type: "reset" })).toEqual({});
    expect(knownReducer(k, { type: "reset", keepPatient: true })).toEqual({ patient: p1 });
  });
});
