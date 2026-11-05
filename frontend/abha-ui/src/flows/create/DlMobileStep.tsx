import { useState } from "react";
import { useKnown } from "../../domain/StoreContext";
import { Field } from "../../ui/Field";
import { digitsOnly, mobileError } from "../../ui/validate";

/** Driving licence: the mobile the OTP goes to. The number on the patient record is the default, so it is not asked twice. */
export function DlMobileStep({ hasMobile, onNext }: { hasMobile: boolean; onNext: () => void }) {
  const { dispatch } = useKnown();
  const [other, setOther] = useState(!hasMobile);
  const [value, setValue] = useState("");
  const [touched, setTouched] = useState(false);
  const problem = mobileError(value);

  if (!other) {
    return (
      <div>
        <h2 id="step-title">Mobile number</h2>
        <p className="lede">ABDM sends an OTP to a mobile number to prove it belongs to the patient. This replaces the Aadhaar OTP for this route.</p>
        <div className="actions stack">
          <button type="button" className="btn btn-primary" onClick={() => { dispatch({ type: "forget", keys: ["communicationMobile"] }); onNext(); }}>
            Send OTP to the number on the patient record
          </button>
          <button type="button" className="btn" onClick={() => setOther(true)}>Use a different mobile</button>
        </div>
      </div>
    );
  }
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        setTouched(true);
        if (problem) return;
        dispatch({ type: "learn", patch: { communicationMobile: digitsOnly(value) } });
        onNext();
      }}
      noValidate
    >
      <h2 id="step-title">Mobile number</h2>
      <p className="lede">{hasMobile ? "An OTP is sent to this number." : "There is no mobile number on the patient record. Enter the one the OTP should go to."}</p>
      <Field label="Mobile number" inputMode="numeric" autoComplete="off" autoFocus maxLength={14} placeholder="10 digits" value={value} onChange={(e) => setValue(e.target.value)} onBlur={() => setTouched(true)} error={touched ? problem : null} hint="10 digits" />
      <div className="actions">
        <button type="submit" className="btn btn-primary">Send OTP</button>
        {hasMobile && <button type="button" className="btn btn-quiet" onClick={() => setOther(false)}>Use the number on the patient record</button>}
      </div>
    </form>
  );
}
