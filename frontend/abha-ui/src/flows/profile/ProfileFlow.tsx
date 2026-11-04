import { useCallback, useEffect, useState } from "react";
import { getCard, getContext, getProfile, getQrCode } from "../../api/abha";
import { ApiError } from "../../api/client";
import type { ProfileSummary } from "../../api/types";
import { hrefFor } from "../../app/router";
import { useKnown } from "../../domain/StoreContext";
import { ErrorNote } from "../../ui/ErrorNote";
import { PngPreview } from "../../ui/PngPreview";
import { ProfileCard } from "../../ui/ProfileCard";

type Load = { status: "loading" } | { status: "none" } | { status: "ready"; profile: ProfileSummary } | { status: "expired"; message: string } | { status: "error"; message: string };

/** What ABDM holds for the patient's ABHA: photograph, details, QR code and card. Read live; nothing is stored here. */
export function ProfileFlow() {
  const { known } = useKnown();
  const patient = known.patient;
  const [load, setLoad] = useState<Load>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!patient) return;
    let live = true;
    setLoad({ status: "loading" });
    getContext(patient.name)
      .then(async (c) => {
        if (!live) return;
        if (!c.abha.linked) return setLoad({ status: "none" });
        try {
          const profile = await getProfile(patient.name);
          if (live) setLoad({ status: "ready", profile });
        } catch (e) {
          if (!live) return;
          const message = e instanceof ApiError ? e.message : "Could not load the ABHA profile.";
          setLoad(e instanceof ApiError && e.kind === "auth" ? { status: "expired", message } : { status: "error", message });
        }
      })
      .catch((e: unknown) => live && setLoad({ status: "error", message: e instanceof ApiError ? e.message : "Could not check this patient." }));
    return () => {
      live = false;
    };
  }, [patient?.name, attempt]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadCard = useCallback(() => getCard(patient!.name), [patient]);
  const loadQr = useCallback(() => getQrCode(patient!.name), [patient]);

  if (!patient) return null;
  if (load.status === "loading") return <p className="muted" role="status">Loading {patient.patient_name}…</p>;
  if (load.status === "none") {
    return (
      <div className="card panel">
        <h2>{patient.patient_name} has no ABHA yet</h2>
        <p className="lede">There is nothing to show until an ABHA is created or linked.</p>
        <div className="actions">
          <a className="btn btn-primary" href={hrefFor("create")}>Create an ABHA</a>
          
        </div>
      </div>
    );
  }
  if (load.status === "expired") {
    return (
      <div className="card panel">
        <h2>The ABHA session has expired</h2>
        <p className="lede">ABDM only shows the profile to someone who has just proved who the patient is. Verify the patient again to view it.</p>
        <ErrorNote>{load.message}</ErrorNote>
        <div className="actions"><a className="btn btn-primary" href={hrefFor("verify")}>Verify the patient</a></div>
      </div>
    );
  }
  if (load.status === "error") {
    return (
      <div className="card panel">
        <ErrorNote>{load.message}</ErrorNote>
        <div className="actions"><button type="button" className="btn" onClick={() => setAttempt((n) => n + 1)}>Try again</button></div>
      </div>
    );
  }

  return (
    <div className="stack-lg">
      <section className="card panel" aria-labelledby="profile-title">
        <h2 id="profile-title">Profile and photograph</h2>
        <ProfileCard profile={load.profile} personName={patient.patient_name} />
        <div className="actions"><button type="button" className="btn" onClick={() => setAttempt((n) => n + 1)}>Refresh from ABDM</button></div>
      </section>
      <section className="card panel" aria-labelledby="cards-title">
        <h2 id="cards-title">Card and QR code</h2>
        <div className="grid-2">
          <div>
            <h3>ABHA card</h3>
            <PngPreview title="ABHA card" load={loadCard} />
          </div>
          <div>
            <h3>QR code</h3>
            <PngPreview title="QR code" load={loadQr} />
          </div>
        </div>
        <p className="muted small">Images are fetched when you ask, shown here and not saved on the server.</p>
      </section>
    </div>
  );
}
