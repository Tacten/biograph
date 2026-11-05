import type { Boot, PatientRow } from "../api/types";

/** Dev-only harness: lets `npm run dev` and the screenshots run without a Frappe site. Never imported in production. */
/** `?patient=PAT-0001` starts with that patient chosen, like the Desk's "ABHA app" menu item does. */
export const DEV_BOOT: Boot = {
  csrf_token: "dev-token",
  user: { name: "desk@example.com", full_name: "Desk Nurse", roles: ["Nursing User"] },
  patient: new URLSearchParams(window.location.search).has("patient") ? { name: "PAT-0001", patient_name: "Asha Verma" } : null,
  site: "dev",
};

const PATIENTS: PatientRow[] = [
  { name: "PAT-0001", patient_name: "Asha Verma", mobile: "on file", abha_number: null },
  { name: "PAT-0002", patient_name: "Ravi Kumar", mobile: "on file", abha_number: "present" },
  { name: "PAT-0003", patient_name: "Asha Menon", mobile: null, abha_number: null },
];

const TEXT =
  "I, hereby declare that I am voluntarily sharing my Aadhaar number and demographic information issued by UIDAI, with National Health Authority (NHA) for the sole purpose of creation of ABHA number. (Dev placeholder: the real wording comes from the server.)";
const PROFILE = { ABHANumber: "91-1111-2222-3333", name: "Asha Devi Verma", gender: "F", dayOfBirth: "5", monthOfBirth: "11", yearOfBirth: "1988", preferredAbhaAddress: "asha.verma@sbx", mobile: "XXXXXX3210", kycVerified: true, status: "ACTIVE", stateName: "Karnataka", districtName: "Bengaluru" };
// 1x1 transparent PNG
const PNG = { file_name: "dev.png", content_type: "image/png", content: "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==" };

const ROUTES: Record<string, (args: Record<string, unknown>) => unknown> = {
  get_context: (a) => ({
    patient: { name: a.patient, patient_name: "Asha Verma", sex: null, dob: null, has_mobile: true },
    abha: { linked: false, abha_number: null, abha_number_masked: null, abha_address: null, status: null, verified_at: null },
  }),
  get_consent_text: () => ({ title: "Terms and Conditions", text: TEXT, code: "abha-enrollment", version: "1.4", sha256: "dev" }),
  record_aadhaar_consent: () => ({ consent_id: "dev", version: "1.4", consented_at: new Date().toISOString() }),
  request_enrolment_otp: () => ({ txnId: "dev-txn" }),
  complete_abha_enrollment: () => ({ txnId: "dev-txn-2", ABHAProfile: PROFILE }),
  send_enrollment_mobile_otp: () => ({ txnId: "dev-txn-3" }),
  verify_enrollment_mobile_otp: () => ({ txnId: "dev-txn-4" }),
  get_abha_address_suggestions: () => ({ abhaAddressList: ["asha.verma@sbx", "asha1988@sbx", "verma.asha@sbx"] }),
  create_abha_address: (a) => ({ preferredAbhaAddress: a.abha_address }),
  get_abha_profile: () => PROFILE,
  apply_abha_to_patient: () => ({ applied: [] }),
  request_abha_login_otp: () => ({ txnId: "dev-login" }),
  verify_abha_login_otp: () => ({
    verified: true,
    select_account: true,
    txn_id: "dev-login-2",
    accounts: [
      { ABHANumber: "91-1111-2222-3333", name: "Asha Devi Verma", preferredAbhaAddress: "asha@sbx", gender: "F", dob: "1988-11-05", status: "ACTIVE" },
      { ABHANumber: "91-4444-5555-6666", name: "Ravi Verma", preferredAbhaAddress: "ravi@sbx", gender: "M", dob: "1990-01-01", status: "ACTIVE" },
    ],
  }),
  select_abha_login_account: () => ({ verified: true, profile: PROFILE }),
  search_abha_address: () => ({ authMethods: ["AADHAAR_OTP", "MOBILE_OTP"] }),
  get_abha_card: () => PNG,
  get_abha_qr_code: () => PNG,
};

/** Dev scenarios, from the page URL: ?linked=1 (patient already has an ABHA), ?expired=1 (ABHA session expired), ?fail=<method> (that call is refused). */
function scenario() {
  const q = new URLSearchParams(window.location.search);
  return { linked: q.has("linked"), expired: q.has("expired"), fail: q.get("fail") };
}

export function installMockApi(): void {
  const real = window.fetch.bind(window);
  window.fetch = async (input, init) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    const reply = (message: unknown) => new Response(JSON.stringify({ message }), { status: 200, headers: { "Content-Type": "application/json" } });
    if (url.includes("/api/method/frappe.client.get_list")) {
      const body = JSON.parse(String(init?.body ?? "{}")) as { or_filters?: [string, string, string][] };
      const needle = (body.or_filters?.[0]?.[2] ?? "").replace(/%/g, "").toLowerCase();
      return reply(PATIENTS.filter((p) => p.patient_name.toLowerCase().includes(needle) || p.name.toLowerCase().includes(needle)));
    }
    const method = decodeURIComponent(url.split("/api/method/")[1] ?? "").split(".").pop() ?? "";
    const handler = ROUTES[method];
    if (handler) {
      await new Promise((r) => setTimeout(r, 250)); // so loading states are visible
      const sc = scenario();
      const refuse = (message: string) => new Response(JSON.stringify({ exc_type: "ValidationError", _server_messages: JSON.stringify([JSON.stringify({ message })]) }), { status: 417 });
      if (sc.fail === method) return refuse("ABHA API Error (400): this is a demo refusal from ABDM, shown in ABDM's own words.");
      if (sc.expired && method === "get_abha_profile") return refuse("The login session has expired. Please request a new OTP.");
      if (sc.linked && method === "get_context") {
        const base = handler(JSON.parse(String(init?.body ?? "{}"))) as { abha: Record<string, unknown> };
        return reply({ ...base, abha: { ...base.abha, linked: true, abha_number: "91-1111-2222-3333", abha_number_masked: "91-XXXX-XXXX-3333", abha_address: "asha.verma@sbx", status: "ACTIVE" } });
      }
      return reply(handler(JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>));
    }
    return real(input, init);
  };
}
