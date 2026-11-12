import { useEffect, useState } from "react";
import { getContext } from "../../api/abha";
import { ApiError } from "../../api/client";
import type { LoginProfile, PatientContext } from "../../api/types";
import { StepRail } from "../../app/StepRail";
import { hrefFor } from "../../app/router";
import { useKnown } from "../../domain/StoreContext";
import { ErrorNote, InfoNote } from "../../ui/ErrorNote";
import { SkipAbha, WithoutAbha } from "../../ui/WithoutAbha";
import { DoneStep } from "../create/DoneStep";
import { type IdentifierKind, verifySteps } from "../steps";
import { IdentifierStep, type Option } from "./IdentifierStep";
import { MethodStep } from "./MethodStep";
import { VerifyOtpStep } from "./VerifyOtpStep";

type Phase = "identifier" | "method" | "otp" | "done";

const digits = (s?: string | null) => (s ?? "").replace(/\D/g, "");

/**
 * Verify an ABHA that already exists, so the app can show its profile, card and QR code. A patient who already has an
 * ABHA is verified with the number or address on the record (no typing, and no identifier that could name another
 * person's ABHA); a patient without one can also be found by Aadhaar.
 */
export function VerifyFlow() {
  const { known, dispatch } = useKnown();
  const [ctx, setCtx] = useState<PatientContext | null>(null);
  const [error, setError] = useState("");
  const [phase, setPhase] = useState<Phase>("identifier");
  const [kind, setKind] = useState<IdentifierKind>("abha-number");
  const [visited, setVisited] = useState<ReadonlySet<string>>(() => new Set(["identifier"]));
  const [skipped, setSkipped] = useState(false);
  const [mismatch, setMismatch] = useState(false);
  const patient = known.patient;

  const go = (next: Phase) => {
    setVisited((v) => new Set(v).add(next));
    setPhase(next);
  };

  useEffect(() => {
    if (!patient) return;
    let live = true;
    getContext(patient.name)
      .then((c) => {
        if (!live) return;
        setCtx(c);
        setKind(c.abha.abha_number ? "abha-number" : c.abha.abha_address ? "abha-address" : "aadhaar");
      })
      .catch((e: unknown) => live && setError(e instanceof ApiError ? e.message : "Could not check this patient."));
    return () => {
      live = false;
    };
  }, [patient?.name]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!patient) return null;
  if (error) return <div className="card panel"><ErrorNote>{error}</ErrorNote></div>;
  if (!ctx) return <p className="muted" role="status">Checking {patient.patient_name}…</p>;
  if (skipped) return <WithoutAbha onAnother={() => dispatch({ type: "patient", patient: undefined })} />;

  const linked = ctx.abha.linked;
  const options: Option[] = linked
    ? [
        ...(ctx.abha.abha_number ? [{ kind: "abha-number" as const, label: "ABHA number", known: ctx.abha.abha_number }] : []),
        ...(ctx.abha.abha_address ? [{ kind: "abha-address" as const, label: "ABHA address", known: ctx.abha.abha_address }] : []),
      ]
    : [
        { kind: "aadhaar", label: "Aadhaar number" },
        { kind: "abha-number", label: "ABHA number" },
        { kind: "abha-address", label: "ABHA address" },
      ];
  const valueKnown = options.find((o) => o.kind === kind)?.known !== undefined;

  function verified(profile: LoginProfile) {
    // ABDM named an account; if the record already held a different ABHA, say so rather than calling it a success.
    if (ctx?.abha.abha_number && profile.abha_number && digits(ctx.abha.abha_number) !== digits(profile.abha_number)) setMismatch(true);
    dispatch({ type: "forgetSensitive" });
    go("done");
  }

  let body;
  switch (phase) {
    case "identifier":
      body = <IdentifierStep options={options} kind={kind} onKind={setKind} onNext={() => go(kind === "abha-address" ? "method" : "otp")} />;
      break;
    case "method":
      body = <MethodStep onNext={() => go("otp")} />;
      break;
    case "otp":
      body = <VerifyOtpStep onVerified={verified} onBack={() => go(kind === "abha-address" ? "method" : "identifier")} />;
      break;
    default:
      body = (
        <DoneStep heading="ABHA verified" onAnother={() => dispatch({ type: "patient", patient: undefined })}>
          {mismatch ? (
            <InfoNote tone="warn">
              ABDM verified an ABHA with a different number than the one on this patient's record. Check with an administrator before relying on the record.
            </InfoNote>
          ) : (
            <InfoNote tone="ok">The ABHA is verified for this session. What ABDM holds is shown below, and the card and QR code can be fetched.</InfoNote>
          )}
        </DoneStep>
      );
  }

  return (
    <div className="layout-wizard">
      <StepRail steps={verifySteps(kind, valueKnown)} currentId={phase} known={{ ...known, identifierKind: kind }} label="Verify ABHA steps" visited={visited} />
      <section className="card panel" aria-labelledby="step-title">
        {linked && phase === "identifier" && (
          <InfoNote>
            {patient.patient_name} already has an ABHA ending {ctx.abha.abha_number_masked?.slice(-4) ?? "on file"}. Verifying shows its profile and card here. <a href={hrefFor("profile")}>View the profile</a> if it was verified recently.
          </InfoNote>
        )}
        {body}
        {phase !== "done" && <SkipAbha onSkip={() => { dispatch({ type: "forgetSensitive" }); setSkipped(true); }} />}
      </section>
    </div>
  );
}
