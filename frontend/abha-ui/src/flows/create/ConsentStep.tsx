import { useEffect, useState } from "react";
import { getConsentText, recordConsent } from "../../api/abha";
import { ApiError } from "../../api/client";
import type { ConsentText } from "../../api/types";
import { useKnown } from "../../domain/StoreContext";
import { ErrorNote } from "../../ui/ErrorNote";

/** The terms, in full and unchanged, before any field that takes the Aadhaar number (CRT_ABHA_102). */
export function ConsentStep({ onNext }: { onNext: () => void }) {
  const { known, dispatch } = useKnown();
  const [terms, setTerms] = useState<ConsentText | null>(null);
  const [agreed, setAgreed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let live = true;
    getConsentText()
      .then((t) => live && setTerms(t))
      .catch((e: unknown) => live && setError(e instanceof ApiError ? e.message : "Could not load the terms."));
    return () => {
      live = false;
    };
  }, []);

  async function agree() {
    if (!known.patient || !agreed) return;
    setBusy(true);
    setError("");
    try {
      const rec = await recordConsent(known.patient.name);
      dispatch({ type: "learn", patch: { consent: { id: rec.consent_name, at: new Date().toISOString() } } });
      onNext();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not record the agreement.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <h2 id="step-title">Patient consent</h2>
      <p className="lede">Read these terms to the patient, or hand them the screen. Nothing is sent to ABDM until they agree.</p>
      {terms ? (
        <section className="consent" aria-label={terms.title}>
          <h3>{terms.title}</h3>
          <p>{terms.text}</p>
        </section>
      ) : (
        !error && <p className="muted">Loading the terms…</p>
      )}
      {terms && !terms.available && (
        <ErrorNote>Consent cannot be recorded on this site, so an ABHA cannot be created here yet: the consent app (frappe_abdm) is not installed. Ask an administrator to install it.</ErrorNote>
      )}
      <label className="check">
        <input type="checkbox" checked={agreed} disabled={!terms || !terms.available} onChange={(e) => setAgreed(e.target.checked)} />
        <span>I agree. The patient has been shown these terms and agrees to them.</span>
      </label>
      <ErrorNote>{error}</ErrorNote>
      <div className="actions">
        <button type="button" className="btn btn-primary" disabled={!agreed || busy || !terms || !terms.available} onClick={agree}>
          {busy ? "Recording…" : "Record agreement and continue"}
        </button>
      </div>
      {terms && <p className="muted small">Your name, the time and the version of these terms ({terms.version}) are recorded.</p>}
    </div>
  );
}
