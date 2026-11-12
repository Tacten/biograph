import { useMemo, useState } from "react";
import { submitForApproval } from "../../api/abha";
import { ApiError } from "../../api/client";
import type { LicenceDetails, PatientContext } from "../../api/types";
import { useKnown } from "../../domain/StoreContext";
import { ErrorNote } from "../../ui/ErrorNote";
import { Field } from "../../ui/Field";
import { toJpegBase64 } from "../../ui/image";

const NAME = /^[A-Za-z][A-Za-z .'-]{0,49}$/;
const DL_NUMBER = /^[A-Za-z0-9][A-Za-z0-9 /-]{6,24}$/;

type Form = { documentId: string; firstName: string; middleName: string; lastName: string; dob: string; gender: "" | "M" | "F" | "O"; address: string; state: string; district: string; pinCode: string };

/** The patient record already has a name, date of birth and sex: offered as a starting point, to be made to match the licence. */
function prefill(p: PatientContext["patient"]): Form {
  const parts = (p.patient_name || "").trim().split(/\s+/).filter(Boolean);
  const gender = p.sex === "Male" ? "M" : p.sex === "Female" ? "F" : p.sex ? "O" : "";
  return {
    documentId: "",
    firstName: parts[0] ?? "",
    middleName: parts.length > 2 ? parts.slice(1, -1).join(" ") : "",
    lastName: parts.length > 1 ? (parts[parts.length - 1] ?? "") : "",
    dob: p.dob ?? "",
    gender,
    address: "",
    state: "",
    district: "",
    pinCode: "",
  };
}

function problems(f: Form, front: File | null, back: File | null): Partial<Record<keyof Form | "front" | "back", string>> {
  const e: Partial<Record<keyof Form | "front" | "back", string>> = {};
  if (!DL_NUMBER.test(f.documentId.trim())) e.documentId = "Enter the licence number as printed (7 to 25 letters and digits).";
  if (!NAME.test(f.firstName.trim())) e.firstName = "Enter the first name as printed on the licence.";
  if (f.middleName.trim() && !NAME.test(f.middleName.trim())) e.middleName = "The middle name has characters that are not allowed.";
  if (!NAME.test(f.lastName.trim())) e.lastName = "Enter the last name as printed on the licence.";
  if (!f.gender) e.gender = "Choose the gender as printed on the licence.";
  if (!/^\d{4}-\d{2}-\d{2}$/.test(f.dob) || Number.isNaN(Date.parse(f.dob))) e.dob = "Enter the date of birth.";
  else if (f.dob >= new Date().toISOString().slice(0, 10) || f.dob < "1900-01-01") e.dob = "The date of birth is not possible.";
  if (f.pinCode.trim() && !/^\d{6}$/.test(f.pinCode.trim())) e.pinCode = "The PIN code is 6 digits.";
  if (!front) e.front = "Add a photograph of the front of the licence.";
  if (!back) e.back = "Add a photograph of the back of the licence.";
  return e;
}

export function DlDetailsStep({ patient: ctxPatient, onNext }: { patient: PatientContext["patient"]; onNext: () => void }) {
  const { known, dispatch } = useKnown();
  const [form, setForm] = useState<Form>(() => prefill(ctxPatient));
  const [front, setFront] = useState<File | null>(null);
  const [back, setBack] = useState<File | null>(null);
  const [touched, setTouched] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const errs = useMemo(() => problems(form, front, back), [form, front, back]);
  const set = (k: keyof Form) => (e: { target: { value: string } }) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const show = (k: keyof typeof errs) => (touched ? errs[k] ?? null : null);

  async function submit() {
    setTouched(true);
    if (Object.keys(errs).length || !known.patient || !known.txnId || !front || !back) return;
    setBusy(true);
    setError("");
    try {
      const [frontB64, backB64] = await Promise.all([toJpegBase64(front), toJpegBase64(back)]);
      const details: LicenceDetails = {
        documentId: form.documentId.trim(),
        firstName: form.firstName.trim(),
        lastName: form.lastName.trim(),
        dob: form.dob,
        gender: form.gender as "M" | "F" | "O",
        ...(form.middleName.trim() && { middleName: form.middleName.trim() }),
        ...(form.address.trim() && { address: form.address.trim() }),
        ...(form.state.trim() && { state: form.state.trim() }),
        ...(form.district.trim() && { district: form.district.trim() }),
        ...(form.pinCode.trim() && { pinCode: form.pinCode.trim() }),
      };
      await submitForApproval(known.patient.name, known.txnId, details, frontB64, backB64);
      dispatch({ type: "forgetSensitive" }); // the details and the transaction are held on the server now
      onNext();
    } catch (e) {
      setError(e instanceof ApiError || e instanceof Error ? e.message : "Could not send the documents for approval.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={(e) => { e.preventDefault(); void submit(); }} noValidate>
      <h2 id="step-title">Licence details and photos</h2>
      <p className="lede">Enter the details exactly as printed on the licence. They start from the patient record and must be changed to match the licence. A second person checks them before anything goes to ABDM.</p>
      <Field label="Licence number" autoComplete="off" value={form.documentId} onChange={set("documentId")} error={show("documentId")} />
      <Field label="First name" autoComplete="off" value={form.firstName} onChange={set("firstName")} error={show("firstName")} />
      <Field label="Middle name" autoComplete="off" value={form.middleName} onChange={set("middleName")} error={show("middleName")} hint="Leave empty if there is none" />
      <Field label="Last name" autoComplete="off" value={form.lastName} onChange={set("lastName")} error={show("lastName")} />
      <Field label="Date of birth" type="date" value={form.dob} onChange={set("dob")} error={show("dob")} />
      <div className="field">
        <label htmlFor="dl-gender">Gender</label>
        <select id="dl-gender" value={form.gender} onChange={set("gender")} aria-invalid={show("gender") ? true : undefined}>
          <option value="">Choose…</option>
          <option value="M">Male</option>
          <option value="F">Female</option>
          <option value="O">Other</option>
        </select>
        <div className={show("gender") ? "field-error" : "field-hint"}>{show("gender")}</div>
      </div>
      <Field label="Address" autoComplete="off" value={form.address} onChange={set("address")} hint="As printed, optional" />
      <Field label="State" autoComplete="off" value={form.state} onChange={set("state")} hint="Optional" />
      <Field label="District" autoComplete="off" value={form.district} onChange={set("district")} hint="Optional" />
      <Field label="PIN code" inputMode="numeric" maxLength={6} autoComplete="off" value={form.pinCode} onChange={set("pinCode")} error={show("pinCode")} hint="6 digits, optional" />
      <div className="field">
        <label htmlFor="dl-front">Photograph of the front</label>
        <input id="dl-front" type="file" accept="image/png,image/jpeg" onChange={(e) => setFront(e.target.files?.[0] ?? null)} />
        <div className={show("front") ? "field-error" : "field-hint"}>{show("front") ?? "Shrunk in this browser to fit ABDM's 150 KB limit"}</div>
      </div>
      <div className="field">
        <label htmlFor="dl-back">Photograph of the back</label>
        <input id="dl-back" type="file" accept="image/png,image/jpeg" onChange={(e) => setBack(e.target.files?.[0] ?? null)} />
        <div className={show("back") ? "field-error" : "field-hint"}>{show("back")}</div>
      </div>
      <ErrorNote>{error}</ErrorNote>
      <div className="actions">
        <button type="submit" className="btn btn-primary" disabled={busy}>{busy ? "Sending…" : "Send for approval"}</button>
      </div>
    </form>
  );
}
