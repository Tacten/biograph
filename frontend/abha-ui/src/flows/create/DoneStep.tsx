import { useEffect, useState, type ReactNode } from "react";
import { getCard, getProfile, getQrCode } from "../../api/abha";
import { ApiError } from "../../api/client";
import type { ProfileSummary } from "../../api/types";
import { hrefFor } from "../../app/router";
import { useKnown } from "../../domain/StoreContext";
import { ErrorNote, InfoNote } from "../../ui/ErrorNote";
import { PngPreview } from "../../ui/PngPreview";
import { ProfileCard } from "../../ui/ProfileCard";

/**
 * The ABHA exists and the server has already updated the patient record. This screen shows what ABDM holds (read now,
 * not assumed) with the card and QR code on request.
 */
export function DoneStep({ onAnother, heading = "ABHA created", children }: { onAnother: () => void; heading?: string; children?: ReactNode }) {
  const { known } = useKnown();
  const patient = known.patient;
  const [profile, setProfile] = useState<ProfileSummary | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!patient) return;
    let live = true;
    getProfile(patient.name)
      .then((p) => live && setProfile(p))
      .catch((e: unknown) => live && setError(e instanceof ApiError ? e.message : "Could not load the ABHA profile."));
    return () => {
      live = false;
    };
  }, [patient]);

  if (!patient) return null;
  return (
    <div>
      <h2 id="step-title">{heading}</h2>
      {children ?? (
        <InfoNote tone="ok">
          {patient.patient_name} now has an ABHA{known.abhaNumber ? ` (${known.abhaNumber})` : ""}
          {known.abhaAddress ? ` and the address ${known.abhaAddress}` : ""}. The patient record has already been updated.
        </InfoNote>
      )}
      {!profile && !error && <p className="muted" role="status">Loading what ABDM holds…</p>}
      <ErrorNote>{error}</ErrorNote>
      {profile && <ProfileCard profile={profile} personName={patient.patient_name} />}
      <div className="grid-2">
        <div>
          <h3>ABHA card</h3>
          <PngPreview title="ABHA card" load={() => getCard(patient.name)} />
        </div>
        <div>
          <h3>QR code</h3>
          <PngPreview title="QR code" load={() => getQrCode(patient.name)} />
        </div>
      </div>
      <div className="actions">
        <a className="btn btn-primary" href={hrefFor("profile")}>View profile</a>
        <button type="button" className="btn" onClick={onAnother}>Register another patient</button>
      </div>
    </div>
  );
}
