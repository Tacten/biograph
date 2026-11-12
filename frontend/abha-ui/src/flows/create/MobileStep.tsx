import { useState } from "react";
import { sendMobileOtp, verifyMobileOtp } from "../../api/abha";
import { useKnown } from "../../domain/StoreContext";
import { Field } from "../../ui/Field";
import { OtpPanel } from "../../ui/OtpPanel";
import { digitsOnly, mobileError } from "../../ui/validate";

type Phase = "choose" | "enter" | "otp";

/**
 * Only reached when ABDM did not link the mobile by itself. The ABHA stays inactive until a mobile is proven with an
 * OTP: by default the number on the patient record, or a different one.
 */
export function MobileStep({ hasMobile, onNext }: { hasMobile: boolean; onNext: () => void }) {
  const { known, dispatch } = useKnown();
  const [phase, setPhase] = useState<Phase>(hasMobile ? "choose" : "enter");
  const [value, setValue] = useState("");
  const [touched, setTouched] = useState(false);
  const [chosen, setChosen] = useState(""); // "" means: the number on the patient record
  const patient = known.patient?.name;

  const problem = mobileError(value);

  async function send() {
    if (!patient || !known.txnId) throw new Error("The enrolment session has expired. Start again.");
    const res = await sendMobileOtp(patient, known.txnId, chosen || undefined);
    dispatch({ type: "learn", patch: { txnId: res.txnId ?? known.txnId } });
  }

  async function verify(code: string) {
    if (!patient || !known.txnId) throw new Error("The enrolment session has expired. Start again.");
    const res = await verifyMobileOtp(patient, known.txnId, code);
    void res;
    dispatch({ type: "forget", keys: ["communicationMobile"] });
    onNext();
  }

  if (phase === "choose") {
    return (
      <div>
        <h2 id="step-title">Confirm mobile</h2>
        <p className="lede">ABDM could not link a mobile number by itself, so the ABHA is not active yet. An OTP to the patient's mobile number activates it.</p>
        <div className="actions stack">
          <button type="button" className="btn btn-primary" onClick={() => { setChosen(""); setPhase("otp"); }}>
            Send OTP to the number on the patient record
          </button>
          <button type="button" className="btn" onClick={() => setPhase("enter")}>
            Use a different mobile
          </button>
        </div>
      </div>
    );
  }

  if (phase === "enter") {
    return (
      <form
        onSubmit={(e) => {
          e.preventDefault();
          setTouched(true);
          if (problem) return;
          setChosen(digitsOnly(value));
          dispatch({ type: "learn", patch: { communicationMobile: digitsOnly(value) } });
          setPhase("otp");
        }}
        noValidate
      >
        <h2 id="step-title">Confirm mobile</h2>
        <p className="lede">{hasMobile ? "An OTP is sent to this number to prove it belongs to the patient." : "There is no mobile number on the patient record. Enter the one to activate the ABHA with; an OTP is sent to it."}</p>
        <Field label="Mobile number" inputMode="numeric" autoComplete="off" autoFocus maxLength={14} placeholder="10 digits" value={value} onChange={(e) => setValue(e.target.value)} onBlur={() => setTouched(true)} error={touched ? problem : null} hint="10 digits" />
        <div className="actions">
          <button type="submit" className="btn btn-primary">Send OTP</button>
          {hasMobile && <button type="button" className="btn btn-quiet" onClick={() => setPhase("choose")}>Use the number on the patient record</button>}
        </div>
      </form>
    );
  }

  return (
    <OtpPanel
      heading="Verify mobile OTP"
      lede="Enter the 6-digit OTP sent to the mobile number."
      label="Mobile OTP"
      verify={verify}
      resend={send}
      send={send}
      back={{ label: "Change the number", onClick: () => setPhase(hasMobile ? "choose" : "enter") }}
    />
  );
}
