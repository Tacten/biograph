import { useState } from "react";
import { enrolByBiometric } from "../../api/abha";
import { ApiError } from "../../api/client";
import { useKnown } from "../../domain/StoreContext";
import { RdServiceError } from "../../rd/rdService";
import { useRd } from "../../rd/RdContext";
import { ErrorNote } from "../../ui/ErrorNote";

/**
 * Scan a fingerprint on the registered device and create the ABHA. The PID block lives in this function only: it is
 * passed straight to the server and then dropped. A failed scan shows why and the person scans again.
 */
export function BioCaptureStep({ onNext, onBack }: { onNext: (mobileLinked: boolean) => void; onBack: () => void }) {
  const rd = useRd();
  const { known, dispatch } = useKnown();
  const [busy, setBusy] = useState<"" | "scan" | "send">("");
  const [error, setError] = useState("");

  async function scan() {
    if (!known.patient || !known.aadhaar || !known.consent) return setError("The Aadhaar number or the agreement is missing. Go back and enter it.");
    setError("");
    try {
      setBusy("scan");
      const pid = await rd.capture();
      setBusy("send");
      const res = await enrolByBiometric(known.patient.name, known.aadhaar, pid, known.consent.id);
      dispatch({ type: "learn", patch: { txnId: res.txnId, abhaNumber: res.abha_number, mobileLinked: res.mobile_linked } });
      dispatch({ type: "forget", keys: ["aadhaar"] });
      onNext(res.mobile_linked);
    } catch (e) {
      setError(e instanceof RdServiceError || e instanceof ApiError || e instanceof Error ? e.message : "The scan did not work. Try again.");
    } finally {
      setBusy("");
    }
  }

  return (
    <div>
      <h2 id="step-title">Scan fingerprint</h2>
      <p className="lede">Ask the patient to place a finger on the fingerprint device at this desk, then press Scan. The scan is sent to ABDM with the Aadhaar number and is not kept.</p>
      <ErrorNote>{error}</ErrorNote>
      <div className="actions">
        <button type="button" className="btn btn-primary" onClick={() => void scan()} disabled={busy !== ""}>
          {busy === "scan" ? "Scanning…" : busy === "send" ? "Creating the ABHA…" : error ? "Scan again" : "Scan fingerprint"}
        </button>
        <button type="button" className="btn btn-quiet" onClick={onBack} disabled={busy !== ""}>Change Aadhaar number</button>
      </div>
    </div>
  );
}
