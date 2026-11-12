import type { StepDef } from "../domain/stepContract";
import type { CreateRoute, Known } from "../domain/known";

/**
 * The create journey, as data. The step rail renders it; the contract test walks it and fails if any step asks for
 * something already known (the M1 design rule "never ask a patient the same thing twice").
 */
const CONSENT: StepDef = { id: "consent", title: "Patient consent", collects: ["consent"] };
const METHOD: StepDef = { id: "method", title: "How to create", collects: ["createRoute"] };
// Reached from a lookup that found no ABHA: the Aadhaar number is already known and is not asked again.
const AADHAAR: StepDef = { id: "aadhaar", title: "Aadhaar number", collects: ["aadhaar"], skipWhen: (k: Known) => k.aadhaar !== undefined };
// The number on the patient record goes with the OTP, so ABDM usually links it by itself and this step is not needed.
const MOBILE: StepDef = { id: "mobile", title: "Confirm mobile", collects: ["communicationMobile"], learns: ["txnId"], skipWhen: (k: Known) => k.mobileLinked === true };
const ADDRESS: StepDef = { id: "address", title: "Choose ABHA address", collects: ["abhaAddress"] };
const DONE: StepDef = { id: "done", title: "ABHA created", collects: [], learns: ["profile"] };

/**
 * The create journeys, as data. The step rail renders them; the contract test walks each and fails if any step asks
 * for something already known (the M1 design rule "never ask a patient the same thing twice").
 */
export function createSteps(route: CreateRoute = "aadhaar-otp"): StepDef[] {
  if (route === "driving-licence") {
    return [
      CONSENT,
      METHOD,
      { id: "dl-mobile", title: "Mobile number", collects: ["communicationMobile"] },
      { id: "dl-otp", title: "Verify mobile OTP", collects: [], learns: ["txnId"] },
      { id: "dl-details", title: "Licence details and photos", collects: ["licenceDetails"] },
      { id: "dl-result", title: "Approval and enrolment number", collects: [] },
    ];
  }
  if (route === "biometric") {
    return [CONSENT, METHOD, AADHAAR, { id: "capture", title: "Scan fingerprint", collects: [], learns: ["txnId", "abhaNumber", "mobileLinked"] }, MOBILE, ADDRESS, DONE];
  }
  return [CONSENT, METHOD, AADHAAR, { id: "otp", title: "Verify Aadhaar OTP", collects: [], learns: ["txnId", "abhaNumber", "mobileLinked"] }, MOBILE, ADDRESS, DONE];
}

export const CREATE_STEPS = createSteps("aadhaar-otp");

export type IdentifierKind = NonNullable<Known["identifierKind"]>;

/**
 * Verify an existing ABHA: what identifies the patient, the OTP method only where there is a choice (an ABHA address),
 * then the OTP. When the identifier is already on the patient record it is not asked for (`valueKnown`).
 */
export function verifySteps(kind: IdentifierKind, valueKnown = false): StepDef[] {
  const fact = { aadhaar: "aadhaar", "abha-number": "abhaNumber", "abha-address": "abhaAddress" }[kind] as "aadhaar" | "abhaNumber" | "abhaAddress";
  return [
    { id: "identifier", title: "Identify the patient", collects: valueKnown ? ["identifierKind"] : ["identifierKind", fact] },
    { id: "method", title: "Choose OTP method", collects: ["otpMethod"], skipWhen: () => kind !== "abha-address" },
    { id: "otp", title: "Verify OTP", collects: [], learns: ["txnId"] },
    { id: "done", title: "ABHA verified", collects: [], learns: ["profile"] },
  ];
}
