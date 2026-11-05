// Shapes of what the existing whitelisted methods return. Tokens are stripped on the server (S3), so none appear here.

export interface Boot {
  csrf_token: string;
  user: { name: string; full_name: string; roles: string[] };
  patient: { name: string; patient_name: string } | null;
  site: string;
}

export interface PatientRow {
  name: string;
  patient_name: string;
  mobile?: string | null;
  abha_number?: string | null;
  abha_address?: string | null;
  sex?: string | null;
  dob?: string | null;
}

export interface OtpRequested {
  txnId?: string;
  message?: string;
}

/** enrol.enrol_by_aadhaar (via ui.complete_enrolment): the ABHA is created and the Patient updated by the server. */
export interface EnrolResult {
  message?: string;
  abha_number: string;
  abha_address?: string;
  status?: string;
  /** True when ABDM linked the mobile by itself (it matched the Aadhaar-linked one): no mobile OTP is needed. */
  mobile_linked: boolean;
  txnId?: string;
}

/** profile.get_abha_profile: what the server chooses to show. Mobile and email arrive masked. */
export interface ProfileSummary {
  abha_number: string;
  abha_address: string;
  name: string;
  mobile: string;
  email: string;
  gender: string;
  dob: string;
  status: string;
  /** A Patient file URL, not the picture itself. */
  photo: string | null;
}

export interface Png {
  file_name: string;
  content_type: "image/png";
  content: string; // base64
}

/** ui_api.get_context: what the desk already knows. The mobile number itself is never sent, only whether one exists. */
export interface PatientContext {
  patient: { name: string; patient_name: string; sex: string | null; dob: string | null; has_mobile: boolean };
  abha: {
    linked: boolean;
    abha_number: string | null;
    abha_number_masked: string | null;
    abha_address: string | null;
    status: string | null;
    verified_at: string | null;
  };
}



export interface ConsentText {
  /** False when the site cannot record consent (frappe_abdm not installed): the page says so up front. */
  available: boolean;
  title: string;
  text: string;
  code: string;
  version: string;
  sha256: string;
}

export interface ConsentRecord {
  consent_name: string;
  consent_version: string;
  message?: string;
}

/** What verify_abha_login_otp / verify_abha_address_otp return: the account ABDM named, normalised by the server. */
export interface LoginProfile {
  abha_number: string;
  abha_address: string;
  name: string;
  gender: string;
  mobile: string;
  dob: string;
}

export type OtpSystem = "abdm" | "aadhaar";
export type LoginHint = "aadhaar" | "abha-number";

/** enrol_routes.get_routes: which ways to create an ABHA this site offers, and whether this user may approve. */
export interface Routes {
  aadhaar_otp: boolean;
  driving_licence: boolean;
  biometric: boolean;
  can_approve: boolean;
}

export interface LicenceDetails {
  documentId: string;
  firstName: string;
  middleName?: string;
  lastName: string;
  dob: string; // YYYY-MM-DD
  gender: "M" | "F" | "O";
  address?: string;
  state?: string;
  district?: string;
  pinCode?: string;
}

export type DocumentStatus = "Awaiting approval" | "Approved" | "Rejected" | "Submitted" | "Failed";

/** The latest document enrolment for a patient (no held details). Empty before one exists. */
export interface DocumentEnrolment {
  name?: string;
  status?: DocumentStatus;
  requested_by?: string;
  decided_by?: string;
  decision_note?: string;
  enrolment_number?: string;
  enrolment_state?: string;
  result_message?: string;
}

export interface PendingApproval {
  name: string;
  patient: string;
  patient_name: string;
  requested_by: string;
  requested_at: string;
}

export interface ReviewPacket {
  name: string;
  patient: string;
  patient_name: string;
  collected_by: string;
  details: LicenceDetails;
  front_photo: string; // base64 JPEG
  back_photo: string;
}

export interface BiometricResult {
  abha_number: string;
  abha_address?: string;
  status?: string;
  /** True when ABDM returned a session token, so no mobile OTP is needed. */
  mobile_linked: boolean;
  txnId?: string;
}
