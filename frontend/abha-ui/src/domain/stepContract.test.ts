import { describe, expect, it } from "vitest";
import { findRepeatedQuestions, type StepDef } from "./stepContract";

describe("findRepeatedQuestions", () => {
  it("passes a journey that asks each thing once", () => {
    const steps: StepDef[] = [
      { id: "consent", title: "Consent", collects: ["consent"] },
      { id: "aadhaar", title: "Aadhaar", collects: ["aadhaar"] },
      { id: "otp", title: "OTP", collects: [], learns: ["txnId"] },
    ];
    expect(findRepeatedQuestions(steps)).toEqual([]);
  });

  it("flags a step that asks again for something an earlier step collected", () => {
    const steps: StepDef[] = [
      { id: "a", title: "A", collects: ["aadhaar"] },
      { id: "b", title: "B", collects: ["aadhaar"] },
    ];
    expect(findRepeatedQuestions(steps)).toEqual([{ step: "b", fact: "aadhaar", reason: "asked-again" }]);
  });

  it("flags a step that asks for something the system already learned from ABDM", () => {
    const steps: StepDef[] = [
      { id: "verify", title: "Verify", collects: ["abhaNumber"], learns: ["profile"] },
      { id: "confirm", title: "Confirm", collects: ["profile"] },
    ];
    expect(findRepeatedQuestions(steps)).toEqual([{ step: "confirm", fact: "profile", reason: "asked-again" }]);
  });

  it("flags a step that asks for a fact it is forbidden to ask", () => {
    const steps: StepDef[] = [{ id: "x", title: "X", collects: ["aadhaar"], forbidden: ["aadhaar"] }];
    expect(findRepeatedQuestions(steps)).toEqual([{ step: "x", fact: "aadhaar", reason: "forbidden" }]);
  });

  it("treats a skipped step as not asking", () => {
    const steps: StepDef[] = [
      { id: "a", title: "A", collects: ["communicationMobile"] },
      { id: "b", title: "B", collects: ["communicationMobile"], skipWhen: (k) => k.communicationMobile !== undefined },
    ];
    expect(findRepeatedQuestions(steps)).toEqual([]);
  });

  it("starts from what is already known, so a seeded fact cannot be asked", () => {
    const steps: StepDef[] = [{ id: "a", title: "A", collects: ["aadhaar"] }];
    expect(findRepeatedQuestions(steps, ["aadhaar"])).toEqual([{ step: "a", fact: "aadhaar", reason: "asked-again" }]);
  });
});

import { CREATE_STEPS, createSteps, verifySteps } from "../flows/steps";

describe("the real create journey never asks twice", () => {
  it("create ABHA", () => {
    expect(findRepeatedQuestions(CREATE_STEPS)).toEqual([]);
  });

  it.each(["aadhaar-otp", "driving-licence", "biometric"] as const)("create by %s never asks twice, and consent comes first", (route) => {
    const steps = createSteps(route);
    expect(findRepeatedQuestions(steps)).toEqual([]);
    expect(steps[0]!.id).toBe("consent");
    expect(steps[1]!.id).toBe("method");
  });

  it("create ABHA after a lookup found nothing: the Aadhaar already typed is not asked again", () => {
    expect(findRepeatedQuestions(CREATE_STEPS, ["aadhaar"])).toEqual([]);
  });

  it("consent is collected before the Aadhaar number", () => {
    const ids = CREATE_STEPS.map((s) => s.id);
    expect(ids.indexOf("consent")).toBe(0);
    expect(ids.indexOf("consent")).toBeLessThan(ids.indexOf("aadhaar"));
  });

  it("the mobile step is skipped when ABDM linked the mobile by itself", () => {
    const mobile = CREATE_STEPS.find((s) => s.id === "mobile")!;
    expect(mobile.skipWhen!({ mobileLinked: true })).toBe(true);
    expect(mobile.skipWhen!({ mobileLinked: false })).toBe(false);
  });

  it.each(["aadhaar", "abha-number", "abha-address"] as const)("verify by %s", (kind) => {
    expect(findRepeatedQuestions(verifySteps(kind))).toEqual([]);
  });

  it("verify with the identifier already on the record never asks for it", () => {
    expect(findRepeatedQuestions(verifySteps("abha-number", true), ["abhaNumber"])).toEqual([]);
    expect(findRepeatedQuestions(verifySteps("abha-number", false), ["abhaNumber"])).toEqual([{ step: "identifier", fact: "abhaNumber", reason: "asked-again" }]);
  });

  it("only an ABHA address asks which OTP method", () => {
    const asks = (k: "aadhaar" | "abha-number" | "abha-address") => !verifySteps(k).find((s) => s.id === "method")!.skipWhen!({});
    expect(["aadhaar", "abha-number", "abha-address"].filter((k) => asks(k as "aadhaar"))).toEqual(["abha-address"]);
  });
});
