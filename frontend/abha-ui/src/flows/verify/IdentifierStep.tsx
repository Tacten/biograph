import { useState } from "react";
import { useKnown } from "../../domain/StoreContext";
import { Field } from "../../ui/Field";
import { aadhaarError, abhaAddressLookupError, abhaNumberError, digitsOnly } from "../../ui/validate";
import type { IdentifierKind } from "../steps";

export interface Option {
  kind: IdentifierKind;
  label: string;
  /** The value already on the patient record, shown but never asked for again. */
  known?: string;
}

const HINT: Record<IdentifierKind, string> = { aadhaar: "12 digits", "abha-number": "14 digits, dashes are fine", "abha-address": "For example name@sbx" };
const PROBLEM = { aadhaar: aadhaarError, "abha-number": abhaNumberError, "abha-address": abhaAddressLookupError };

/** What identifies the patient. A value already on the record is used as it is; only a missing one is typed. */
export function IdentifierStep({ options, kind, onKind, onNext }: { options: Option[]; kind: IdentifierKind; onKind: (k: IdentifierKind) => void; onNext: () => void }) {
  const { dispatch } = useKnown();
  const [value, setValue] = useState("");
  const [touched, setTouched] = useState(false);
  const chosen = options.find((o) => o.kind === kind) ?? options[0]!;
  const problem = chosen.known ? null : PROBLEM[chosen.kind](value);

  function submit() {
    setTouched(true);
    if (problem) return;
    const raw = chosen.known ?? value;
    const v = chosen.kind === "abha-address" ? raw.trim().toLowerCase() : digitsOnly(raw);
    dispatch({ type: "forget", keys: ["aadhaar", "otpMethod", "txnId"] });
    dispatch({ type: "learn", patch: { identifierKind: chosen.kind, ...(chosen.kind === "aadhaar" ? { aadhaar: v } : chosen.kind === "abha-number" ? { abhaNumber: v } : { abhaAddress: v }) } });
    onNext();
  }

  return (
    <form onSubmit={(e) => { e.preventDefault(); submit(); }} noValidate>
      <h2 id="step-title">Identify the patient</h2>
      <p className="lede">Choose what to verify the ABHA with. ABDM sends an OTP, and the ABHA is verified for this session.</p>
      {options.length > 1 && (
        <div className="seg" role="radiogroup" aria-label="Verify with">
          {options.map((o) => (
            <label key={o.kind} className="seg-item">
              <input type="radio" name="verify-with" checked={kind === o.kind} onChange={() => { onKind(o.kind); setValue(""); setTouched(false); }} />
              <span>{o.label}</span>
            </label>
          ))}
        </div>
      )}
      {chosen.known ? (
        <p className="lede" data-testid="known-identifier">
          {chosen.label} on the patient record: <strong>{chosen.kind === "abha-number" ? maskNumber(chosen.known) : chosen.known}</strong>. It is used as it is.
        </p>
      ) : (
        <Field label={chosen.label} inputMode={chosen.kind === "abha-address" ? "email" : "numeric"} autoComplete="off" autoCapitalize="none" autoFocus maxLength={chosen.kind === "abha-address" ? 64 : 17} value={value} onChange={(e) => setValue(e.target.value)} onBlur={() => setTouched(true)} error={touched ? problem : null} hint={HINT[chosen.kind]} />
      )}
      <div className="actions">
        <button type="submit" className="btn btn-primary">Continue</button>
      </div>
    </form>
  );
}

export function maskNumber(n: string): string {
  const d = digitsOnly(n);
  return d.length === 14 ? `${d.slice(0, 2)}-XXXX-XXXX-${d.slice(10)}` : n;
}
