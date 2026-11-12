import type { LicenceDetails, ProfileSummary } from "../api/types";

export type CreateRoute = "aadhaar-otp" | "driving-licence" | "biometric";

/** One store of everything known about the patient in front of the desk. Screens read from it; they never re-ask. */
export type FactKey =
  | "patient"
  | "consent"
  | "aadhaar"
  | "mobile"
  | "communicationMobile"
  | "abhaNumber"
  | "abhaAddress"
  | "email"
  | "identifierKind"
  | "otpMethod"
  | "txnId"
  | "updateKind"
  | "mobileLinked"
  | "createRoute"
  | "licenceDetails"
  | "profile";

export interface PatientRef {
  name: string;
  patient_name: string;
}

export interface Known {
  patient?: PatientRef;
  consent?: { id: string; at: string };
  aadhaar?: string;
  mobile?: string;
  communicationMobile?: string;
  abhaNumber?: string;
  abhaAddress?: string;
  email?: string;
  identifierKind?: "aadhaar" | "abha-number" | "abha-address";
  otpMethod?: "aadhaar" | "abdm";
  txnId?: string;
  updateKind?: "mobile" | "email" | "re-kyc" | "photo";
  mobileLinked?: boolean;
  createRoute?: CreateRoute;
  licenceDetails?: LicenceDetails;
  profile?: ProfileSummary;
}

/** Values that must not outlive the step that needs them. */
export const SENSITIVE: FactKey[] = ["aadhaar", "mobile", "communicationMobile", "email", "txnId", "licenceDetails"];

export type Action =
  | { type: "patient"; patient: PatientRef | undefined }
  | { type: "learn"; patch: Partial<Known> }
  | { type: "forget"; keys: FactKey[] }
  | { type: "forgetSensitive" }
  | { type: "reset"; keepPatient?: boolean };

export function knownReducer(state: Known, action: Action): Known {
  switch (action.type) {
    case "patient":
      // A different patient starts from nothing: nothing learned about one person may leak onto another.
      return action.patient ? { patient: action.patient } : {};
    case "learn":
      return { ...state, ...action.patch };
    case "forget": {
      const next = { ...state };
      for (const k of action.keys) delete next[k];
      return next;
    }
    case "forgetSensitive": {
      const next = { ...state };
      for (const k of SENSITIVE) delete next[k];
      return next;
    }
    case "reset":
      return action.keepPatient && state.patient ? { patient: state.patient } : {};
  }
}
