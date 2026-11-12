import { useCallback, useEffect, useState } from "react";
import { decide, getForReview, listPending } from "../../api/abha";
import { ApiError } from "../../api/client";
import type { PendingApproval, ReviewPacket } from "../../api/types";
import { ErrorNote, InfoNote } from "../../ui/ErrorNote";

const ROWS: [keyof ReviewPacket["details"], string][] = [
  ["documentId", "Licence number"],
  ["firstName", "First name"],
  ["middleName", "Middle name"],
  ["lastName", "Last name"],
  ["dob", "Date of birth"],
  ["gender", "Gender"],
  ["address", "Address"],
  ["state", "State"],
  ["district", "District"],
  ["pinCode", "PIN code"],
];
const GENDER: Record<string, string> = { M: "Male", F: "Female", O: "Other" };

/**
 * The second person's check of a driving-licence enrolment: the details and both photographs, side by side with who the
 * patient is. Only an approval goes to ABDM. The photographs are held in memory while this screen is open.
 */
export function ApprovalsFlow() {
  const [list, setList] = useState<PendingApproval[] | null>(null);
  const [packet, setPacket] = useState<ReviewPacket | null>(null);
  const [error, setError] = useState("");
  const [done, setDone] = useState("");
  const [checked, setChecked] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    setError("");
    try {
      setList(await listPending());
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load the approvals.");
      setList([]);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function open(name: string) {
    setError("");
    setDone("");
    setChecked(false);
    setReason("");
    try {
      setPacket(await getForReview(name));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not open this enrolment.");
    }
  }

  async function act(decision: "approve" | "reject") {
    if (!packet) return;
    setBusy(true);
    setError("");
    try {
      const res = await decide(packet.name, decision, reason.trim());
      setDone(
        res.status === "Submitted"
          ? `Sent to ABDM. Enrolment number ${res.enrolment_number ?? ""}. It is not an ABHA yet.`
          : "Rejected. Nothing was sent to ABDM, and the documents were deleted.",
      );
      setPacket(null);
      await refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "The decision could not be recorded.");
    } finally {
      setBusy(false);
    }
  }

  if (packet) {
    const d = packet.details;
    return (
      <section className="card panel" aria-labelledby="review-title">
        <h2 id="review-title">Check {packet.patient_name}</h2>
        <p className="lede">Collected by {packet.collected_by}. Compare the photographs with the patient in front of you, and the details with the licence.</p>
        <div className="grid-2">
          <figure className="png-figure"><img src={`data:image/jpeg;base64,${packet.front_photo}`} alt="Front of the licence" /><figcaption>Front</figcaption></figure>
          <figure className="png-figure"><img src={`data:image/jpeg;base64,${packet.back_photo}`} alt="Back of the licence" /><figcaption>Back</figcaption></figure>
        </div>
        <dl className="facts">
          {ROWS.filter(([k]) => d[k]).map(([k, label]) => (
            <div key={k}><dt>{label}</dt><dd>{k === "gender" ? GENDER[d.gender] ?? d.gender : String(d[k])}</dd></div>
          ))}
        </dl>
        <label className="check">
          <input type="checkbox" checked={checked} onChange={(e) => setChecked(e.target.checked)} />
          <span>I checked the photographs against the person and the details against the licence.</span>
        </label>
        <div className="field">
          <label htmlFor="reject-reason">Reason, needed to reject</label>
          <input id="reject-reason" value={reason} onChange={(e) => setReason(e.target.value)} autoComplete="off" />
        </div>
        <ErrorNote>{error}</ErrorNote>
        <div className="actions">
          <button type="button" className="btn btn-primary" disabled={!checked || busy} onClick={() => void act("approve")}>{busy ? "Working…" : "Approve and send to ABDM"}</button>
          <button type="button" className="btn" disabled={!reason.trim() || busy} onClick={() => void act("reject")}>Reject</button>
          <button type="button" className="btn btn-quiet" disabled={busy} onClick={() => setPacket(null)}>Back to the list</button>
        </div>
      </section>
    );
  }

  return (
    <section className="card panel" aria-labelledby="pending-title">
      <h2 id="pending-title">Waiting for approval</h2>
      {done && <InfoNote tone="ok">{done}</InfoNote>}
      <ErrorNote>{error}</ErrorNote>
      {list === null && <p className="muted" role="status">Loading…</p>}
      {list && list.length === 0 && !error && <p className="muted">Nothing is waiting.</p>}
      {list && list.length > 0 && (
        <ul className="list">
          {list.map((p) => (
            <li key={p.name} className="list-row">
              <span><strong>{p.patient_name}</strong><br /><small className="muted">{p.patient} · collected by {p.requested_by}</small></span>
              <button type="button" className="btn" onClick={() => void open(p.name)}>Review</button>
            </li>
          ))}
        </ul>
      )}
      <div className="actions"><button type="button" className="btn btn-quiet" onClick={() => void refresh()}>Refresh</button></div>
    </section>
  );
}
