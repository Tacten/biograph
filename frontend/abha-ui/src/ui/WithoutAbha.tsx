import { useKnown } from "../domain/StoreContext";
import { hrefFor } from "../app/router";

/** A registration is complete without an ABHA. Nothing was written to the patient; the facility patient id is the identifier. */
export function WithoutAbha({ onAnother }: { onAnother: () => void }) {
  const { known } = useKnown();
  if (!known.patient) return null;
  return (
    <div className="card panel">
      <h2>Continuing without an ABHA</h2>
      <p className="lede">
        {known.patient.patient_name} stays registered with the facility patient ID <strong>{known.patient.name}</strong>. No ABHA is linked and nothing was changed on the patient record. An ABHA can be created or linked at any later visit.
      </p>
      <div className="actions">
        <button type="button" className="btn btn-primary" onClick={onAnother}>Register another patient</button>
        <a className="btn" href={hrefFor("create")}>Create an ABHA later</a>
      </div>
    </div>
  );
}

export function SkipAbha({ onSkip }: { onSkip: () => void }) {
  return (
    <div className="skip">
      <button type="button" className="btn btn-quiet" onClick={onSkip}>
        Continue without an ABHA
      </button>
    </div>
  );
}
