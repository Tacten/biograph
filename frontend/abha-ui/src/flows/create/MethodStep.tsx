import { useState } from "react";
import { useRoutes } from "../../app/RoutesContext";
import { useKnown } from "../../domain/StoreContext";
import type { CreateRoute } from "../../domain/known";

const OPTIONS: { route: CreateRoute; label: string; note: string; needs?: "biometric" }[] = [
  { route: "aadhaar-otp", label: "Aadhaar OTP", note: "Recommended. An OTP goes to the mobile linked to the Aadhaar and the ABHA is created at once." },
  { route: "driving-licence", label: "Driving licence", note: "For a patient who cannot use Aadhaar. A second person checks the licence photographs before they go to ABDM, and ABDM answers with an enrolment number, not an ABHA." },
  { route: "biometric", label: "Aadhaar fingerprint", note: "A fingerprint scan on a registered device at this desk replaces the OTP.", needs: "biometric" },
];

/** After the consent: how ABDM should confirm the patient. Routes the site has not enabled are not shown. */
export function MethodStep({ onNext }: { onNext: (route: CreateRoute) => void }) {
  const routes = useRoutes();
  const { known, dispatch } = useKnown();
  const offered = OPTIONS.filter((o) => (o.route === "aadhaar-otp" ? routes.aadhaar_otp : o.route === "driving-licence" ? routes.driving_licence : routes.biometric));
  const [picked, setPicked] = useState<CreateRoute>(known.createRoute && offered.some((o) => o.route === known.createRoute) ? known.createRoute : (offered[0]?.route ?? "aadhaar-otp"));
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        dispatch({ type: "learn", patch: { createRoute: picked } });
        onNext(picked);
      }}
    >
      <h2 id="step-title">How should ABDM confirm the patient?</h2>
      <p className="lede">The agreement above covers every route.</p>
      <fieldset className="choices wide">
        <legend className="sr-only">How to create</legend>
        {offered.map((o) => (
          <label key={o.route} className="choice">
            <input type="radio" name="create-route" checked={picked === o.route} onChange={() => setPicked(o.route)} />
            <span><strong>{o.label}</strong><br /><small className="muted">{o.note}</small></span>
          </label>
        ))}
      </fieldset>
      <div className="actions"><button type="submit" className="btn btn-primary">Continue</button></div>
    </form>
  );
}
