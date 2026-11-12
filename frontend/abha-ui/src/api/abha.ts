import { call } from "./client";
import type { BiometricResult, ConsentRecord, DocumentEnrolment, LicenceDetails, PendingApproval, ReviewPacket, Routes, ConsentText, EnrolResult, LoginHint, LoginProfile, OtpRequested, OtpSystem, PatientContext, PatientRow, Png, ProfileSummary } from "./types";

// The Frappe 16 branch's ABDM API (healthcare/regional/india/abdm/api) plus the page-only calls in api/ui.py.
const E = "healthcare.regional.india.abdm.api.enrol.";
const P = "healthcare.regional.india.abdm.api.profile.";
const U = "healthcare.regional.india.abdm.api.ui.";
const R = "healthcare.regional.india.abdm.api.enrol_routes.";
const CONSENT = "healthcare.regional.india.abdm.api.consent.";

// ── what the desk already knows ─────────────────────────────────────────────────────────────────────────
export const getContext = (patient: string) => call<PatientContext>(U + "get_context", { patient });

// ── consent, then create (Aadhaar OTP) ──────────────────────────────────────────────────────────────────
export const getConsentText = () => call<ConsentText>(U + "get_consent_text");
export const recordConsent = (patient: string) =>
  call<ConsentRecord>(CONSENT + "record_consent", { patient, consent_type: "ABHA Creation", source: "Registration Desk" });

/** The OTP is only requested with a recorded agreement: the server refuses otherwise. */
export const requestEnrolmentOtp = (patient: string, aadhaar: string, consent_name: string) =>
  call<OtpRequested>(U + "request_enrolment_otp", { patient, aadhaar, consent_name });
export const resendEnrolmentOtp = (patient: string, txn_id: string) => call<{ message?: string }>(E + "resend_aadhaar_otp", { patient, txn_id });

/** Enrols with the OTP. The mobile comes from the Patient record, so the person is not asked for it again. */
export const completeEnrolment = (patient: string, txn_id: string, otp: string, mobile?: string) =>
  call<EnrolResult>(U + "complete_enrolment", { patient, txn_id, otp, ...(mobile ? { mobile } : {}) });

// Only when ABDM did not link the mobile by itself.
export const sendMobileOtp = (patient: string, txn_id: string, mobile?: string) =>
  call<OtpRequested>(E + "send_mobile_otp", { patient, txn_id, ...(mobile ? { mobile } : {}) });
export const verifyMobileOtp = (patient: string, txn_id: string, otp: string) => call<{ message?: string }>(E + "verify_mobile_otp", { patient, txn_id, otp });

export const getAddressSuggestions = async (patient: string): Promise<string[]> =>
  (await call<{ suggestions?: string[] }>(E + "get_abha_suggestions", { patient })).suggestions ?? [];
export const setAddress = (patient: string, abha_address: string) => call<{ abha_address?: string }>(E + "set_abha_address", { patient, abha_address });

// ── verify an existing ABHA (the session token stays on the server) ─────────────────────────────────────
// For an ABHA number ABDM sends the OTP to the mobile linked to that ABHA; for an Aadhaar, to the Aadhaar-linked mobile.
export const requestLoginOtp = (patient: string, login_id: string, login_hint: LoginHint) => call<OtpRequested>(P + "request_abha_login_otp", { patient, login_id, login_hint });
export const verifyLoginOtp = (patient: string, txn_id: string, otp: string, login_hint: LoginHint) => call<LoginProfile>(P + "verify_abha_login_otp", { patient, txn_id, otp, login_hint });
export const requestAddressOtp = (patient: string, abha_address: string, otp_system: OtpSystem) => call<OtpRequested>(P + "request_abha_address_otp", { patient, abha_address, otp_system });
export const verifyAddressOtp = (patient: string, txn_id: string, otp: string, otp_system: OtpSystem) => call<LoginProfile>(P + "verify_abha_address_otp", { patient, txn_id, otp, otp_system });

// ── the other ways to create an ABHA ────────────────────────────────────────────────────────────────────
export const getRoutes = () => call<Routes>(R + "get_routes");

// Driving licence: the mobile is verified first, the documents are held for a second person to approve, and the answer
// is an enrolment number (not an ABHA).
export const requestDocumentOtp = (patient: string, consent_name: string, mobile?: string) =>
  call<OtpRequested>(R + "request_document_otp", { patient, consent_name, ...(mobile ? { mobile } : {}) });
export const verifyDocumentOtp = (patient: string, txn_id: string, otp: string) => call<{ txnId?: string }>(E + "verify_dl_otp", { patient, txn_id, otp });
export const submitForApproval = (patient: string, txn_id: string, details: LicenceDetails, front_photo: string, back_photo: string) =>
  call<{ name: string; status: string }>(R + "submit_for_approval", { patient, txn_id, details: JSON.stringify(details), front_photo, back_photo });
export const getDocumentStatus = (patient: string) => call<DocumentEnrolment>(R + "get_status", { patient });
export const listPending = () => call<PendingApproval[]>(R + "list_pending");
export const getForReview = (name: string) => call<ReviewPacket>(R + "get_for_review", { name });
export const decide = (name: string, decision: "approve" | "reject", note = "") =>
  call<{ name: string; status: string; enrolment_number?: string }>(R + "decide", { name, decision, note });

// Aadhaar biometric (only when the site enables it). The PID block is passed through to ABDM, never stored.
export const enrolByBiometric = (patient: string, aadhaar: string, pid: string, consent_name: string, mobile?: string) =>
  call<BiometricResult>(R + "enrol_by_biometric", { patient, aadhaar, pid, consent_name, ...(mobile ? { mobile } : {}) });

// ── profile, QR, card ───────────────────────────────────────────────────────────────────────────────────
export const getProfile = (patient: string) => call<ProfileSummary>(P + "get_abha_profile", { patient });
export const getQrCode = async (patient: string): Promise<Png> => ({
  file_name: "abha-qr.png",
  content_type: "image/png",
  content: (await call<{ qr_code: string }>(P + "get_abha_qr_code", { patient })).qr_code,
});
export const getCard = async (patient: string): Promise<Png> => ({
  file_name: "abha-card.png",
  content_type: "image/png",
  content: (await call<{ card_b64: string }>(P + "download_abha_card", { patient })).card_b64,
});

// ── patients (Frappe's own list, so the user's permissions apply) ───────────────────────────────────────
export const searchPatients = (text: string) =>
  call<PatientRow[]>("frappe.client.get_list", {
    doctype: "Patient",
    fields: ["name", "patient_name", "mobile", "abha_number", "abha_address", "sex", "dob"],
    or_filters: [
      ["patient_name", "like", `%${text}%`],
      ["name", "like", `%${text}%`],
      ["mobile", "like", `%${text}%`],
    ],
    limit_page_length: 8,
    order_by: "modified desc",
  });
