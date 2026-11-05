import { useState } from "react";
import { useKnown } from "../../domain/StoreContext";

const LABEL = { aadhaar: "Aadhaar OTP", abdm: "Mobile OTP" } as const;
const NOTE = { aadhaar: "Sent to the mobile number linked to the patient's Aadhaar.", abdm: "Sent to the mobile number registered with the ABHA." } as const;

/** Only for an ABHA address, the one identifier ABDM lets the patient receive either kind of OTP for. */
export function MethodStep({ onNext }: { onNext: () => void }) {
  const { dispatch } = useKnown();
  const [picked, setPicked] = useState<"aadhaar" | "abdm">("abdm");
  return (
    <form onSubmit={(e) => { e.preventDefault(); dispatch({ type: "learn", patch: { otpMethod: picked } }); onNext(); }}>
      <h2 id="step-title">Choose OTP method</h2>
      <p className="lede">How should ABDM send the OTP?</p>
      <fieldset className="choices">
        <legend className="sr-only">OTP method</legend>
        {(["abdm", "aadhaar"] as const).map((m) => (
          <label key={m} className="choice">
            <input type="radio" name="otp-method" checked={picked === m} onChange={() => setPicked(m)} />
            <span><strong>{LABEL[m]}</strong><br /><small className="muted">{NOTE[m]}</small></span>
          </label>
        ))}
      </fieldset>
      <div className="actions"><button type="submit" className="btn btn-primary">Send OTP</button></div>
    </form>
  );
}
