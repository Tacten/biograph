import { useState } from "react";
import { requestEnrolmentOtp } from "../../api/abha";
import { ApiError } from "../../api/client";
import { useKnown } from "../../domain/StoreContext";
import { ErrorNote } from "../../ui/ErrorNote";
import { Field } from "../../ui/Field";
import { aadhaarError, digitsOnly } from "../../ui/validate";

export function AadhaarStep({ onNext, onConsentLost, capture = false }: { onNext: () => void; onConsentLost: () => void; capture?: boolean }) {
  const { known, dispatch } = useKnown();
  const [value, setValue] = useState("");
  const [touched, setTouched] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [needsConsent, setNeedsConsent] = useState(false);

  const problem = aadhaarError(value);

  async function send() {
    setTouched(true);
    if (problem || !known.patient || !known.consent) return;
    setBusy(true);
    setError("");
    setNeedsConsent(false);
    const aadhaar = digitsOnly(value);
    if (capture) {
      // The fingerprint route sends the Aadhaar number with the scan, so nothing is requested here.
      dispatch({ type: "learn", patch: { aadhaar } });
      return onNext();
    }
    try {
      const res = await requestEnrolmentOtp(known.patient.name, aadhaar, known.consent.id);
      dispatch({ type: "learn", patch: { aadhaar, txnId: res.txnId } });
      onNext();
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "Could not send the OTP.";
      setError(msg);
      setNeedsConsent(/agreement/i.test(msg));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        void send();
      }}
      noValidate
    >
      <h2 id="step-title">Aadhaar number</h2>
      <p className="lede">{capture ? "The number is sent with the fingerprint scan for this one request and is not stored on the patient." : "An OTP goes to the mobile number linked to this Aadhaar. The number is used for this one request and is not stored on the patient."}</p>
      <Field
        label="Aadhaar number"
        inputMode="numeric"
        autoComplete="off"
        autoFocus
        maxLength={14}
        placeholder="12 digits"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onBlur={() => setTouched(true)}
        error={touched ? problem : null}
        hint="12 digits"
      />
      <ErrorNote>{error}</ErrorNote>
      {needsConsent && (
        <button type="button" className="btn" onClick={onConsentLost}>
          Record the agreement again
        </button>
      )}
      <div className="actions">
        <button type="submit" className="btn btn-primary" disabled={busy}>
          {busy ? "Sending OTP…" : capture ? "Continue" : "Send OTP"}
        </button>
      </div>
    </form>
  );
}
