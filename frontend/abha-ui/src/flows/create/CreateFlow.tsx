import { useEffect, useState } from "react";
import { getContext } from "../../api/abha";
import { ApiError } from "../../api/client";
import type { PatientContext } from "../../api/types";
import { StepRail } from "../../app/StepRail";
import { hrefFor } from "../../app/router";
import { useKnown } from "../../domain/StoreContext";
import { SkipAbha, WithoutAbha } from "../../ui/WithoutAbha";
import { ErrorNote } from "../../ui/ErrorNote";
import { createSteps } from "../steps";
import { AadhaarStep } from "./AadhaarStep";
import { AddressStep } from "./AddressStep";
import { BioCaptureStep } from "./BioCaptureStep";
import { ConsentStep } from "./ConsentStep";
import { DlDetailsStep } from "./DlDetailsStep";
import { DlMobileStep } from "./DlMobileStep";
import { DlOtpStep } from "./DlOtpStep";
import { DlResultStep } from "./DlResultStep";
import { DoneStep } from "./DoneStep";
import { MethodStep } from "./MethodStep";
import { MobileStep } from "./MobileStep";
import { OtpStep } from "./OtpStep";

/** Create an ABHA: consent, then how to confirm the patient (Aadhaar OTP, driving licence, or fingerprint), then that route's steps. */
export function CreateFlow() {
  const { known, dispatch } = useKnown();
  const [step, setStep] = useState("consent");
  const [visited, setVisited] = useState<ReadonlySet<string>>(() => new Set(["consent"]));
  const go = (next: string) => {
    setVisited((v) => new Set(v).add(next));
    setStep(next);
  };
  const [ctx, setCtx] = useState<PatientContext | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [skipped, setSkipped] = useState(false);
  const patient = known.patient;

  // One ABHA per patient: look first, and do not start a second creation for someone who already has one.
  useEffect(() => {
    if (!patient) return;
    let live = true;
    setCtx(null);
    setError("");
    getContext(patient.name)
      .then((c) => live && setCtx(c))
      .catch((e: unknown) => live && setError(e instanceof ApiError ? e.message : "Could not check this patient."));
    return () => {
      live = false;
    };
  }, [patient?.name, attempt]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!patient) return null;
  if (error) {
    return (
      <div className="card panel">
        <ErrorNote>{error}</ErrorNote>
        <div className="actions"><button type="button" className="btn" onClick={() => setAttempt((n) => n + 1)}>Try again</button></div>
      </div>
    );
  }
  if (!ctx) return <p className="muted" role="status">Checking {patient.patient_name}…</p>;

  if (skipped) return <WithoutAbha onAnother={() => dispatch({ type: "patient", patient: undefined })} />;

  const justCreated = step === "done";
  if (ctx.abha.linked && !justCreated) {
    return (
      <div className="card panel">
        <h2>{patient.patient_name} already has an ABHA</h2>
        <p className="lede">
          An ABHA ending {ctx.abha.abha_number_masked?.slice(-4) ?? "on file"} is linked to this patient. One patient can have only one ABHA, so a second one is not created.
        </p>
        <div className="actions">
          <a className="btn btn-primary" href={hrefFor("profile")}>View the profile</a>
        </div>
      </div>
    );
  }

  const restartConsent = () => {
    dispatch({ type: "forget", keys: ["consent", "txnId", "aadhaar", "createRoute"] });
    go("consent");
  };

  const route = known.createRoute ?? "aadhaar-otp";
  const backToAadhaar = () => {
    dispatch({ type: "forget", keys: ["aadhaar", "txnId"] });
    go("aadhaar");
  };

  let body;
  switch (step) {
    case "consent":
      body = <ConsentStep onNext={() => go("method")} />;
      break;
    case "method":
      body = <MethodStep onNext={(r) => go(r === "driving-licence" ? "dl-mobile" : r === "biometric" ? (known.aadhaar ? "capture" : "aadhaar") : known.aadhaar ? "otp" : "aadhaar")} />;
      break;
    case "aadhaar":
      body = <AadhaarStep capture={route === "biometric"} onNext={() => go(route === "biometric" ? "capture" : "otp")} onConsentLost={restartConsent} />;
      break;
    case "otp":
      body = <OtpStep onNext={(linked) => go(linked ? "address" : "mobile")} onBack={backToAadhaar} />;
      break;
    case "capture":
      body = <BioCaptureStep onNext={(linked) => go(linked ? "address" : "mobile")} onBack={backToAadhaar} />;
      break;
    case "mobile":
      body = <MobileStep hasMobile={ctx.patient.has_mobile} onNext={() => go("address")} />;
      break;
    case "address":
      body = <AddressStep onNext={() => { dispatch({ type: "forgetSensitive" }); go("done"); }} />;
      break;
    case "dl-mobile":
      body = <DlMobileStep hasMobile={ctx.patient.has_mobile} onNext={() => go("dl-otp")} />;
      break;
    case "dl-otp":
      body = <DlOtpStep onNext={() => go("dl-details")} onBack={() => go("dl-mobile")} />;
      break;
    case "dl-details":
      body = <DlDetailsStep patient={ctx.patient} onNext={() => go("dl-result")} />;
      break;
    case "dl-result":
      body = <DlResultStep onRestart={restartConsent} />;
      break;
    default:
      body = <DoneStep onAnother={() => { dispatch({ type: "patient", patient: undefined }); go("consent"); }} />;
  }

  return (
    <div className="layout-wizard">
      <StepRail steps={createSteps(route)} currentId={step} known={known} label="Create ABHA steps" visited={visited} />
      <section className="card panel" aria-labelledby="step-title">
        {body}
        {step !== "done" && step !== "dl-result" && <SkipAbha onSkip={() => { dispatch({ type: "forgetSensitive" }); dispatch({ type: "forget", keys: ["aadhaar", "consent"] }); setSkipped(true); }} />}
      </section>
    </div>
  );
}
