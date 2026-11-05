import { useState } from "react";
import { requestAddressOtp, requestLoginOtp, verifyAddressOtp, verifyLoginOtp } from "../../api/abha";
import type { LoginProfile } from "../../api/types";
import { hrefFor } from "../../app/router";
import { useKnown } from "../../domain/StoreContext";
import { InfoNote } from "../../ui/ErrorNote";
import { OtpPanel } from "../../ui/OtpPanel";

const NOT_FOUND = /ABDM-1114/;
/** The branch refuses an ABHA number that another patient record already holds, and names that record. */
const HELD_BY = /already linked to a different patient record \(([^)]+)\)/i;

export function VerifyOtpStep({ onVerified, onBack }: { onVerified: (profile: LoginProfile) => void; onBack: () => void }) {
  const { known, dispatch } = useKnown();
  const [notFound, setNotFound] = useState(false);
  const [heldBy, setHeldBy] = useState<string | null>(null);
  const patient = known.patient?.name;
  const kind = known.identifierKind;
  const system = known.otpMethod ?? "abdm";

  async function request() {
    if (!patient || !kind) throw new Error("Choose how to verify first.");
    try {
      const res =
        kind === "abha-address"
          ? await requestAddressOtp(patient, known.abhaAddress ?? "", system)
          : await requestLoginOtp(patient, (kind === "aadhaar" ? known.aadhaar : known.abhaNumber) ?? "", kind);
      dispatch({ type: "learn", patch: { txnId: res.txnId } });
    } catch (e) {
      if (e instanceof Error && NOT_FOUND.test(e.message)) setNotFound(true);
      throw e;
    }
  }

  async function verify(code: string) {
    if (!patient || !kind || !known.txnId) throw new Error("The OTP request has expired. Go back and send it again.");
    try {
      const profile = kind === "abha-address" ? await verifyAddressOtp(patient, known.txnId, code, system) : await verifyLoginOtp(patient, known.txnId, code, kind);
      onVerified(profile);
    } catch (e) {
      if (e instanceof Error && NOT_FOUND.test(e.message)) setNotFound(true);
      if (e instanceof Error) setHeldBy(HELD_BY.exec(e.message)?.[1] ?? null);
      throw e;
    }
  }

  // No ABHA for this Aadhaar: offer creation, carrying the number so it is not asked again.
  function createInstead() {
    dispatch({ type: "forget", keys: ["txnId", "identifierKind", "otpMethod"] });
    window.location.hash = hrefFor("create");
  }

  function openHolder(name: string) {
    dispatch({ type: "patient", patient: { name, patient_name: name } });
    window.location.hash = hrefFor("verify");
  }

  const lede =
    kind === "abha-number" ? "Enter the 6-digit OTP sent to the mobile number linked to this ABHA." : kind === "aadhaar" ? "Enter the 6-digit OTP sent to the mobile number linked to the Aadhaar." : "Enter the 6-digit OTP.";
  return (
    <OtpPanel heading="Verify OTP" lede={lede} label="OTP" verify={verify} resend={request} send={request} back={{ label: "Change how the patient is verified", onClick: onBack }}>
      {heldBy && (
        <InfoNote tone="warn">
          This ABHA already belongs to the patient record <strong>{heldBy}</strong>, and one ABHA can belong to only one patient. If that is the same person, use that record; the other one is a duplicate for an administrator to merge.{" "}
          <button type="button" className="btn" onClick={() => openHolder(heldBy)}>Verify {heldBy} here</button>{" "}
          <a className="btn" href={`/app/patient/${encodeURIComponent(heldBy)}`} target="_blank" rel="noopener noreferrer">Open the record</a>
        </InfoNote>
      )}
      {notFound && (
        <InfoNote tone="warn">
          ABDM has no ABHA for this {kind === "aadhaar" ? "Aadhaar number" : "identifier"}.
          {kind === "aadhaar" && (
            <>
              {" "}
              <button type="button" className="btn" onClick={createInstead}>Create an ABHA with this Aadhaar</button>
            </>
          )}
        </InfoNote>
      )}
    </OtpPanel>
  );
}
