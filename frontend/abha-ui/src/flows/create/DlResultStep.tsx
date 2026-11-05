import { useCallback, useEffect, useState } from "react";
import { getDocumentStatus } from "../../api/abha";
import { ApiError } from "../../api/client";
import type { DocumentEnrolment } from "../../api/types";
import { useKnown } from "../../domain/StoreContext";
import { ErrorNote, InfoNote } from "../../ui/ErrorNote";

/** Where the documents stand: waiting for a second person, refused, or sent to ABDM with an enrolment number (not an ABHA). */
export function DlResultStep({ onRestart }: { onRestart: () => void }) {
  const { known } = useKnown();
  const [row, setRow] = useState<DocumentEnrolment | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const patient = known.patient?.name;

  const load = useCallback(async () => {
    if (!patient) return;
    setBusy(true);
    setError("");
    try {
      setRow(await getDocumentStatus(patient));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not check the status.");
    } finally {
      setBusy(false);
    }
  }, [patient]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div>
      <h2 id="step-title">Approval and enrolment number</h2>
      {!row && !error && <p className="muted" role="status">Checking…</p>}
      <ErrorNote>{error}</ErrorNote>
      {row?.status === "Awaiting approval" && (
        <InfoNote>Waiting for a second person (a Healthcare Administrator) to check the licence photographs against the patient. Nothing has gone to ABDM yet, and the documents are deleted from this system once it is decided.</InfoNote>
      )}
      {row?.status === "Rejected" && (
        <InfoNote tone="warn">The documents were not approved{row.decision_note ? `: ${row.decision_note}` : ""}. Nothing was sent to ABDM.</InfoNote>
      )}
      {row?.status === "Failed" && <InfoNote tone="warn">ABDM did not accept the documents{row.result_message ? `: ${row.result_message}` : ""}.</InfoNote>}
      {row?.status === "Submitted" && (
        <InfoNote tone="ok">
          ABDM issued the enrolment number <strong>{row.enrolment_number}</strong>{row.enrolment_state ? ` (${row.enrolment_state})` : ""}. This is not an ABHA yet: ABDM creates the ABHA after it has checked the document. Use Verify ABHA later to link it.
        </InfoNote>
      )}
      <div className="actions">
        <button type="button" className="btn" onClick={() => void load()} disabled={busy}>Check again</button>
        {(row?.status === "Rejected" || row?.status === "Failed") && <button type="button" className="btn btn-primary" onClick={onRestart}>Start again</button>}
      </div>
    </div>
  );
}
