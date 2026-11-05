import type { ProfileSummary } from "../api/types";
import { profileRows } from "./profile";

/** The ABHA profile as the server shows it: photograph beside the facts (mobile and email arrive masked). */
export function ProfileCard({ profile, personName }: { profile: ProfileSummary; personName: string }) {
  const rows = profileRows(profile);
  return (
    <div className="profile-grid">
      {profile.photo && <img className="profile-photo" src={profile.photo} alt={`Photograph of ${personName}`} />}
      <dl className="facts">
        {rows.map(([k, v]) => (
          <div key={k}>
            <dt>{k}</dt>
            <dd>{v}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
